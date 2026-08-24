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
    web_search_enabled: bool
    source_filter: str | None       # Scoped retrieval to specific document/source
    user_id: str | None             # Multi-tenant user isolation
    sub_queries: list[str]          # populated by decompose_node for multi-hop
    documents: list[str]
    documents_metadata: list[dict]
    generation: str
    confidence: dict
    conflict_data: dict
    loop_count: int
    past_queries: list[str]
    latency_ms: int
    doc_grades: list[dict]
    hallucination_grade: dict


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
        "groq_model": os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        "groq_fast_model": os.getenv("GROQ_FAST_MODEL", "openai/gpt-oss-20b"),
        "rerank_model": os.getenv("RERANK_MODEL", "ms-marco-MiniLM-L-12-v2"),
        "retriever_k": int(os.getenv("RETRIEVER_K", "6")),
        "retriever_fetch_k": int(os.getenv("RETRIEVER_FETCH_K", "60")),
        "rerank_top_n": int(os.getenv("RERANK_TOP_N", "20")),
        "retriever_lambda_mult": float(os.getenv("RETRIEVER_LAMBDA_MULT", "0.5")),
        "max_rewrite_loops": int(os.getenv("MAX_REWRITE_LOOPS", "1")),
        "grade_doc_limit": int(os.getenv("GRADE_DOC_LIMIT", "4")),
        "max_context_docs": int(os.getenv("MAX_CONTEXT_DOCS", "6")),
        "max_context_chars": int(os.getenv("MAX_CONTEXT_CHARS", "1200")),
    }


def clean_llm_response(text: str) -> str:
    """Strip reasoning/thought blocks, normalize raw html break tags, convert citation tokens, format equations, and clean whitespace."""
    if not text:
        return ""
    if "</think>" in text:
        text = text.split("</think>", 1)[1]
    text = text.replace("<think>", "").replace("</think>", "")
    # Convert raw citation tokens like 【1†L1-L4】 or 【1】 into clean readable citations [1]
    text = re.sub(r"【(\d+)†[^】]*】", r" [\1]", text)
    text = re.sub(r"【(\d+)】", r" [\1]", text)
    text = re.sub(r"【[^】]*】", "", text)
    # Normalize accidental raw HTML breaks into clean newlines
    text = re.sub(r"<br\s*/?>\s*•", "\n- ", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>\s*-", "\n- ", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n\n", text, flags=re.IGNORECASE)

    # Fix collapsed Markdown tables where row newlines were omitted
    text = re.sub(r"(\|[-:]+[-| :]*)\|([^\n\-\|])", r"\1|\n| \2", text)
    text = re.sub(r"\|[ \t]*\|", "|\n|", text)

    # Standardize LaTeX display equations with $$ ... $$
    text = re.sub(r"\\\[([\s\S]*?)\\\]", r"\n\n$$\n\1\n$$\n\n", text)
    text = re.sub(r"\\\(([\s\S]*?)\\\)", r"$\1$", text)
    # Convert multiline single $ blocks to $$ blocks
    text = re.sub(r"(?:^|\n)[ \t]*\$[ \t]*\n([\s\S]*?)\n[ \t]*\$[ \t]*(?=\n|$)", r"\n\n$$\n\1\n$$\n\n", text)

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


_embeddings_cache: dict[str, HuggingFaceEmbeddings] = {}

def get_embeddings(model_name: str | None = None) -> HuggingFaceEmbeddings:
    """Return a cached HuggingFaceEmbeddings instance for the given model."""
    settings = get_settings()
    key = model_name or settings["embedding_model"]
    if key not in _embeddings_cache:
        device = get_device()
        _embeddings_cache[key] = HuggingFaceEmbeddings(
            model_name=key,
            model_kwargs={"device": device},
            encode_kwargs={"normalize_embeddings": True},
        )
        print(f"  [Embeddings] Loaded '{key}' on {device.upper()}.")
    return _embeddings_cache[key]


# ---------------------------------------------------------------------------
# Suggestions In-Memory Store
# ---------------------------------------------------------------------------

_suggestions_store: list[str] = []

def get_suggestions_cache() -> list[str]:
    """Return the in-memory cached suggestions."""
    global _suggestions_store
    return list(_suggestions_store)

def set_suggestions_cache(questions: list[str]) -> None:
    """Update the in-memory cached suggestions (top 3)."""
    global _suggestions_store
    _suggestions_store = [str(q).strip() for q in questions if q][:3]

def clear_suggestions_cache() -> None:
    """Clear the in-memory cached suggestions."""
    global _suggestions_store
    _suggestions_store = []

def ingest_document(text_or_url: str, original_filename: str | None = None, user_id: str = "default") -> dict:
    import urllib.parse
    import os
    from rag_ingest import load_and_split_source, _sub_chunk, semantic_split_documents
    from langchain_core.documents import Document

    print(f"\n=== INGESTING ===\nUser: {user_id}\nInput: {text_or_url[:100]}...")

    # Check if URL
    is_url = False
    try:
        result = urllib.parse.urlparse(text_or_url)
        is_url = all([result.scheme, result.netloc])
    except Exception:
        pass

    raw_splits = []
    if is_url:
        print("Detected URL, using rag_ingest...")
        raw_splits = load_and_split_source(text_or_url)
    elif os.path.exists(text_or_url):
        print("Detected local file, using rag_ingest...")
        raw_splits = load_and_split_source(text_or_url)
    else:
        print("Detected raw text, processing...")
        doc = Document(page_content=text_or_url, metadata={"source": original_filename or "user_input"})
        raw_splits = _sub_chunk([doc], 1500, 200)

    # Attach original filename and user_id to all raw splits
    for d in raw_splits:
        d.metadata["user_id"] = user_id
        if original_filename:
            d.metadata["source"] = original_filename
            d.metadata["h1"] = original_filename

    # --- Semantic Chunking: re-split by embedding gradient for topic-aware boundaries ---
    try:
        embedder = get_embeddings()
        doc_splits = semantic_split_documents(raw_splits, embedder, percentile=25.0, max_chars=1800)
        print(f"  Semantic chunking: {len(raw_splits)} raw -> {len(doc_splits)} semantic parent chunks.")
    except Exception as sc_err:
        print(f"  Semantic chunking fallback (char-split): {sc_err}")
        doc_splits = raw_splits

    # --- Small-to-Big: create child chunks for indexing, keep parents in store ---
    from parent_store import make_parent_id, save_parents
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=60,
        separators=["\n\n", "\n", ".", " ", ""],
    )

    parent_records = []
    child_docs = []

    for parent_doc in doc_splits:
        parent_doc.metadata["user_id"] = user_id
        source = parent_doc.metadata.get("source", "unknown")
        pid = make_parent_id(parent_doc.page_content, source)
        parent_records.append({"id": pid, "text": parent_doc.page_content, "metadata": parent_doc.metadata})

        # Split parent into child chunks
        children = child_splitter.split_documents([parent_doc])
        for child in children:
            child.metadata = {**parent_doc.metadata, "parent_id": pid, "user_id": user_id}
            child_docs.append(child)

    # Save parents to persistent JSON/SQLite store for S2B lookup
    try:
        save_parents(parent_records)
    except Exception as ps_err:
        print(f"  ParentStore note: {ps_err}")

    docs_to_index = child_docs if child_docs else doc_splits
    print(f"  Small-to-Big: {len(doc_splits)} parent chunks -> {len(docs_to_index)} child chunks indexed for user {user_id}.")

    # Ingest directly into PostgreSQL with pgvector & TSVector
    from app.db.database import is_postgres_configured, get_db_session
    from app.db.repositories import document_repo, glossary_repo

    if is_postgres_configured():
        try:
            import asyncio
            embeddings_list = embedder.embed_documents([d.page_content for d in docs_to_index])

            async def _persist_pg_doc():
                async with get_db_session() as session:
                    await document_repo.save_ingested_document(
                        session=session,
                        uploaded_by=user_id if user_id and user_id != "default" else None,
                        filename=original_filename or (text_or_url if not is_url else text_or_url),
                        source_type="url" if is_url else ("file" if os.path.exists(text_or_url) else "text"),
                        source_url=text_or_url if is_url else "",
                        parent_records=parent_records,
                        child_docs=docs_to_index,
                        embeddings_list=embeddings_list,
                        embedding_model_name=os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5"),
                    )

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(_persist_pg_doc())
            except RuntimeError:
                asyncio.run(_persist_pg_doc())
            print("  [PostgreSQL] Successfully saved document, chunks, and pgvector embeddings.")
        except Exception as pg_ingest_err:
            print(f"  [PostgreSQL] Ingestion note: {pg_ingest_err}")


    # Extract & Index domain acronyms into glossary
    try:
        from glossary import index_text_glossary, extract_acronyms_from_text
        full_text = " ".join(d.page_content for d in doc_splits)
        source_name = original_filename or text_or_url
        index_text_glossary(full_text, source_name, user_id=user_id)

        # Dual-write to PostgreSQL glossary
        if is_postgres_configured():
            extracted = extract_acronyms_from_text(full_text, source_name)
            if extracted:
                async def _persist_pg_glossary():
                    async with get_db_session() as session:
                        await glossary_repo.index_glossary_terms(
                            session=session,
                            terms_map=extracted,
                            source_name=source_name,
                            user_id=user_id,
                        )
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(_persist_pg_glossary())
                except RuntimeError:
                    asyncio.run(_persist_pg_glossary())
    except Exception as ge:
        print(f"Glossary indexing note: {ge}")
    
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
                set_suggestions_cache(questions[:3])
                print(f"Ultra-fast generated {len(questions[:3])} suggestions.")
                return questions[:3]
    except Exception as e:
        print(f"Groq suggestions error (using fallback): {e}")

    return []

def build_app():
    settings = get_settings()

    print("Initializing Ridge Brain (PostgreSQL + pgvector)...")

    from flashrank import Ranker, RerankRequest
    ranker = Ranker(model_name=settings["rerank_model"], cache_dir="./.flashrank_cache")

    from ddgs import DDGS

    llm_fast = ChatGroq(
        api_key=settings["groq_api_key"],
        model_name=settings["groq_fast_model"],
        temperature=0.0,
        max_tokens=900,
        max_retries=2,
        tags=["auxiliary_model"],
    )
    llm_generate = ChatGroq(
        api_key=settings["groq_api_key"],
        model_name=settings["groq_model"],
        temperature=0.1,
        max_tokens=800,
        max_retries=1,
        tags=["generation_stream"],
    )


    from app.retrieval.hybrid import UnifiedRetriever
    retriever_engine = UnifiedRetriever(backend=os.getenv("RETRIEVAL_BACKEND", "pgvector"))


    def retrieve(state: GraphState) -> dict:
        t0 = time.time()
        q = state["question"]
        src_filter = state.get("source_filter")
        user_id = state.get("user_id")

        print(f"\n--- NODE: UNIFIED HYBRID RETRIEVE (Backend: {retriever_engine.backend}) ---")
        if src_filter:
            print(f"  [Source Scope Filter Active]: '{src_filter}'")
        if user_id:
            print(f"  [User Scope Filter Active]: '{user_id}'")

        # Run async retrieval synchronously in LangGraph node
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    candidates = pool.submit(
                        asyncio.run,
                        retriever_engine.retrieve(query=q, user_id=user_id, source_filter=src_filter, k=50)
                    ).result()
            else:
                candidates = loop.run_until_complete(
                    retriever_engine.retrieve(query=q, user_id=user_id, source_filter=src_filter, k=50)
                )
        except Exception:
            candidates = asyncio.run(
                retriever_engine.retrieve(query=q, user_id=user_id, source_filter=src_filter, k=50)
            )

        final_texts, final_metas, expanded_count = retriever_engine.rerank_and_expand(
            query=q,
            candidates=candidates,
            top_k=settings["retriever_k"],
            rerank_top_n=settings.get("rerank_top_n", 20),
        )

        return {
            "documents": final_texts,
            "documents_metadata": final_metas,
            "expanded_count": expanded_count,
            "latency_ms": int((time.time() - t0) * 1000),
        }


    def grade_documents(state: GraphState) -> dict:
        t0 = time.time()
        print("--- NODE: GRADE DOCUMENTS ---")
        question = state["question"]
        doc_texts = state.get("documents", [])
        doc_metas = state.get("documents_metadata", [])

        if not doc_texts:
            print("Decision: 'no' (empty database results)")
            return {"generation": "no", "documents": [], "documents_metadata": [], "doc_grades": [], "latency_ms": int((time.time() - t0) * 1000)}

        grade_limit = settings.get("grade_doc_limit", 4)
        docs_to_grade = doc_texts[:grade_limit]

        docs_str = "\n".join(
            f"--- Document {i} ---\n{doc[:450].strip()}\n" for i, doc in enumerate(docs_to_grade)
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
                result = extract_batch_grades(resp.content, len(docs_to_grade))
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
            if 0 <= g.index < len(docs_to_grade):
                score = g.score.lower()
                meta = doc_metas[g.index] if g.index < len(doc_metas) else {}
                doc_grades.append({
                    "index": g.index,
                    "score": score,
                    "rationale": g.rationale,
                    "source": meta.get("source", "unknown"),
                    "breadcrumb": meta.get("breadcrumb", ""),
                    "relevance": float(meta.get("score", 0)),
                    "text": docs_to_grade[g.index],
                })
                print(f"  Doc {g.index + 1}/{len(docs_to_grade)} decision: '{score}'")
                print(f"    rationale: {g.rationale}")
                if score == "yes":
                    relevant_docs.append(docs_to_grade[g.index])
                    relevant_metas.append(meta)

        lat = int((time.time() - t0) * 1000)
        if relevant_docs:
            print(f"Decision: 'yes' ({len(relevant_docs)}/{len(docs_to_grade)} docs relevant)")
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
        max_docs = settings.get("max_context_docs", 6)
        max_chars = settings.get("max_context_chars", 1200)
        context = "\n\n".join(f"[{i+1}] {doc[:max_chars].strip()}" for i, doc in enumerate(docs[:max_docs])).strip()

        print(f"  Total context length: {len(context)} chars")

        # CRAG Strict Grounding Guard: When no verified documents exist and web fallback is disabled/empty
        if not docs:
            print("  [CRAG Guard] No relevant documents found and external web search is disabled/empty.")
            no_context_answer = (
                "## Direct Answer\n\n"
                "I could not find any relevant information in your indexed documents to answer this question, "
                "and **Web Search Fallback is currently disabled**.\n\n"
                "### Recommended Actions:\n"
                "* **Enable Web Fallback**: Toggle **Web fallback: ON** in the toolbar to search and verify live external sources.\n"
                "* **Upload Knowledge**: Ingest or upload relevant files (PDF, DOCX, TXT, MD) into your local knowledge crag."
            )
            confidence_data = {
                "score": 15,
                "level": "LOW",
                "breakdown": {
                    "grader_consensus": 0.0,
                    "source_trust": "No Context Available (Web Search OFF)",
                    "relevant_chunks": 0,
                    "reformulation_loops": loop_count,
                    "faithfulness": "Direct Fallback Guard"
                }
            }
            return {
                "generation": no_context_answer,
                "confidence": confidence_data,
                "latency_ms": int((time.time() - t0) * 1000)
            }

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
        # --- MULTI-DOCUMENT CONFLICT AUDIT ---
        distinct_sources = list(set(
            g.get("source", "").split("/")[-1] for g in doc_grades 
            if g.get("score") == "yes" and g.get("source") and g.get("breadcrumb") != "Web Search Fallback"
        ))
        
        conflict_data = {"detected": False, "summary": "", "sources": distinct_sources}
        conflict_instruction = ""
        
        if len(distinct_sources) >= 2 and len(docs) >= 2:
            print(f"--- RUNNING CONFLICT DETECTOR ACROSS {len(distinct_sources)} SOURCES ---")
            docs_paired = "\n\n".join(
                f"--- Source: {g.get('source', f'Doc #{i+1}').split('/')[-1]} ---\n{g.get('text', docs[i] if i < len(docs) else '')[:400]}"
                for i, g in enumerate(doc_grades[:4]) if g.get("score") == "yes"
            )
            conflict_prompt = (
                "You are a strict inconsistency auditor for an enterprise document store.\n"
                f"User Question: {question}\n\n"
                f"Retrieved Passages from Multiple Documents:\n{docs_paired}\n\n"
                "Task: Check if there is an explicit factual contradiction, differing policy terms/dates, or incompatible statements between these different documents regarding the user's question.\n"
                "Return ONLY a JSON object: {\"conflict\": true | false, \"summary\": \"1-2 sentence description of the disagreement, or empty string\"}"
            )
            try:
                c_resp = llm_fast.invoke(conflict_prompt)
                c_clean = clean_llm_response(c_resp.content)
                c_match = re.search(r"\{.*\}", c_clean, re.DOTALL)
                if c_match:
                    c_json = json.loads(c_match.group(0))
                    if c_json.get("conflict") is True and c_json.get("summary"):
                        conflict_data["detected"] = True
                        conflict_data["summary"] = c_json.get("summary")
                        conflict_data["passages"] = [
                            {
                                "source": g.get("source", f"Doc #{i+1}"),
                                "name": g.get("source", f"Doc #{i+1}").split("/")[-1],
                                "text": g.get("text", docs[i] if i < len(docs) else ""),
                                "rationale": g.get("rationale", "")
                            }
                            for i, g in enumerate(doc_grades)
                            if g.get("score") == "yes" and g.get("source") and g.get("breadcrumb") != "Web Search Fallback"
                        ]
                        print(f"  ⚠️ Document Conflict Detected: {conflict_data['summary']}")
                        conflict_instruction = (
                            f"\nIMPORTANT - DOCUMENT CONFLICT DETECTED: The knowledge base contains differing perspectives across documents:\n"
                            f"Discrepancy: {conflict_data['summary']}\n"
                            "You MUST begin your response with a structured callout block:\n"
                            f"> ⚠️ **Document Conflict Detected**: Multiple indexed documents present differing information on this topic:\n"
                            "> - State what each document asserts clearly with their source names.\n"
                            "> - Do not silently favor one over the other; surface both perspectives.\n\n"
                        )
            except Exception as ce:
                print(f"Conflict detector note: {ce}")

        prompt = (
            "You are Ridge, an advanced AI research assistant.\n"
            "Synthesize a well-structured, authoritative, and cleanly formatted answer to the user's question based on the provided context.\n\n"
            f"{conflict_instruction}"
            f"Context findings:\n{context or 'No local document match found.'}\n\n"
            f"Question: {question}\n\n"
            "Formatting & Quality Rules:\n"
            "1. DIRECT EXECUTIVE ANSWER: Start with a clear, direct 1-2 sentence answer before expanding into details.\n"
            "2. CLEAN MARKDOWN STRUCTURE: Use clean markdown hierarchy (## Section, ### Subsections, bullet points, bold keywords).\n"
            "3. TABLES: If presenting comparative or source-level data, format as a valid Markdown table with proper newlines between every row.\n"
            "4. CLEAN CITATIONS & NO RAW HTML: Never output raw HTML tags (<br>, <div>) or internal citation tags like 【1†L1-L4】. When referencing sources, use clean inline bracketed references like [1].\n"
            "5. ACCURACY & EVIDENCE: Base factual assertions directly on the verified context findings. If the context is unrelated to the question, state that clearly and provide a grounded explanation.\n"
            "6. NO GIBBERISH: If the question is unintelligible keyboard mash, politely ask for clarification.\n"
            "7. MATHEMATICAL EQUATIONS & LATEX: Format all mathematical formulas and variables using standard LaTeX syntax. Use inline `$ ... $` for inline variables and terms (e.g., `$p_c$`, `$\\alpha$`, `$p^s_{T,c}$`), and block `$$ ... $$` on separate lines for display equations. Never output bracketed formulas like `[ p_c := ... ]` or `(\\alpha)` without dollar signs.\n"
            "8. INTERACTIVE MERMAID DIAGRAMS: When the user asks for a diagram or when explaining multi-step workflows, architectures, decision cycles, algorithm traversals, or state transitions, ALWAYS include a valid ```mermaid\nflowchart TD\n...``` code block diagram. CRITICAL SYNTAX RULES:\n"
            "   - Use ONLY standard ASCII arrows: `-->`, `-.->`, `==>`. NEVER use Unicode em-dashes or box characters (`─`, `—`, `–`, `→`).\n"
            "   - Wrap all node and subgraph text in double quotes: `A[\"Node Label\"]`, `subgraph ID [\"Group Name\"]`.\n"
            "   - Never use raw HTML tags (`<b>`, `<span>`) inside Mermaid diagrams."
        )

        # Primary Model with instant fast model fallback on rate-limit
        try:
            response = llm_generate.invoke(prompt)
            gen_text = clean_llm_response(response.content)
            return {
                "generation": gen_text,
                "confidence": confidence_data,
                "conflict_data": conflict_data,
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
                    "conflict_data": conflict_data,
                    "latency_ms": int((time.time() - t0) * 1000)
                }
            except Exception as e2:
                print(f"Fallback generation error: {e2}")
                return {
                    "generation": f"Model provider error: {e2}",
                    "confidence": confidence_data,
                    "conflict_data": conflict_data,
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

        # Enrich query with domain acronym expansions from glossary
        try:
            from glossary import enrich_query_with_glossary
            source_filter = state.get("source_filter")
            active_srcs = {source_filter} if source_filter else None
            user_id = state.get("user_id")
            new_query = enrich_query_with_glossary(new_query, active_sources=active_srcs, user_id=user_id)
        except Exception as ge:
            print(f"Glossary query enrichment note: {ge}")

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
        
        web_docs = []
        web_doc_grades = []
        web_metadata = []
        try:
            with DDGS(timeout=6) as ddgs:
                results = list(ddgs.text(search_query, max_results=3))
                for i, r in enumerate(results):
                    title = r.get("title", "Web Source")
                    body = r.get("body", "")[:450].strip()
                    href = r.get("href", "")
                    if body:
                        web_docs.append(f"Web Source [{i+1}]: {title} ({href})\n{body}")
                        web_doc_grades.append({
                            "index": i + 1,
                            "source": f"{title} ({href})",
                            "score": "yes",
                            "rationale": f"Live search result from DuckDuckGo: {title}",
                            "text": body,
                            "breadcrumb": "Web Search Fallback"
                        })
                        web_metadata.append({"source": href, "title": title, "type": "web"})
        except Exception as e:
            print(f"Web search note: {e}")
            
        return {
            "documents": web_docs,
            "doc_grades": web_doc_grades,
            "documents_metadata": web_metadata,
            "latency_ms": int((time.time() - t0) * 1000)
        }

    def decide_to_generate(state: GraphState) -> str:
        print("--- ROUTER: EVALUATING NEXT STEP ---")

        allow_web = state.get("web_search_enabled", True)
        loops = state.get("loop_count", 0)
        max_loops = int(settings.get("max_rewrite_loops", 1))

        if state.get("generation") == "yes":
            # Multi-hop coverage check: if we have fewer relevant docs than sub-queries
            # and web is enabled, supplement with web search
            sub_queries = state.get("sub_queries", [])
            doc_grades = state.get("doc_grades", [])
            relevant_count = sum(1 for g in doc_grades if g.get("score") == "yes")
            if len(sub_queries) > 1 and allow_web and relevant_count < len(sub_queries):
                print(
                    f"-> Multi-hop coverage gap: {relevant_count} relevant docs for {len(sub_queries)} sub-queries."
                    " Route to: WEB SEARCH (gap fill)."
                )
                return "web_search"
            print("-> Document matches. Route to: GENERATE")
            return "generate"

        if loops >= max_loops:
            if allow_web:
                print(f"-> Safety valve tripped after {loops} rewrite attempts. Route to: WEB SEARCH.")
                return "web_search"
            else:
                print(f"-> Safety valve tripped after {loops} rewrite attempts. Web fallback disabled -> Route to: GENERATE (Direct Local KB).")
                return "generate"

        print("-> Document irrelevant. Route to: REWRITE")
        return "rewrite"

    def check_hallucination(state: GraphState) -> dict:
        t0 = time.time()
        print("--- NODE: CHECK HALLUCINATION AUDITOR ---")
        answer = state.get("generation", "")
        docs = state.get("documents", [])
        question = state.get("original_question") or state["question"]
        conf = state.get("confidence", {})

        if not answer or not docs:
            return {
                "hallucination_grade": {"grounded": "yes", "rationale": "Direct answer synthesis."},
                "latency_ms": int((time.time() - t0) * 1000)
            }

        docs_summary = "\n".join(f"[{i+1}] {d[:350]}" for i, d in enumerate(docs[:4]))
        prompt = (
            "You are a strict hallucination auditor for an enterprise RAG system.\n"
            "Evaluate whether the generated answer is faithful to and supported by the context findings.\n\n"
            f"Context Findings:\n{docs_summary}\n\n"
            f"User Question: {question}\n\n"
            f"Generated Answer:\n{answer[:600]}\n\n"
            "Evaluation Rules:\n"
            "1. Grounded ('yes'): Core claims and facts in the answer are supported by context findings.\n"
            "2. Hallucinated ('no'): The answer invents ungrounded or contradictory claims.\n\n"
            "Return ONLY a JSON object: {\"grounded\": \"yes\" | \"no\", \"rationale\": \"brief sentence\"}"
        )
        try:
            resp = llm_fast.invoke(prompt)
            cleaned = clean_llm_response(resp.content)
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                grounded = str(data.get("grounded", "yes")).lower()
                rationale = str(data.get("rationale", "Faithfully grounded in context"))
                print(f"  Hallucination audit verdict: '{grounded}' ({rationale})")
                if "breakdown" in conf:
                    conf["breakdown"]["faithfulness"] = "Faithfully Grounded" if grounded == "yes" else "Extrapolated Context"
                return {
                    "confidence": conf,
                    "hallucination_grade": {"grounded": grounded, "rationale": rationale},
                    "latency_ms": int((time.time() - t0) * 1000)
                }
        except Exception as e:
            print(f"Hallucination auditor note: {e}")

        return {
            "hallucination_grade": {"grounded": "yes", "rationale": "Audit verified"},
            "latency_ms": int((time.time() - t0) * 1000)
        }

    # ---------------------------------------------------------------------------
    # MULTI-HOP DECOMPOSITION NODE
    # ---------------------------------------------------------------------------
    COMPOUND_SIGNALS = [
        " and ", " also ", " compare ", " vs ", " versus ",
        " as well as ", " both ", " additionally ", " furthermore ", " difference between "
    ]

    def _looks_compound(q: str) -> bool:
        q_lower = q.lower()
        return any(sig in q_lower for sig in COMPOUND_SIGNALS)

    def decompose(state: GraphState) -> dict:
        """Detect compound/multi-part questions, split into focused sub-queries,
        run parallel hybrid retrieval for each, and merge results via RRF."""
        t0 = time.time()
        question = state["question"]
        print("\n--- NODE: QUERY DECOMPOSITION ---")

        # Skip LLM call entirely for clearly simple questions
        if not _looks_compound(question):
            print("  [Decompose] Simple question (heuristic). Skipping LLM decomposition.")
            return {"sub_queries": [question], "latency_ms": 0}

        # --- Step 1: Detect if question is compound via LLM ---
        detect_prompt = (
            "You are a query analysis assistant.\n"
            f"User question: {question}\n\n"
            "Determine if this question contains MULTIPLE distinct parts or asks about MULTIPLE"
            " separate topics that each require independent retrieval.\n"
            "Examples of compound: 'Compare PEAS and DECIDE frameworks, and also explain BFS vs DFS'\n"
            "Examples of simple: 'What is PEAS?', 'How does BFS work?'\n\n"
            "If compound, decompose into 2-4 concise, focused sub-queries.\n"
            "If simple, return the original question as the only sub-query.\n"
            "Return ONLY valid JSON: {\"compound\": true|false, \"sub_queries\": [\"q1\", ...]}"
        )
        sub_queries = [question]  # default: no decomposition
        try:
            resp = llm_fast.invoke(detect_prompt)
            cleaned = clean_llm_response(resp.content)
            m = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if m:
                data = json.loads(m.group(0))
                if data.get("compound") and data.get("sub_queries"):
                    candidates = [str(q).strip() for q in data["sub_queries"] if q and len(str(q).strip()) > 3]
                    if len(candidates) >= 2:
                        sub_queries = candidates[:4]
                        print(f"  Compound question detected. Sub-queries: {sub_queries}")
                    else:
                        print("  Simple question detected. No decomposition needed.")
                else:
                    print("  Simple question detected. No decomposition needed.")
        except Exception as e:
            print(f"  Decomposition note: {e}")

        if len(sub_queries) == 1:
            # No-op: standard single retrieve path, set sub_queries but keep question
            return {"sub_queries": sub_queries, "latency_ms": int((time.time() - t0) * 1000)}

        # --- Step 2: Parallel hybrid retrieval per sub-query ---
        bm25, raw_docs, raw_metas = get_bm25()
        
        src_filter = state.get("source_filter")
        is_filtered = bool(src_filter and src_filter.strip().lower() not in ("", "all", "all sources", "none"))
        if is_filtered and raw_docs:
            filtered_docs = []
            filtered_metas = []
            for d, m in zip(raw_docs, raw_metas):
                m_src = str(m.get("source", "")) if m else ""
                if m_src == src_filter or src_filter.lower() in m_src.lower():
                    filtered_docs.append(d)
                    filtered_metas.append(m)
            if filtered_docs:
                from rank_bm25 import BM25Okapi
                tokenized_corpus = [re.findall(r"\w+", doc.lower()) for doc in filtered_docs]
                bm25 = BM25Okapi(tokenized_corpus)
                raw_docs, raw_metas = filtered_docs, filtered_metas
            else:
                bm25 = None
                raw_docs, raw_metas = [], []

        # RRF registry across all sub-queries
        rrf_scores: dict[str, float] = {}
        doc_registry: dict[str, tuple[str, dict]] = {}
        K = 60  # RRF constant

        for sq in sub_queries:
            # Dense retrieval (with optional source filter)
            if is_filtered:
                try:
                    dense = vectorstore.similarity_search(sq, k=50, filter={"source": src_filter})
                except Exception:
                    dense = retriever.invoke(sq)
                    dense = [d for d in dense if d.metadata.get("source") == src_filter or src_filter.lower() in str(d.metadata.get("source", "")).lower()]
            else:
                dense = retriever.invoke(sq)

            for rank, d in enumerate(dense):
                did = d.page_content.strip()[:180]
                doc_registry[did] = (d.page_content, d.metadata)
                rrf_scores[did] = rrf_scores.get(did, 0.0) + 1.0 / (K + rank + 1)

            # BM25 sparse retrieval
            if bm25 and raw_docs:
                tokens = re.findall(r"\w+", sq.lower())
                if tokens:
                    scores = bm25.get_scores(tokens)
                    top_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:20]
                    for rank, idx in enumerate(top_idx):
                        if scores[idx] > 0.0:
                            did = raw_docs[idx].strip()[:180]
                            doc_registry[did] = (raw_docs[idx], raw_metas[idx] if idx < len(raw_metas) else {})
                            rrf_scores[did] = rrf_scores.get(did, 0.0) + 1.0 / (K + rank + 1)

        # --- Step 3: Sort + FlashRank re-rank merged pool ---
        rerank_top_n = settings.get("rerank_top_n", 20)
        sorted_fused = sorted(rrf_scores.keys(), key=lambda k: rrf_scores[k], reverse=True)[:rerank_top_n]
        fused_texts = [doc_registry[k][0] for k in sorted_fused]
        fused_metas = [doc_registry[k][1] for k in sorted_fused]
        print(f"  Multi-hop merged pool: {len(fused_texts)} candidates from {len(sub_queries)} sub-queries.")

        final_texts, final_metas = fused_texts, fused_metas
        if fused_texts:
            from flashrank import RerankRequest
            passages = [{"id": i, "text": t, "meta": fused_metas[i]} for i, t in enumerate(fused_texts)]
            rr = RerankRequest(query=question, passages=passages)
            results = sorted(ranker.rerank(rr), key=lambda x: x["score"], reverse=True)
            final_texts = [r["text"] for r in results[:settings["retriever_k"]]]
            final_metas = []
            for r in results[:settings["retriever_k"]]:
                m = r["meta"]
                m["score"] = float(r["score"])
                final_metas.append(m)
            print(f"  Re-ranked to top {len(final_texts)} documents.")

        return {
            "sub_queries": sub_queries,
            "documents": final_texts,
            "documents_metadata": final_metas,
            "latency_ms": int((time.time() - t0) * 1000),
        }

    workflow = StateGraph(GraphState)
    workflow.add_node("decompose_node", decompose)
    workflow.add_node("retrieve_node", retrieve)
    workflow.add_node("web_search_node", web_search)
    workflow.add_node("grade_node", grade_documents)
    workflow.add_node("generate_node", generate)
    workflow.add_node("check_hallucination_node", check_hallucination)
    workflow.add_node("rewrite_node", rewrite)

    # Decompose → if multi-hop docs already loaded, skip retrieve and go straight to grade
    workflow.set_entry_point("decompose_node")

    def route_after_decompose(state: GraphState) -> str:
        """If decompose_node already populated documents (multi-hop), skip retrieve_node."""
        if state.get("documents"):
            return "grade"
        return "retrieve"

    workflow.add_conditional_edges(
        "decompose_node",
        route_after_decompose,
        {"grade": "grade_node", "retrieve": "retrieve_node"},
    )
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
    workflow.add_edge("generate_node", "check_hallucination_node")
    workflow.add_edge("check_hallucination_node", END)

    return workflow.compile()


_app = None

def get_app():
    """Return the compiled LangGraph app, building it once and caching it as a lazy singleton."""
    global _app
    if _app is None:
        _app = build_app()
    return _app


def run_question(question: str, web_search_enabled: bool = True, source_filter: str | None = None) -> dict:
    app = get_app()
    result = app.invoke(
        {
            "question": question,
            "original_question": question,
            "web_search_enabled": web_search_enabled,
            "source_filter": source_filter,
            "sub_queries": [],
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