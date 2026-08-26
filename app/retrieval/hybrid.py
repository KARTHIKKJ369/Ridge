"""
Unified Hybrid Retrieval Orchestrator
=====================================
Selects and executes the configured retrieval backend (pgvector, chroma, or dual A/B test),
applies CrossEncoder / FlashRank cross-encoder re-ranking, and performs Small-to-Big parent expansion.
"""
import os
import time
import uuid
import logging
from typing import Optional, List, Tuple

from app.db.database import is_postgres_configured
from app.retrieval.interface import BaseRetriever, RetrievalCandidate
from app.retrieval.pgvector_retriever import PgvectorRetriever

logger = logging.getLogger(__name__)


class UnifiedRetriever(BaseRetriever):
    def __init__(self, backend: Optional[str] = None):
        self.backend = backend or os.getenv("RETRIEVAL_BACKEND", "pgvector").lower().strip()
        self._pg_retriever = PgvectorRetriever()
        self._flashrank_ranker = None
        self._cross_encoder = None
        self.reranker_type = os.getenv("RERANKER_BACKEND", "flashrank").lower().strip()

    def _get_flashrank_ranker(self):
        if self._flashrank_ranker is None:
            from flashrank import Ranker
            model_name = os.getenv("RERANK_MODEL", "ms-marco-MiniLM-L-12-v2")
            self._flashrank_ranker = Ranker(model_name=model_name, cache_dir="./.flashrank_cache")
        return self._flashrank_ranker

    def _get_cross_encoder(self):
        if self._cross_encoder is None:
            try:
                from sentence_transformers import CrossEncoder
                ce_model = os.getenv("CROSS_ENCODER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
                self._cross_encoder = CrossEncoder(ce_model)
                logger.info(f"✓ Initialized CrossEncoder '{ce_model}'")
            except Exception as e:
                logger.warning(f"Note loading CrossEncoder, falling back to FlashRank: {e}")
                self._cross_encoder = None
        return self._cross_encoder

    async def retrieve(
        self,
        query: str,
        user_id: Optional[str] = None,
        tenant_id: Optional[uuid.UUID] = None,
        source_filter: Optional[str] = None,
        k: int = 50,
    ) -> list[RetrievalCandidate]:
        """
        Executes query-aware routed hybrid vector + full-text search with SQL Reciprocal Rank Fusion.
        """
        from app.retrieval.router import get_query_router
        router = get_query_router()
        plan = router.route_query(query)

        effective_k = max(k, plan.top_k_candidates)

        candidates = await self._pg_retriever.retrieve(
            query=query,
            user_id=user_id,
            tenant_id=tenant_id,
            source_filter=source_filter,
            k=effective_k,
        )

        # Tag candidates with routing metadata
        for c in candidates:
            c.metadata["query_archetype"] = plan.archetype.value

        return candidates

    def rerank_and_expand(
        self,
        query: str,
        candidates: list[RetrievalCandidate],
        top_k: int = 6,
        rerank_top_n: int = 20,
    ) -> tuple[list[str], list[dict], int]:
        """
        Applies CrossEncoder / FlashRank cross-encoder reranking and Small-to-Big parent expansion.
        Returns (final_texts, final_metas, expanded_count).
        """
        if not candidates:
            return [], [], 0

        # Take top N for cross-encoder reranking
        fused = candidates[:rerank_top_n]
        ranked_passages = []

        if self.reranker_type == "cross_encoder":
            ce = self._get_cross_encoder()
            if ce is not None:
                try:
                    pairs = [[query, c.text] for c in fused]
                    scores = ce.predict(pairs)
                    scored = []
                    for i, c in enumerate(fused):
                        score_val = float(scores[i])
                        m = dict(c.metadata or {})
                        m["score"] = score_val
                        scored.append({"text": c.text, "meta": m, "score": score_val})
                    ranked_passages = sorted(scored, key=lambda x: x["score"], reverse=True)
                except Exception as ce_err:
                    logger.warning(f"CrossEncoder prediction note: {ce_err}, falling back to FlashRank")
                    ranked_passages = []

        if not ranked_passages:
            # FlashRank fallback
            passages = [
                {"id": i, "text": c.text, "meta": c.metadata}
                for i, c in enumerate(fused)
            ]
            from flashrank import RerankRequest
            ranker = self._get_flashrank_ranker()
            rerank_req = RerankRequest(query=query, passages=passages)
            results = sorted(ranker.rerank(rerank_req), key=lambda x: x["score"], reverse=True)

            for r in results:
                m = dict(r.get("meta", {}) or {})
                m["score"] = float(r["score"])
                ranked_passages.append({
                    "text": r["text"],
                    "meta": m,
                    "score": float(r["score"]),
                })

        # Bounded Parent + Neighbor Expansion & Context Packing
        from app.retrieval.context_packer import get_context_packer
        packer = get_context_packer()
        return packer.pack_context(ranked_passages, top_k=top_k)
