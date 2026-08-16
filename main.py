"""
Ridge: Corrective RAG (CRAG) State Machine Architecture
======================================================
This module implements the core LangGraph state graph for Corrective Retrieval-Augmented Generation:
  1. Retrieve: MMR vector search via ChromaDB + all-MiniLM-L6-v2.
  2. Re-rank: FlashRank cross-encoder re-ranking.
  3. Grade: Groq LLM hallucination and relevance evaluator.
  4. Rewrite / Web Search: Adaptive query reformulation and DuckDuckGo fallback.
  5. Generate: Grounded synthesis across all verified passages.
"""

import os
import sys
import time
from typing import Literal

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


load_dotenv()

DEFAULT_QUESTION = "What is task decomposition in LLM agents?"


class GraphState(TypedDict):
    question: str
    original_question: str
    documents: list[str]
    documents_metadata: list[dict]
    generation: str
    loop_count: int
    past_queries: list[str]
    latency_ms: int
    doc_grades: list[dict]


class DocGrade(BaseModel):
    index: int = Field(description="Index of the document")
    rationale: str = Field(description="Brief explanation of why the document is relevant or not")
    score: Literal["yes", "no"] = Field(description="'yes' if relevant or partially relevant, 'no' if completely unrelated")

class BatchGrades(BaseModel):
    grades: list[DocGrade] = Field(
        description="List of grades for all provided documents"
    )


def get_settings() -> dict:
    return {
        "embedding_model": os.getenv(
            "EMBEDDING_MODEL",
            "sentence-transformers/all-MiniLM-L6-v2",
        ),
        "chroma_dir": os.getenv("CHROMA_DIR", "./chroma_db"),
        # Lean/fast model for grading + rewrite (called up to retriever_k times per loop)
        "groq_api_key": os.getenv("GROQ_API_KEY"),
        "groq_model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        "retriever_k": int(os.getenv("RETRIEVER_K", "5")),
        "retriever_fetch_k": int(os.getenv("RETRIEVER_FETCH_K", "15")),
        "retriever_lambda_mult": float(os.getenv("RETRIEVER_LAMBDA_MULT", "0.5")),
        "max_rewrite_loops": int(os.getenv("MAX_REWRITE_LOOPS", "1")),
    }


def unload_ollama_model(model_name: str, base_url: str):
    import requests
    print(f"\n--- UNLOADING MODEL: {model_name} ---")
    try:
        url = f"{base_url.rstrip('/')}/api/chat"
        requests.post(url, json={"model": model_name, "keep_alive": 0}, timeout=5)
    except Exception as e:
        print(f"  Failed to unload model {model_name}: {e}")


def _get_retry_after(exc, default=5):
    try:
        err_data = exc.args[0].error.metadata.get("retry_after_seconds")
        if err_data:
            return float(err_data) + 1
    except Exception:
        pass
    return default


def get_vectorstore():
    settings = get_settings()
    embeddings = HuggingFaceEmbeddings(model_name=settings["embedding_model"])
    return Chroma(
        persist_directory=settings["chroma_dir"],
        embedding_function=embeddings,
    )

def ingest_document(text_or_url: str) -> dict:
    import urllib.parse
    import os
    from rag_ingest import load_and_split_source, _sub_chunk
    from langchain_core.documents import Document
    
    print(f"\n=== INGESTING ===\nInput: {text_or_url[:100]}...")
    
    # Check if URL
    is_url = False
    try:
        result = urllib.parse.urlparse(text_or_url)
        is_url = all([result.scheme, result.netloc])
    except Exception:
        pass

    doc_splits = []
    if is_url:
        print("Detected URL, using rag_ingest...")
        doc_splits = load_and_split_source(text_or_url)
    elif os.path.exists(text_or_url):
        print("Detected local file, using rag_ingest...")
        doc_splits = load_and_split_source(text_or_url)
    else:
        print("Detected raw text, processing...")
        doc = Document(page_content=text_or_url, metadata={"source": "user_input"})
        doc_splits = _sub_chunk([doc], 1500, 200)
        
    print(f"Created {len(doc_splits)} chunks. Storing in Chroma...")
    vectorstore = get_vectorstore()
    vectorstore.add_documents(doc_splits)
    print("Ingestion complete.")
    
    # Generate suggestions in a background thread so ingestion returns immediately
    if doc_splits:
        try:
            import threading
            context_text = " ".join(d.page_content for d in doc_splits[:3])[:1500]
            threading.Thread(target=generate_suggestions, args=(context_text,), daemon=True).start()
        except Exception as e:
            print(f"Error launching background suggestions: {e}")

    return {"status": "success", "chunks_added": len(doc_splits)}

def generate_suggestions(text: str):
    import json
    from langchain_groq import ChatGroq
    from pydantic import BaseModel, Field
    
    class Suggestions(BaseModel):
        questions: list[str] = Field(description="List of exactly 3 natural, concise questions about the document")
    
    settings = get_settings()
    try:
        # Use ultra-fast llama-3.1-8b-instant (800+ tok/s on Groq) for sub-250ms latency
        llm = ChatGroq(
            api_key=settings["groq_api_key"],
            model_name="llama-3.1-8b-instant",
            temperature=0.6,
            max_tokens=256,
        ).with_structured_output(Suggestions)
        
        prompt = (
            "You are an AI assistant. Based on this document excerpt, generate exactly 3 short, insightful questions "
            "that a user would ask about the concepts.\n\n"
            f"Excerpt:\n{text}\n"
        )
        
        result = llm.invoke(prompt)
        
        if result and getattr(result, 'questions', None):
            with open("suggestions.json", "w") as f:
                json.dump({"suggestions": result.questions}, f)
            print(f"Ultra-fast generated {len(result.questions)} suggestions.")
            return result.questions
    except Exception as e:
        print(f"Groq suggestions error (using fallback): {e}")

    return []

def build_app():
    settings = get_settings()

    print("Initializing Memory and Brain...")
    vectorstore = get_vectorstore()

    retriever = vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={
            "k": 50, # Fetch more for re-ranking
            "fetch_k": 100,
            "lambda_mult": settings["retriever_lambda_mult"],
        },
    )

    from flashrank import Ranker, RerankRequest
    ranker = Ranker(cache_dir="./.flashrank_cache")

    from duckduckgo_search import DDGS

    llm_grade = ChatGroq(
        api_key=settings["groq_api_key"],
        model_name=settings["groq_model"],
        temperature=0,
    )
    llm_generate = ChatGroq(
        api_key=settings["groq_api_key"],
        model_name=settings["groq_model"],
        temperature=0,
    )
    structured_grader = llm_grade.with_structured_output(BatchGrades)

    def retrieve(state: GraphState) -> dict:
        t0 = time.time()
        print("\n--- NODE: RETRIEVE ---")
        docs = retriever.invoke(state["question"])
        doc_texts = [d.page_content for d in docs]
        doc_metas = [d.metadata for d in docs]
        print(f"Retrieved {len(doc_texts)} documents from Chroma.")

        final_texts = []
        final_metas = []
        if doc_texts:
            print("--- RE-RANKING DOCUMENTS ---")
            passages = [{"id": i, "text": doc, "meta": doc_metas[i]} for i, doc in enumerate(doc_texts)]
            rerankrequest = RerankRequest(query=state["question"], passages=passages)
            rerank_results = ranker.rerank(rerankrequest)
            
            rerank_results = sorted(rerank_results, key=lambda x: x["score"], reverse=True)
            for res in rerank_results[:settings["retriever_k"]]:
                final_texts.append(res["text"])
                final_metas.append(res["meta"])
                # Inject score into meta as native python float for clean JSON serialization
                final_metas[-1]["score"] = float(res["score"])
            print(f"Kept top {len(final_texts)} documents after re-ranking.")
        else:
            final_texts = doc_texts
            final_metas = doc_metas
            
        return {"documents": final_texts, "documents_metadata": final_metas, "latency_ms": int((time.time() - t0) * 1000)}

    def grade_documents(state: GraphState) -> dict:
        t0 = time.time()
        print("--- NODE: GRADE DOCUMENTS ---")
        question = state["question"]
        doc_texts = state.get("documents", [])
        doc_metas = state.get("documents_metadata", [])

        if not doc_texts:
            print("Decision: 'no' (empty database results)")
            return {"generation": "no"}

        docs_str = "\n".join(
            f"--- Document {i} ---\n{doc}\n" for i, doc in enumerate(doc_texts)
        )

        prompt = (
            "You are an expert relevance evaluator for a technical retrieval system.\n"
            "Assess whether the retrieved document is relevant or helpful for answering the user question.\n\n"
            f"Question: {question}\n\n"
            f"Documents:\n{docs_str}\n\n"
            "Grading instructions:\n"
            "1. Score 'yes' if the document contains facts, concepts, algorithms, heuristics, definitions, or methods relevant or partially relevant to the question.\n"
            "2. Score 'no' ONLY if the document is completely unrelated to the domain or subject matter of the question.\n"
            "Be helpful and objective. For questions asking about benefits, advantages, implications, or summaries of the documented methods, score 'yes' if the document discusses those methods."
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
                print(f"  Grading attempt {attempt + 1}/3 failed: {e}. Waiting {wait}s...")
                time.sleep(wait)

        if result is None:
            print(f"  Grading gave up after 3 attempts. Treating all as 'no'. Last error: {last_err}")
            return {"generation": "no", "documents": [], "documents_metadata": [], "doc_grades": [], "latency_ms": int((time.time() - t0) * 1000)}

        relevant_docs = []
        relevant_metas = []
        doc_grades = []
        for g in result.grades:
            if 0 <= g.index < len(doc_texts):
                score = g.score.lower()
                meta = doc_metas[g.index] if g.index < len(doc_metas) else {}
                doc_grades.append({"index": g.index, "score": score, "rationale": g.rationale, "source": meta.get("source", "unknown"), "relevance": float(meta.get("score", 0))})
                preview = doc_texts[g.index][:150].replace("\n", " ")
                print(f"  Doc {g.index + 1}/{len(doc_texts)} decision: '{score}'")
                print(f"    rationale: {g.rationale}")
                print(f"    content preview: \"{preview}...\"")
                if score == "yes":
                    relevant_docs.append(doc_texts[g.index])
                    relevant_metas.append(meta)

        lat = int((time.time() - t0) * 1000)
        if relevant_docs:
            print(f"Decision: 'yes' ({len(relevant_docs)}/{len(doc_texts)} docs relevant)")
            return {"generation": "yes", "documents": relevant_docs, "documents_metadata": relevant_metas, "doc_grades": doc_grades, "latency_ms": lat}

        print("Decision: 'no' (no relevant docs found)")
        return {"generation": "no", "documents": [], "documents_metadata": [], "doc_grades": doc_grades, "latency_ms": lat}

    def generate(state: GraphState) -> dict:
        t0 = time.time()
        print("--- NODE: GENERATE ---")
        question = state.get("original_question") or state["question"]
        docs = state["documents"]
        context = "\n\n".join(docs)

        print("--- FULL CONTEXT PASSED TO GENERATE ---")
        for j, d in enumerate(docs):
            print(f"  [Doc {j + 1}] {d}")
            print("  " + "-" * 40)
        print(f"  Total context length: {len(context)} chars")

        prompt = (
            "You are Ridge, an expert AI assistant providing detailed, clear, and well-structured answers.\n"
            "Use the provided context to thoroughly answer the user's question.\n\n"
            "Guidelines:\n"
            "1. Synthesize insights across all provided document excerpts and web search findings.\n"
            "2. Explain technical mechanisms, implications, benefits, and practical use cases derived from the context.\n"
            "3. If the context covers specific methods (such as Union by Rank, Path Compression, tree operations, time complexities), directly explain their purpose, efficiency gains (e.g. reducing tree height from O(N) to near O(1)/O(α(N))), and operational advantages.\n"
            "4. Format your answer with clean markdown headings, bullet points, and code/formulas where helpful.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {question}"
        )

        for attempt in range(3):
            try:
                response = llm_generate.invoke(prompt)
                return {"generation": response.content, "latency_ms": int((time.time() - t0) * 1000)}
            except Exception as e:
                wait = _get_retry_after(e, default=2 * (attempt + 1))
                print(f"  generate attempt {attempt + 1}/3 failed: {e}. Waiting {wait}s...")
                time.sleep(wait)

        return {
            "generation": "Sorry, the model provider is currently unavailable after multiple retries.",
            "latency_ms": int((time.time() - t0) * 1000)
        }

    def rewrite(state: GraphState) -> dict:
        print("--- NODE: REWRITE QUERY ---")
        original_q = state.get("original_question") or state["question"]
        current_loops = state.get("loop_count", 0) + 1
        past_queries = state.get("past_queries", [])

        prompt = (
            "You are an expert search query optimizer for a technical document retrieval system.\n"
            f"Original user question: {original_q}\n"
            f"Previously attempted search queries that yielded no matches: {past_queries}\n\n"
            "Generate a different, focused search query using alternative core keywords, technical terms, or broader concepts related to the original question.\n"
            "Do NOT drift into unrelated topics.\n"
            "Output only the raw search query string without quotes or markdown."
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
            new_query = original_q

        print(f"New Search Query: '{new_query}'")
        print(f"Current Loop Counter: {current_loops}/{settings['max_rewrite_loops']}")

        return {
            "question": new_query,
            "original_question": original_q,
            "loop_count": current_loops,
            "past_queries": past_queries + [new_query],
        }

    def web_search(state: GraphState) -> dict:
        t0 = time.time()
        print("--- NODE: WEB SEARCH ---")
        search_query = state.get("original_question") or state["question"]
        print(f"Searching web for: '{search_query}'")
        
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(search_query, max_results=4))
            if results:
                docs = "\n\n".join(
                    f"--- Web Source: {r.get('title', 'Web Search')} ({r.get('href', '')}) ---\n{r.get('body', '')}"
                    for r in results if r.get('body')
                )
            else:
                docs = "No web search snippets returned."
        except Exception as e:
            docs = f"Web search could not retrieve external pages: {e}"
            
        web_results = f"\n\nWeb Search Results:\n{docs}"
        
        current_docs = state.get("documents", [])
        current_docs.append(web_results)
        return {"documents": current_docs, "latency_ms": int((time.time() - t0) * 1000)}

    def decide_to_generate(state: GraphState) -> str:
        print("--- ROUTER: EVALUATING NEXT STEP ---")

        if state["generation"] == "yes":
            print("-> Document matches. Route to: GENERATE")
            return "generate"

        loops = state.get("loop_count", 0)
        if loops >= settings["max_rewrite_loops"]:
            print(f"-> Safety valve tripped after {loops} rewrite attempts. Route to: WEB SEARCH.")
            return "web_search"

        print("-> Document irrelevant. Route to: REWRITE")
        return "rewrite"

    workflow = StateGraph(GraphState)
    workflow.add_node("retrieve_node", retrieve)
    workflow.add_node("web_search_node", web_search)
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
            "web_search": "web_search_node",
        },
    )
    workflow.add_edge("rewrite_node", "retrieve_node")
    workflow.add_edge("web_search_node", "generate_node")
    workflow.add_edge("generate_node", END)

    return workflow.compile()


def run_question(question: str) -> dict:
    app = build_app()
    result = app.invoke(
        {
            "question": question,
            "documents": [],
            "documents_metadata": [],
            "generation": "",
            "loop_count": 0,
            "past_queries": [],
            "latency_ms": 0,
        }
    )
    return result


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    question = " ".join(args).strip() or DEFAULT_QUESTION
    print(f"\n=== TESTING QUERY: {question} ===")

    final_state = run_question(question)

    print("\n=== FINAL ANSWER ===")
    print(final_state["generation"])


if __name__ == "__main__":
    main()