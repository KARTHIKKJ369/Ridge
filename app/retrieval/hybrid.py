"""
Unified Hybrid Retrieval Orchestrator
=====================================
Selects and executes the configured retrieval backend (pgvector, chroma, or dual A/B test),
applies FlashRank cross-encoder re-ranking, and performs Small-to-Big parent expansion.
"""
import os
import time
import logging
from typing import Optional

from app.db.database import is_postgres_configured
from app.retrieval.interface import BaseRetriever, RetrievalCandidate
from app.retrieval.pgvector_retriever import PgvectorRetriever

logger = logging.getLogger(__name__)


class UnifiedRetriever(BaseRetriever):
    def __init__(self, backend: Optional[str] = None):
        self.backend = backend or os.getenv("RETRIEVAL_BACKEND", "pgvector").lower().strip()
        self._pg_retriever = PgvectorRetriever()
        self._ranker = None

    def _get_ranker(self):
        if self._ranker is None:
            from flashrank import Ranker
            model_name = os.getenv("RERANK_MODEL", "ms-marco-MiniLM-L-12-v2")
            self._ranker = Ranker(model_name=model_name, cache_dir="./.flashrank_cache")
        return self._ranker

    async def retrieve(
        self,
        query: str,
        user_id: Optional[str] = None,
        source_filter: Optional[str] = None,
        k: int = 50,
    ) -> list[RetrievalCandidate]:
        """
        Executes hybrid vector + full-text search with SQL Reciprocal Rank Fusion.
        """
        return await self._pg_retriever.retrieve(
            query=query,
            user_id=user_id,
            source_filter=source_filter,
            k=k,
        )


    def rerank_and_expand(
        self,
        query: str,
        candidates: list[RetrievalCandidate],
        top_k: int = 6,
        rerank_top_n: int = 20,
    ) -> tuple[list[str], list[dict], int]:
        """
        Applies FlashRank cross-encoder reranking and Small-to-Big parent expansion.
        Returns (final_texts, final_metas, expanded_count).
        """
        if not candidates:
            return [], [], 0

        # Take top N for cross-encoder
        fused = candidates[:rerank_top_n]
        passages = [
            {"id": i, "text": c.text, "meta": c.metadata}
            for i, c in enumerate(fused)
        ]

        from flashrank import RerankRequest
        ranker = self._get_ranker()
        rerank_req = RerankRequest(query=query, passages=passages)
        results = sorted(ranker.rerank(rerank_req), key=lambda x: x["score"], reverse=True)

        reranked_texts = []
        reranked_metas = []

        for r in results[:top_k]:
            reranked_texts.append(r["text"])
            m = dict(r.get("meta", {}) or {})
            m["score"] = float(r["score"])
            reranked_metas.append(m)

        # Small-to-Big Expansion: expand child chunks to their parents
        from parent_store import expand_documents
        exp_texts, exp_metas = expand_documents(reranked_texts, reranked_metas)
        expanded_count = sum(1 for m in exp_metas if m.get("expanded_from_child"))

        return exp_texts, exp_metas, expanded_count
