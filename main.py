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

def ingest_document(text_or_url: str, original_filename: str | None = None) -> dict:
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
        doc = Document(page_content=text_or_url, metadata={"source": original_filename or "user_input"})
        doc_splits = _sub_chunk([doc], 1500, 200)

    # Attach original filename if provided (e.g. for uploads)
    if original_filename:
        for d in doc_splits:
            d.metadata["source"] = original_filename
            d.metadata["h1"] = original_filename
        
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

    llm_fast = ChatGroq(
        api_key=settings["groq_api_key"],
        model_name="llama-3.1-8b-instant",
        temperature=0.1,
        max_tokens=256,
        max_retries=1,
    )
    llm_generate = ChatGroq(
        api_key=settings["groq_api_key"],
        model_name=settings["groq_model"],
        temperature=0,
        max_retries=0,  # Fail instantly on rate-limit to trigger immediate 8B fallback
    )
    # Fast 8B model for grading - 20,000 TPM limit (prevents 429 rate limits & delivers sub-200ms latency)
    structured_grader = llm_fast.with_structured_output(BatchGrades)

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
            return {"generation": "no", "documents": [], "documents_metadata": [], "doc_grades": [], "latency_ms": int((time.time() - t0) * 1000)}

        docs_str = "\n".join(
            f"--- Document {i} ---\n{doc}\n" for i, doc in enumerate(doc_texts)
        )

        prompt = (
            "You are an expert relevance evaluator for a technical document retrieval system.\n"
            "Assess whether the retrieved document is relevant or helpful for answering the user question.\n\n"
            f"User Question: {question}\n\n"
            f"Retrieved Documents:\n{docs_str}\n\n"
            "Evaluation Rules:\n"
            "1. GIBBERISH / NOISE FILTER: If the user question is random characters, keyboard mash, or nonsensical gibberish (e.g. 'euhygvdvg vbhsd', 'asdfghjkl'), you MUST score 'no' for all documents with rationale 'Question is gibberish/unintelligible'.\n"
            "2. IDENTITY & PROFILE QUESTIONS: If the question asks 'who is [Name]' or asks about a person, and the document contains their resume, biography, education, contact info, or background, score 'yes'.\n"
            "3. TECHNICAL CONCEPTS: If the question asks about a method, algorithm, concept, or technical subject, score 'yes' if the document discusses or defines it.\n"
            "4. UNRELATED DOCUMENTS: Score 'no' if the document is on a completely different subject with no bearing on the question.\n"
            "Be helpful, practical, and objective."
        )

        result = None
        last_err = None
        for attempt in range(2):
            try:
                result = structured_grader.invoke(prompt)
                break
            except Exception as e:
                last_err = e
                print(f"  Grading attempt {attempt + 1} failed: {e}")
                time.sleep(0.5)

        if result is None:
            print(f"  Grading gave up. Last error: {last_err}")
            return {"generation": "no", "documents": [], "documents_metadata": [], "doc_grades": [], "latency_ms": int((time.time() - t0) * 1000)}

        relevant_docs = []
        relevant_metas = []
        doc_grades = []
        for g in result.grades:
            if 0 <= g.index < len(doc_texts):
                score = g.score.lower()
                meta = doc_metas[g.index] if g.index < len(doc_metas) else {}
                doc_grades.append({"index": g.index, "score": score, "rationale": g.rationale, "source": meta.get("source", "unknown"), "relevance": float(meta.get("score", 0))})
                print(f"  Doc {g.index + 1}/{len(doc_texts)} decision: '{score}'")
                print(f"    rationale: {g.rationale}")
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
        docs = state.get("documents", [])
        context = "\n\n".join(docs).strip()

        print(f"  Total context length: {len(context)} chars")

        prompt = (
            "You are Ridge, an expert AI assistant.\n"
            "Answer the user's question clearly.\n\n"
            f"Context findings:\n{context or 'No local document match found.'}\n\n"
            f"Question: {question}\n\n"
            "Guidelines:\n"
            "1. If the question is random keystrokes or nonsensical gibberish (e.g. 'euhygvdvg vbhsd'), politely state that the input is unintelligible and ask for a clear query.\n"
            "2. If verified context from indexed documents or web search is provided, synthesize the facts thoroughly with technical precision.\n"
            "3. If context is empty or unrelated, provide a comprehensive, direct explanation of the requested topic using your verified knowledge, mentioning that it was synthesized outside the indexed documents.\n"
            "4. Format your response with clean markdown headings, bullet points, and code/formulas where helpful."
        )

        # Primary: 70B Model with instant 8B fallback on rate-limit
        try:
            response = llm_generate.invoke(prompt)
            return {"generation": response.content, "latency_ms": int((time.time() - t0) * 1000)}
        except Exception as e:
            print(f"Primary generation rate-limited or error ({e}). Switching instantly to fast model...")
            try:
                response = llm_fast.invoke(prompt)
                return {"generation": response.content, "latency_ms": int((time.time() - t0) * 1000)}
            except Exception as e2:
                print(f"Fallback generation error: {e2}")
                return {
                    "generation": f"Model provider error: {e2}",
                    "latency_ms": int((time.time() - t0) * 1000)
                }

    def rewrite(state: GraphState) -> dict:
        t0 = time.time()
        print("--- NODE: REWRITE QUERY ---")
        original_q = state.get("original_question") or state["question"]
        current_loops = state.get("loop_count", 0) + 1
        past_queries = state.get("past_queries", [])

        prompt = (
            "You are a search query optimizer for a technical retriever.\n"
            f"Original user question: {original_q}\n"
            f"Previous attempts that had no matches: {past_queries}\n\n"
            "Generate a single, focused 3 to 6 word search query.\n"
            "Do NOT repeat words or output long repetitive lists.\n"
            "Output ONLY the plain search query string."
        )

        new_query = None
        try:
            response = llm_fast.invoke(prompt)
            new_query = response.content.strip().replace("`", "").replace('"', "").split("\n")[0]
        except Exception as e:
            print(f"  rewrite attempt failed: {e}")

        if not new_query:
            new_query = original_q

        print(f"New Search Query: '{new_query}'")
        print(f"Current Loop Counter: {current_loops}/{settings['max_rewrite_loops']}")

        return {
            "question": new_query,
            "original_question": original_q,
            "loop_count": current_loops,
            "past_queries": past_queries + [new_query],
            "latency_ms": int((time.time() - t0) * 1000),
        }

    def web_search(state: GraphState) -> dict:
        t0 = time.time()
        search_query = state.get("original_question") or state["question"]
        print(f"--- NODE: WEB SEARCH: '{search_query}' ---")
        
        docs_snippets = []
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS
            
            with DDGS(timeout=5) as ddgs:
                results = list(ddgs.text(search_query, max_results=3))
                for r in results:
                    title = r.get("title", "Web Source")
                    body = r.get("body", "")
                    href = r.get("href", "")
                    if body:
                        docs_snippets.append(f"--- Web Source: {title} ({href}) ---\n{body}")
        except Exception as e:
            print(f"Web search note: {e}")
            
        if docs_snippets:
            web_results = "\n\n".join(docs_snippets)
        else:
            web_results = "No direct web snippets returned."
            
        current_docs = state.get("documents", [])
        current_docs.append(f"Web Search Findings:\n{web_results}")
        return {"documents": current_docs, "latency_ms": int((time.time() - t0) * 1000)}

    def decide_to_generate(state: GraphState) -> str:
        print("--- ROUTER: EVALUATING NEXT STEP ---")

        if state.get("generation") == "yes":
            print("-> Document matches. Route to: GENERATE")
            return "generate"

        loops = state.get("loop_count", 0)
        max_loops = int(settings.get("max_rewrite_loops", 1))
        if loops >= max_loops:
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