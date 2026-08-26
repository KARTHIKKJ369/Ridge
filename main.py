"""
Ridge: Corrective RAG (CRAG) State Machine Architecture
======================================================
This module implements the core LangGraph state graph and document ingestion for Corrective RAG:
  1. Decompose: Multi-hop query detection and parallel hybrid retrieval.
  2. Retrieve: MMR vector search via PostgreSQL pgvector + TSVector BM25.
  3. Re-rank: CrossEncoder / FlashRank re-ranking with Small-to-Big parent expansion.
  4. Grade: Groq LLM hallucination and relevance evaluator.
  5. Rewrite / Web Search: Adaptive query reformulation and DuckDuckGo fallback.
  6. Generate: Grounded synthesis across all verified passages with NotebookLM citations.
"""

import os
import sys
import time
import uuid
import asyncio
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()

# VM & CPU Optimization: Set PyTorch execution threads to match VM cores
try:
    import torch
    num_threads = int(os.getenv("TORCH_THREADS", "2"))
    torch.set_num_threads(num_threads)
    torch.set_num_interop_threads(num_threads)
except Exception:
    pass

DEFAULT_QUESTION = "What is task decomposition in LLM agents?"

# Re-export state and graph schemas from modular app.graph package
from app.graph.state import GraphState, DocGrade, BatchGrades
from app.graph.prompts import clean_llm_response, extract_batch_grades
from app.graph.builder import build_app, get_app, get_default_settings
from app.graph.observability import get_langfuse_handler


def get_settings() -> dict:
    return get_default_settings()


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


def generate_suggestions(text: str):
    import json
    import re
    from app.graph.llm_factory import create_llm
    
    try:
        llm = create_llm(
            temperature=0.6,
            max_tokens=256,
            is_fast_model=True,
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


async def aingest_document(
    text_or_url: str,
    original_filename: str | None = None,
    user_id: str = "default",
    tenant_id: str | None = None,
    is_shared: bool = False,
) -> dict:
    """
    Asynchronous document ingestion engine: parses documents with Document Intelligence AST,
    computes embeddings, caches parent chunks in memory, and persists to PostgreSQL pgvector
    cleanly on the current event loop without cross-thread connection sharing.
    """
    import os
    import uuid
    from rag_ingest import ingest_document_structure_aware
    from parent_store import make_parent_id, save_parents

    print(f"\n=== INGESTING ===\nUser: {user_id} | Tenant: {tenant_id} | Shared: {is_shared}\nInput: {text_or_url[:100]}...")

    is_url = text_or_url.startswith("http://") or text_or_url.startswith("https://")

    # Structure-Aware Parsing, AST Generation & Semantic Chunking
    doc_ast, parent_docs, child_docs, lineage_info = ingest_document_structure_aware(
        source=text_or_url,
        original_filename=original_filename,
        user_id=user_id,
        target_chunk_size=1200,
        chunk_overlap=150,
        child_chunk_size=350,
        child_overlap=50,
    )

    print(f"  Document Intelligence: {lineage_info['parser_name']} extracted {len(parent_docs)} parents, {len(child_docs)} children, {lineage_info['table_count']} tables, {lineage_info['figure_count']} figures.")

    parent_records = []
    for parent_doc in parent_docs:
        source = parent_doc.metadata.get("source", original_filename or "unknown")
        pid = make_parent_id(parent_doc.page_content, source)
        parent_records.append({
            "id": pid,
            "text": parent_doc.page_content,
            "metadata": parent_doc.metadata,
        })

    try:
        save_parents(parent_records)
    except Exception as ps_err:
        print(f"  ParentStore note: {ps_err}")

    table_records = []
    for tbl in doc_ast.all_tables():
        table_records.append({
            "page_number": tbl.page_number,
            "caption": tbl.caption,
            "section_path": tbl.section_path,
            "headers": tbl.headers,
            "rows": tbl.rows,
            "markdown": tbl.generate_markdown(),
            "search_text": tbl.get_search_text(),
            "metadata": tbl.metadata,
        })

    figure_records = []
    for fig in doc_ast.all_figures():
        figure_records.append({
            "page_number": fig.page_number,
            "caption": fig.caption,
            "section_path": fig.section_path,
            "image_path": fig.image_path,
            "ocr_text": fig.ocr_text,
            "description": fig.description,
            "nearby_text": fig.nearby_text,
            "metadata": fig.metadata,
        })

    docs_to_index = child_docs if child_docs else parent_docs

    # PostgreSQL & pgvector persistence
    from app.db.database import is_postgres_configured, get_db_session
    from app.db.repositories import document_repo, glossary_repo, tenant_repo

    embedder = get_embeddings()
    if is_postgres_configured():
        try:
            embeddings_list = embedder.embed_documents([d.page_content for d in docs_to_index])

            async with get_db_session() as session:
                t_uuid = uuid.UUID(tenant_id) if tenant_id else None
                kb_id = await tenant_repo.get_or_create_tenant_kb(session, t_uuid) if t_uuid else None

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
                    is_shared=is_shared,
                    knowledge_base_id=kb_id,
                    ingestion_run_info=lineage_info,
                    table_records=table_records,
                    figure_records=figure_records,
                )
            print("  [PostgreSQL] Successfully saved document, chunks, structured tables/figures, and pgvector embeddings.")
        except Exception as pg_ingest_err:
            print(f"  [PostgreSQL] Ingestion error: {pg_ingest_err}")
            raise pg_ingest_err

    # Extract & Index domain acronyms into glossary
    try:
        from glossary import index_text_glossary, extract_acronyms_from_text
        full_text = " ".join(d.page_content for d in parent_docs)
        source_name = original_filename or text_or_url
        index_text_glossary(full_text, source_name, user_id=user_id)

        if is_postgres_configured():
            extracted = extract_acronyms_from_text(full_text, source_name)
            if extracted:
                async with get_db_session() as session:
                    await glossary_repo.index_glossary_terms(
                        session=session,
                        terms_map=extracted,
                        source_name=source_name,
                        user_id=user_id,
                    )
    except Exception as ge:
        print(f"Glossary indexing note: {ge}")

    # Generate suggestions in a background thread
    if parent_docs:
        try:
            import threading
            context_text = " ".join(d.page_content for d in parent_docs[:3])[:1500]
            threading.Thread(target=generate_suggestions, args=(context_text,), daemon=True).start()
        except Exception as e:
            print(f"Error launching background suggestions: {e}")

    return {"status": "success", "chunks_added": len(docs_to_index)}


def ingest_document(
    text_or_url: str,
    original_filename: str | None = None,
    user_id: str = "default",
    tenant_id: str | None = None,
    is_shared: bool = False,
) -> dict:
    """
    Synchronous wrapper for aingest_document, safe for CLI scripts and synchronous runners.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(
                asyncio.run,
                aingest_document(
                    text_or_url=text_or_url,
                    original_filename=original_filename,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    is_shared=is_shared,
                )
            ).result()
    else:
        return asyncio.run(
            aingest_document(
                text_or_url=text_or_url,
                original_filename=original_filename,
                user_id=user_id,
                tenant_id=tenant_id,
                is_shared=is_shared,
            )
        )


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