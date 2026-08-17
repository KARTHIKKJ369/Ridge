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

import json
import os
import re
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
    confidence: dict
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
        # Primary synthesis model & Fast model for grading/suggestions/rewrite
        "groq_api_key": os.getenv("GROQ_API_KEY"),
        "groq_model": os.getenv("GROQ_MODEL", "groq/compound"),
        "groq_fast_model": os.getenv("GROQ_FAST_MODEL", "groq/compound-mini"),
        "retriever_k": int(os.getenv("RETRIEVER_K", "4")),
        "retriever_fetch_k": int(os.getenv("RETRIEVER_FETCH_K", "25")),
        "retriever_lambda_mult": float(os.getenv("RETRIEVER_LAMBDA_MULT", "0.5")),
        "max_rewrite_loops": int(os.getenv("MAX_REWRITE_LOOPS", "1")),
    }


def clean_llm_response(text: str) -> str:
    """Strip reasoning/thought blocks, normalize raw html break tags, and clean whitespace."""
    if not text:
        return ""
    if "</think>" in text:
        text = text.split("</think>", 1)[1]
    text = text.replace("<think>", "").replace("</think>", "")
    # Normalize accidental raw HTML breaks into clean newlines
    text = re.sub(r"<br\s*/?>\s*•", "\n- ", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>\s*-", "\n- ", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n\n", text, flags=re.IGNORECASE)
    return text.strip()


def extract_batch_grades(raw_text: str, num_docs: int) -> BatchGrades:
    """Safely extracts BatchGrades from markdown/JSON text output with regex fallback."""
    raw = clean_llm_response(raw_text)
    
    # 1. Try standard JSON decode
    json_candidate = raw
    if "```json" in json_candidate:
        json_candidate = json_candidate.split("```json")[1].split("```")[0]
    elif "```" in json_candidate:
        json_candidate = json_candidate.split("```")[1].split("```")[0]
    
    match = re.search(r"\{.*\}", json_candidate, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            grades = []
            for idx, item in enumerate(data.get("grades", [])):
                doc_idx = int(item.get("index", idx))
                rationale = str(item.get("rationale", "")).strip()
                score_val = str(item.get("score", "no")).strip().lower()
                score = "yes" if score_val in ["yes", "true", "1"] else "no"
                grades.append(DocGrade(index=doc_idx, rationale=rationale, score=score))
            if grades:
                return BatchGrades(grades=grades)
        except Exception:
            pass

    # 2. Resilient regex field extraction if JSON has unescaped quotes
    grades = []
    items = re.findall(r'\{[^{}]*?"index"[^{}]*?\}', raw, re.DOTALL)
    for idx, item_str in enumerate(items):
        idx_match = re.search(r'"index"\s*:\s*(\d+)', item_str)
        doc_idx = int(idx_match.group(1)) if idx_match else idx
        
        score_match = re.search(r'"score"\s*:\s*"(yes|no|true|false|1|0)"', item_str, re.IGNORECASE)
        score_val = score_match.group(1).lower() if score_match else "no"
        score = "yes" if score_val in ["yes", "true", "1"] else "no"
        
        rat_match = re.search(r'"rationale"\s*:\s*"(.*?)"(?=,\s*"score"|\s*\})', item_str, re.DOTALL)
        rationale = rat_match.group(1) if rat_match else ""
        
        grades.append(DocGrade(index=doc_idx, rationale=rationale, score=score))
    
    if grades:
        return BatchGrades(grades=grades)
    
    raise ValueError(f"Could not extract JSON grades: {raw[:150]}")


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


def get_device() -> str:
    import torch
    if torch.backends.mps.is_available():
        return "mps"
    elif torch.cuda.is_available():
        return "cuda"
    return "cpu"


def get_embeddings(model_name: str | None = None) -> HuggingFaceEmbeddings:
    settings = get_settings()
    model = model_name or settings["embedding_model"]
    device = get_device()
    return HuggingFaceEmbeddings(
        model_name=model,
        model_kwargs={"device": device},
        encode_kwargs={"normalize_embeddings": True},
    )


def get_vectorstore():
    settings = get_settings()
    embeddings = get_embeddings(settings["embedding_model"])
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
    import re
    from langchain_groq import ChatGroq
    
    settings = get_settings()
    try:
        llm = ChatGroq(
            api_key=settings["groq_api_key"],
            model_name=settings["groq_fast_model"],
            temperature=0.6,
            max_tokens=1024,
        )
        
        prompt = (
            "You are an AI assistant. Based on this document excerpt, generate exactly 3 short, insightful questions "
            "that a user would ask about the concepts.\n\n"
            f"Excerpt:\n{text}\n\n"
            "Return ONLY a valid JSON object matching this schema:\n"
            '{"questions": ["question 1", "question 2", "question 3"]}'
        )
        
        resp = llm.invoke(prompt)
        raw = clean_llm_response(resp.content)
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            questions = [str(q).strip() for q in data.get("questions", []) if q]
            if questions:
                with open("suggestions.json", "w") as f:
                    json.dump({"suggestions": questions[:3]}, f)
                print(f"Ultra-fast generated {len(questions[:3])} suggestions.")
                return questions[:3]
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
            "k": 50,  # Fetch more for re-ranking
            "fetch_k": 100,
            "lambda_mult": settings["retriever_lambda_mult"],
        },
    )

    from flashrank import Ranker, RerankRequest
    ranker = Ranker(cache_dir="./.flashrank_cache")

    from ddgs import DDGS

    llm_fast = ChatGroq(
        api_key=settings["groq_api_key"],
        model_name=settings["groq_fast_model"],
        temperature=0.0,
        max_tokens=900,
        max_retries=2,
    )
    llm_generate = ChatGroq(
        api_key=settings["groq_api_key"],
        model_name=settings["groq_model"],
        temperature=0.1,
        max_tokens=800,
        max_retries=1,
    )

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
            f"--- Document {i} ---\n{doc[:450].strip()}\n" for i, doc in enumerate(doc_texts[:4])
        )

        prompt = (
            "You are an expert relevance evaluator for a technical document retrieval system.\n"
            "Assess whether the retrieved documents are relevant or helpful for answering the user question.\n\n"
            f"User Question: {question}\n\n"
            f"Retrieved Documents:\n{docs_str}\n\n"
            "Evaluation Rules:\n"
            "1. GIBBERISH / NOISE FILTER: If the user question is random characters or nonsensical gibberish (e.g. 'euhygvdvg vbhsd'), you MUST score 'no' for all documents.\n"
            "2. IDENTITY & PROFILE QUESTIONS: If the question asks about a person, and the document contains their resume or background, score 'yes'.\n"
            "3. TECHNICAL CONCEPTS: If the question asks about a method or algorithm, score 'yes' if the document discusses it.\n"
            "4. UNRELATED DOCUMENTS: Score 'no' if the document is on a completely different subject.\n\n"
            "Return ONLY a valid JSON object matching this schema:\n"
            '{"grades": [{"index": 0, "rationale": "...", "score": "yes" | "no"}]}'
        )

        result = None
        last_err = None
        for attempt in range(2):
            try:
                resp = llm_fast.invoke(prompt)
                result = extract_batch_grades(resp.content, len(doc_texts))
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
        doc_grades = state.get("doc_grades", [])
        loop_count = state.get("loop_count", 0)
        context = "\n\n".join(f"[{i+1}] {doc[:750].strip()}" for i, doc in enumerate(docs[:4])).strip()

        print(f"  Total context length: {len(context)} chars")

        # --- COMPUTE COMPOSITE GROUNDED CONFIDENCE METRIC ---
        # 1. Grader Consensus Ratio (35% weight)
        yes_count = sum(1 for g in doc_grades if g.get("score") == "yes")
        total_grades = len(doc_grades)
        grader_ratio = (yes_count / total_grades) if total_grades > 0 else (0.85 if docs else 0.0)

        # 2. Source Provenance Weight (25% weight)
        is_web = any("duckduckgo" in str(d).lower() or "web" in str(d).lower() for d in docs)
        if docs and not is_web:
            source_weight = 1.0
            source_type_name = "Local Knowledge Base"
        elif docs and is_web:
            source_weight = 0.82
            source_type_name = "Web Search Fallback"
        else:
            source_weight = 0.40
            source_type_name = "General Synthesized Knowledge"

        # 3. Context Richness / Relevant Chunks Coverage (25% weight)
        if len(docs) >= 2:
            coverage_weight = 1.0
        elif len(docs) == 1:
            coverage_weight = 0.75
        else:
            coverage_weight = 0.35

        # 4. Search Loop Penalty (15% weight)
        if loop_count == 0:
            loop_weight = 1.0
        elif loop_count == 1:
            loop_weight = 0.85
        else:
            loop_weight = 0.65

        raw_confidence = (grader_ratio * 35) + (source_weight * 25) + (coverage_weight * 25) + (loop_weight * 15)
        confidence_score = max(15, min(99, int(round(raw_confidence))))

        if confidence_score >= 80:
            confidence_level = "HIGH"
        elif confidence_score >= 60:
            confidence_level = "MEDIUM"
        else:
            confidence_level = "LOW"

        confidence_data = {
            "score": confidence_score,
            "level": confidence_level,
            "breakdown": {
                "grader_consensus": round(grader_ratio * 100, 1),
                "source_trust": source_type_name,
                "relevant_chunks": len(docs),
                "reformulation_loops": loop_count,
            }
        }

        prompt = (
            "You are Ridge, an advanced AI research assistant.\n"
            "Synthesize a well-structured, authoritative, and cleanly formatted answer to the user's question based on the provided context.\n\n"
            f"Context findings:\n{context or 'No local document match found.'}\n\n"
            f"Question: {question}\n\n"
            "Formatting & Quality Rules:\n"
            "1. DIRECT EXECUTIVE ANSWER: Start with a clear, direct 1-2 sentence answer before expanding into details.\n"
            "2. CLEAN MARKDOWN STRUCTURE: Use clean markdown hierarchy (## Section, ### Subsections, bullet points, bold keywords).\n"
            "3. TABLES: If presenting comparative or source-level data, format as a valid Markdown table with proper newlines between every row.\n"
            "4. NO RAW HTML: Never output raw HTML tags like <br>, <b>, or <div>. Use standard Markdown line breaks and bullet lists.\n"
            "5. ACCURACY & EVIDENCE: Base factual assertions directly on the verified context findings. If the context is unrelated to the question, state that clearly and provide a grounded explanation.\n"
            "6. NO GIBBERISH: If the question is unintelligible keyboard mash, politely ask for clarification."
        )

        # Primary Model with instant fast model fallback on rate-limit
        try:
            response = llm_generate.invoke(prompt)
            gen_text = clean_llm_response(response.content)
            return {
                "generation": gen_text,
                "confidence": confidence_data,
                "latency_ms": int((time.time() - t0) * 1000)
            }
        except Exception as e:
            print(f"Primary generation rate-limited or error ({e}). Switching instantly to fast model...")
            try:
                response = llm_fast.invoke(prompt)
                gen_text = clean_llm_response(response.content)
                return {
                    "generation": gen_text,
                    "confidence": confidence_data,
                    "latency_ms": int((time.time() - t0) * 1000)
                }
            except Exception as e2:
                print(f"Fallback generation error: {e2}")
                return {
                    "generation": f"Model provider error: {e2}",
                    "confidence": confidence_data,
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
            cleaned = clean_llm_response(response.content)
            candidate_lines = []
            for line in cleaned.split("\n"):
                line_str = line.strip().replace("`", "").replace('"', "").replace("*", "").replace("#", "")
                if not line_str:
                    continue
                if any(skip_kw in line_str.lower() for skip_kw in ["thinking process", "process:", "analyze", "here's", "<", "search query:", "reformulated:", "user question"]):
                    continue
                candidate_lines.append(line_str)
            if candidate_lines:
                new_query = candidate_lines[-1]
        except Exception as e:
            print(f"  rewrite attempt failed: {e}")

        if not new_query or len(new_query) < 3 or new_query.startswith("<"):
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
            with DDGS(timeout=5) as ddgs:
                results = list(ddgs.text(search_query, max_results=3))
                for r in results:
                    title = r.get("title", "Web Source")
                    body = r.get("body", "")[:450].strip()
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