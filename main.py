import os
from typing import List
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

# --- 1. INITIALIZE MEMORY & BRAIN ---
print("Initializing Memory and Brain...")
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)

retriever = vectorstore.as_retriever(
    search_type="mmr",
    search_kwargs={"k": 5, "fetch_k": 15, "lambda_mult": 0.5}
)

llm = ChatOllama(
    model="gemma4:12b",  # verified via curl http://100.75.99.22:11434/api/tags — has tools capability, needed for structured grading
    base_url="http://100.75.99.22:11434",
    temperature=0,
)

# --- 2. DEFINE STATE & SCHEMAS ---
class GraphState(TypedDict):
    question: str
    documents: List[str]
    generation: str
    loop_count: int
    past_queries: List[str]  # short-term memory so rewrite doesn't repeat itself

from typing import Literal

class Grade(BaseModel):
    score: Literal["yes", "no"] = Field(description="Are the documents relevant to the question? 'yes' or 'no'")

structured_grader = llm.with_structured_output(Grade)

# --- 3. DEFINE THE NODES ---
def retrieve(state: GraphState):
    print("\n--- NODE: RETRIEVE ---")
    question = state["question"]
    docs = retriever.invoke(question)
    doc_texts = [d.page_content for d in docs]
    print(f"Retrieved {len(doc_texts)} documents.")
    return {"documents": doc_texts}

import time

def _get_retry_after(exc, default=5):
    """Pull a provider-suggested wait time out of the error if present (OpenRouter-style).
    Falls back to `default` for local Ollama errors, which won't have this metadata."""
    try:
        err_data = exc.args[0].error.metadata.get("retry_after_seconds")
        if err_data:
            return float(err_data) + 1
    except Exception:
        pass
    return default

def grade_documents(state: GraphState):
    print("--- NODE: GRADE DOCUMENTS ---")
    question = state["question"]
    doc_texts = state["documents"]

    if not doc_texts:
        print("Decision: 'no' (Empty database results)")
        return {"generation": "no"}

    # Grade each retrieved doc independently. If ANY is relevant, we proceed to
    # generate (using just that doc set) instead of rewriting unnecessarily.
    relevant_docs = []
    for i, doc in enumerate(doc_texts):
        prompt = (
            f"You are a grader assessing whether a retrieved document is relevant to a user question.\n\n"
            f"Document:\n{doc}\n\n"
            f"Question: {question}\n\n"
            f"Give a binary score 'yes' or 'no' based on TOPIC overlap, not structural similarity.\n"
            f"Score 'yes' only if the document discusses the same subject matter as the question "
            f"(shares specific keywords, entities, or concepts about that subject), even if it doesn't "
            f"fully answer it.\n"
            f"Score 'no' if the document is about a different subject, even if it happens to share a "
            f"generic format (e.g. a list, a template, or placeholder text) with no actual topical connection.\n"
            f"Example: if the question is about baking a cake, a document listing generic placeholder "
            f"goals like '{{{{user goal 1}}}}' with no mention of baking, cake, or food is 'no' — "
            f"shared list structure is not topic relevance."
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
                print(f"  Doc {i+1}/{len(doc_texts)} attempt {attempt+1}/3 failed: {e}. Waiting {wait}s...")
                time.sleep(wait)

        if result is None:
            # Skip this doc rather than crashing the whole graph on a flaky call
            print(f"  Doc {i+1}/{len(doc_texts)}: giving up after 3 attempts, treating as 'no'. Last error: {last_err}")
            continue

        preview = doc[:200].replace("\n", " ")
        print(f"  Doc {i+1}/{len(doc_texts)} decision: '{result.score}'")
        print(f"    content preview: \"{preview}...\"")
        if result.score == "yes":
            relevant_docs.append(doc)

    if relevant_docs:
        print(f"Decision: 'yes' ({len(relevant_docs)}/{len(doc_texts)} docs relevant)")
        print("--- FULL CONTENT OF RELEVANT DOCS (what generate will see) ---")
        for j, rd in enumerate(relevant_docs):
            print(f"  [Relevant Doc {j+1}] {rd}")
            print("  " + "-" * 40)
        return {"generation": "yes", "documents": relevant_docs}

    print("Decision: 'no' (no relevant docs found)")
    return {"generation": "no"}

def generate(state: GraphState):
    print("--- NODE: GENERATE ---")
    question = state["question"]
    context = "\n\n".join(state["documents"])

    prompt = (
        f"You are an AI assistant. Answer the question using ONLY the provided context.\n"
        f"If the context does not contain the answer, cleanly state that you cannot find it.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}"
    )

    for attempt in range(3):
        try:
            response = llm.invoke(prompt)
            return {"generation": response.content}
        except Exception as e:
            wait = _get_retry_after(e, default=2 * (attempt + 1))
            print(f"  generate attempt {attempt+1}/3 failed: {e}. Waiting {wait}s...")
            time.sleep(wait)

    return {"generation": "Sorry, the model provider is currently unavailable after multiple retries."}

def rewrite(state: GraphState):
    print("--- NODE: REWRITE QUERY ---")
    question = state["question"]
    current_loops = state.get("loop_count", 0) + 1
    past_queries = state.get("past_queries", [])

    prompt = (
        f"You are an expert search engine optimizer.\n"
        f"Your job is to rewrite the original question into a single, concise search query.\n"
        f"WARNING: You have already tried the following queries and they failed: {past_queries}\n"
        f"You MUST generate a completely different search query using alternative keywords or synonyms.\n"
        f"DO NOT output any explanations, formatting, or markdown. Output ONLY the raw search text string.\n\n"
        f"Question to rewrite: {question}"
    )

    new_query = None
    for attempt in range(3):
        try:
            response = llm.invoke(prompt)
            new_query = response.content.strip().replace("`", "").replace('"', '')
            break
        except Exception as e:
            wait = _get_retry_after(e, default=2 * (attempt + 1))
            print(f"  rewrite attempt {attempt+1}/3 failed: {e}. Waiting {wait}s...")
            time.sleep(wait)

    if new_query is None:
        # Fall back to the original question unchanged rather than crashing
        new_query = question

    print(f"New Search Query: '{new_query}'")
    print(f"Current Loop Counter: {current_loops}/3")

    past_queries = past_queries + [new_query]  # new list, avoid mutating state in place

    return {
        "question": new_query,
        "loop_count": current_loops,
        "past_queries": past_queries
    }

# --- 4. DEFINE THE ROUTER ---
def decide_to_generate(state: GraphState):
    print("--- ROUTER: EVALUATING NEXT STEP ---")

    if state["generation"] == "yes":
        print("-> Document matches. Route to: GENERATE")
        return "generate"

    loops = state.get("loop_count", 0)
    if loops >= 3:
        print(f"-> [SAFETY VALVE TRIPPED] Looped {loops} times without success. Forcing exit.")
        return "force_exit"

    print("-> Document irrelevant. Route to: REWRITE")
    return "rewrite"

# --- 5. BUILD THE STATE MACHINE ---
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
        "force_exit": "generate_node"
    }
)

workflow.add_edge("rewrite_node", "retrieve_node")
workflow.add_edge("generate_node", END)

app = workflow.compile()

# --- RUN THE SYSTEM ---
if __name__ == "__main__":
    test_question = "What is task decomposition in LLM agents?"
    print(f"\n=== TESTING QUERY: {test_question} ===")

    final_state = app.invoke({
        "question": test_question,
        "loop_count": 0,
        "past_queries": []
    })

    print("\n=== FINAL ANSWER ===")
    print(final_state["generation"])
