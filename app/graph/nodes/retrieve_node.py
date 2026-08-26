"""
Ridge: Retrieval Node
=====================
Executes hybrid vector + full-text search, cross-encoder reranking,
and Small-to-Big parent chunk expansion.
"""
import time
import uuid
from typing import Callable
from app.graph.state import GraphState
from app.retrieval.interface import BaseRetriever


def make_retrieve_node(
    retriever_engine: BaseRetriever,
    settings: dict,
) -> Callable[[GraphState], dict]:

    async def retrieve_node(state: GraphState) -> dict:
        t0 = time.time()
        q = state["question"]
        src_filter = state.get("source_filter")
        user_id = state.get("user_id")
        tenant_id = state.get("tenant_id")
        t_uuid = uuid.UUID(tenant_id) if tenant_id else None

        print(f"\n--- NODE: UNIFIED HYBRID RETRIEVE (Backend: {getattr(retriever_engine, 'backend', 'pgvector')}) ---")
        if src_filter:
            print(f"  [Source Scope Filter Active]: '{src_filter}'")
        if user_id:
            print(f"  [User Scope Filter Active]: '{user_id}'")
        if tenant_id:
            print(f"  [Tenant Scope Filter Active]: '{tenant_id}'")

        try:
            candidates = await retriever_engine.retrieve(
                query=q, user_id=user_id, tenant_id=t_uuid, source_filter=src_filter, k=settings.get("retriever_fetch_k", 50)
            )
        except Exception as retrieve_err:
            print(f"  [Retrieve Node] Warning: retrieval query failed ({retrieve_err}), proceeding with empty results.")
            candidates = []

        try:
            final_texts, final_metas, expanded_count = retriever_engine.rerank_and_expand(
                query=q,
                candidates=candidates,
                top_k=settings.get("retriever_k", 6),
                rerank_top_n=settings.get("rerank_top_n", 20),
            )
        except Exception as rerank_err:
            print(f"  [Rerank Node] Warning: rerank/expand failed ({rerank_err})")
            final_texts, final_metas, expanded_count = [], [], 0

        return {
            "documents": final_texts,
            "documents_metadata": final_metas,
            "expanded_count": expanded_count,
            "latency_ms": int((time.time() - t0) * 1000),
        }

    return retrieve_node
