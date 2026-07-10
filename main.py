import os
import sys
import time
from typing import Literal

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import ChatOllama
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


load_dotenv()

DEFAULT_QUESTION = "What is task decomposition in LLM agents?"


class GraphState(TypedDict):
    question: str
    documents: list[str]
    generation: str
    loop_count: int
    past_queries: list[str]


class Grade(BaseModel):
    score: Literal["yes", "no"] = Field(
        description="Are the documents relevant to the question? 'yes' or 'no'"
    )


def get_settings() -> dict:
    return {
        "embedding_model": os.getenv(
            "EMBEDDING_MODEL",
            "sentence-transformers/all-MiniLM-L6-v2",
        ),
        "chroma_dir": os.getenv("CHROMA_DIR", "./chroma_db"),
        # Lean/fast model for grading + rewrite (called up to retriever_k times per loop)
        "ollama_grade_model": os.getenv("OLLAMA_GRADE_MODEL", os.getenv("OLLAMA_MODEL", "llama3.1:8b")),
        # Stronger model for the final answer the user actually reads
        "ollama_generate_model": os.getenv("OLLAMA_GENERATE_MODEL", os.getenv("OLLAMA_MODEL", "gemma4:12b")),
        "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        # How long Ollama keeps a model resident in memory after last use.
        # 16GB unified memory can't comfortably hold both models at once, so
        # this just avoids reloading if you ask several questions in a row —
        # not a permanent "keep both loaded forever" setting.
        "ollama_keep_alive": os.getenv("OLLAMA_KEEP_ALIVE", "10m"),
        "retriever_k": int(os.getenv("RETRIEVER_K", "5")),
        "retriever_fetch_k": int(os.getenv("RETRIEVER_FETCH_K", "15")),
        "retriever_lambda_mult": float(os.getenv("RETRIEVER_LAMBDA_MULT", "0.5")),
        "max_rewrite_loops": int(os.getenv("MAX_REWRITE_LOOPS", "3")),
    }


def _get_retry_after(exc, default=5):
    try:
        err_data = exc.args[0].error.metadata.get("retry_after_seconds")
        if err_data:
            return float(err_data) + 1
    except Exception:
        pass
    return default


def build_app():
    settings = get_settings()

    print("Initializing Memory and Brain...")
    embeddings = HuggingFaceEmbeddings(model_name=settings["embedding_model"])
    vectorstore = Chroma(
        persist_directory=settings["chroma_dir"],
        embedding_function=embeddings,
    )

    retriever = vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={
            "k": settings["retriever_k"],
            "fetch_k": settings["retriever_fetch_k"],
            "lambda_mult": settings["retriever_lambda_mult"],
        },
    )

    llm_grade = ChatOllama(
        model=settings["ollama_grade_model"],
        base_url=settings["ollama_base_url"],
        temperature=0,
        keep_alive=settings["ollama_keep_alive"],
    )
    llm_generate = ChatOllama(
        model=settings["ollama_generate_model"],
        base_url=settings["ollama_base_url"],
        temperature=0,
        keep_alive=settings["ollama_keep_alive"],
    )
    structured_grader = llm_grade.with_structured_output(Grade)

    def retrieve(state: GraphState):
        print("\n--- NODE: RETRIEVE ---")
        docs = retriever.invoke(state["question"])
        doc_texts = [d.page_content for d in docs]
        print(f"Retrieved {len(doc_texts)} documents.")
        return {"documents": doc_texts}

    def grade_documents(state: GraphState):
        print("--- NODE: GRADE DOCUMENTS ---")
        question = state["question"]
        doc_texts = state["documents"]

        if not doc_texts:
            print("Decision: 'no' (empty database results)")
            return {"generation": "no"}

        relevant_docs = []
        for i, doc in enumerate(doc_texts):
            prompt = (
                "You are a grader assessing whether a retrieved document is relevant "
                "to a user question.\n\n"
                f"Document:\n{doc}\n\n"
                f"Question: {question}\n\n"
                "Give a binary score 'yes' or 'no' based on topic overlap, not "
                "structural similarity. Score 'yes' only if the document discusses "
                "the same subject matter as the question, even if it does not fully "
                "answer it. Score 'no' if the document is about a different subject."
            )

            result = None
            last_err = None
            for attempt in range(3):
                try:
                    result = structured_grader.invoke(prompt)
                    break
                except Exception as e:
                    last_err = e
                    wait = _get_retry_after(e, default=2 * (attempt + 1))
                    print(
                        f"  Doc {i + 1}/{len(doc_texts)} attempt {attempt + 1}/3 "
                        f"failed: {e}. Waiting {wait}s..."
                    )
                    time.sleep(wait)

            if result is None:
                print(
                    f"  Doc {i + 1}/{len(doc_texts)}: giving up after 3 attempts, "
                    f"treating as 'no'. Last error: {last_err}"
                )
                continue

            preview = doc[:200].replace("\n", " ")
            print(f"  Doc {i + 1}/{len(doc_texts)} decision: '{result.score}'")
            print(f"    content preview: \"{preview}...\"")
            if result.score == "yes":
                relevant_docs.append(doc)

        if relevant_docs:
            print(f"Decision: 'yes' ({len(relevant_docs)}/{len(doc_texts)} docs relevant)")
            return {"generation": "yes", "documents": relevant_docs}

        print("Decision: 'no' (no relevant docs found)")
        return {"generation": "no"}

    def generate(state: GraphState):
        print("--- NODE: GENERATE ---")
        question = state["question"]
        docs = state["documents"]
        context = "\n\n".join(docs)

        print("--- FULL CONTEXT PASSED TO GENERATE ---")
        for j, d in enumerate(docs):
            print(f"  [Doc {j + 1}] {d}")
            print("  " + "-" * 40)
        print(f"  Total context length: {len(context)} chars")

        prompt = (
            "You are an AI assistant answering a question using ONLY the provided context.\n"
            "The context below may contain multiple separate excerpts from a source document — "
            "synthesize across ALL of them rather than relying on just one.\n"
            "Write a complete answer: include specific details, examples, methods, or terms named "
            "in the context that relate to the question, not just a one-line summary.\n"
            "If the context does not contain the answer, cleanly state that you cannot find it.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {question}"
        )

        for attempt in range(3):
            try:
                response = llm_generate.invoke(prompt)
                return {"generation": response.content}
            except Exception as e:
                wait = _get_retry_after(e, default=2 * (attempt + 1))
                print(f"  generate attempt {attempt + 1}/3 failed: {e}. Waiting {wait}s...")
                time.sleep(wait)

        return {
            "generation": "Sorry, the model provider is currently unavailable after multiple retries."
        }

    def rewrite(state: GraphState):
        print("--- NODE: REWRITE QUERY ---")
        question = state["question"]
        current_loops = state.get("loop_count", 0) + 1
        past_queries = state.get("past_queries", [])

        prompt = (
            "You are an expert search engine optimizer.\n"
            "Rewrite the original question into one concise search query.\n"
            f"Already-tried failed queries: {past_queries}\n"
            "Generate a different query using alternative keywords or synonyms.\n"
            "Output only the raw search text string.\n\n"
            f"Question to rewrite: {question}"
        )

        new_query = None
        for attempt in range(3):
            try:
                response = llm_grade.invoke(prompt)
                new_query = response.content.strip().replace("`", "").replace('"', "")
                break
            except Exception as e:
                wait = _get_retry_after(e, default=2 * (attempt + 1))
                print(f"  rewrite attempt {attempt + 1}/3 failed: {e}. Waiting {wait}s...")
                time.sleep(wait)

        if new_query is None:
            new_query = question

        print(f"New Search Query: '{new_query}'")
        print(f"Current Loop Counter: {current_loops}/{settings['max_rewrite_loops']}")

        return {
            "question": new_query,
            "loop_count": current_loops,
            "past_queries": past_queries + [new_query],
        }

    def decide_to_generate(state: GraphState):
        print("--- ROUTER: EVALUATING NEXT STEP ---")

        if state["generation"] == "yes":
            print("-> Document matches. Route to: GENERATE")
            return "generate"

        loops = state.get("loop_count", 0)
        if loops >= settings["max_rewrite_loops"]:
            print(f"-> Safety valve tripped after {loops} rewrite attempts. Forcing exit.")
            return "force_exit"

        print("-> Document irrelevant. Route to: REWRITE")
        return "rewrite"

    workflow = StateGraph(GraphState)
    workflow.add_node("retrieve_node", retrieve)
    workflow.add_node("grade_node", grade_documents)
    workflow.add_node("generate_node", generate)
    workflow.add_node("rewrite_node", rewrite)

    workflow.set_entry_point("retrieve_node")
    workflow.add_edge("retrieve_node", "grade_node")
    workflow.add_conditional_edges(
        "grade_node",
        decide_to_generate,
        {
            "generate": "generate_node",
            "rewrite": "rewrite_node",
            "force_exit": "generate_node",
        },
    )
    workflow.add_edge("rewrite_node", "retrieve_node")
    workflow.add_edge("generate_node", END)

    return workflow.compile()


def run_question(question: str):
    app = build_app()
    return app.invoke(
        {
            "question": question,
            "documents": [],
            "generation": "",
            "loop_count": 0,
            "past_queries": [],
        }
    )


def main(argv: list[str] | None = None):
    args = sys.argv[1:] if argv is None else argv
    question = " ".join(args).strip() or DEFAULT_QUESTION
    print(f"\n=== TESTING QUERY: {question} ===")

    final_state = run_question(question)

    print("\n=== FINAL ANSWER ===")
    print(final_state["generation"])


if __name__ == "__main__":
    main()