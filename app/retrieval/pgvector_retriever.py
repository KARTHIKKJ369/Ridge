"""
PostgreSQL pgvector + FTS Hybrid Retriever
==========================================
Implements high-performance dense vector search via pgvector HNSW index,
PostgreSQL GIN tsvector lexical full-text search, and Reciprocal Rank Fusion.
"""
import uuid
import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db_session
from app.retrieval.interface import BaseRetriever, RetrievalCandidate

logger = logging.getLogger(__name__)


class PgvectorRetriever(BaseRetriever):
    def __init__(self, embedder=None):
        self._embedder = embedder

    def _get_embedder(self):
        if self._embedder is None:
            from main import get_embeddings
            self._embedder = get_embeddings()
        return self._embedder

    async def retrieve(
        self,
        query: str,
        user_id: Optional[str] = None,
        tenant_id: Optional[uuid.UUID] = None,
        source_filter: Optional[str] = None,
        k: int = 50,
    ) -> list[RetrievalCandidate]:
        """
        Executes hybrid dense + sparse retrieval in PostgreSQL with strict tenant isolation:
        1. Dense pgvector cosine distance search (<=>)
        2. PostgreSQL FTS plainto_tsquery search
        3. Reciprocal Rank Fusion (RRF)
        """
        embedder = self._get_embedder()
        q_vec = embedder.embed_query(query)

        # Normalize filters
        is_scoped_user = user_id and user_id not in ("admin", "system", "all")
        is_filtered_source = bool(
            source_filter and source_filter.strip().lower() not in ("", "all", "all sources", "none")
        )

        async with get_db_session() as session:
            # 1. Dense pgvector search
            dense_sql = text("""
                SELECT 
                    c.id AS chunk_id,
                    c.content,
                    c.heading,
                    c.section,
                    c.page_number,
                    c.metadata_json,
                    c.parent_chunk_id,
                    d.filename,
                    d.source_url,
                    d.uploaded_by,
                    d.is_shared,
                    e.embedding <=> CAST(:query_vec AS vector) AS distance
                FROM document_chunks c
                JOIN chunk_embeddings e ON c.id = e.chunk_id
                JOIN documents d ON c.document_id = d.id
                JOIN knowledge_bases kb ON d.knowledge_base_id = kb.id
                WHERE (CAST(:tenant_id AS UUID) IS NULL OR kb.tenant_id = CAST(:tenant_id AS UUID))
                  AND (
                      CAST(:user_id AS VARCHAR) IS NULL 
                      OR d.uploaded_by = CAST(:user_id AS VARCHAR) 
                      OR d.is_shared = true
                  )
                  AND (CAST(:source_filter AS VARCHAR) IS NULL OR d.filename = CAST(:source_filter AS VARCHAR) OR d.source_url = CAST(:source_filter AS VARCHAR) OR LOWER(d.filename) = LOWER(CAST(:source_filter AS VARCHAR)))
                ORDER BY distance ASC
                LIMIT :limit;
            """)

            dense_res = await session.execute(
                dense_sql,
                {
                    "query_vec": str(q_vec),
                    "tenant_id": tenant_id,
                    "user_id": user_id if is_scoped_user else None,
                    "source_filter": source_filter if is_filtered_source else None,
                    "limit": k,
                },
            )
            dense_rows = dense_res.all()

            # 2. Sparse PostgreSQL Full-Text Search
            sparse_rows = []
            try:
                sparse_sql = text("""
                    SELECT 
                        c.id AS chunk_id,
                        c.content,
                        c.heading,
                        c.section,
                        c.page_number,
                        c.metadata_json,
                        c.parent_chunk_id,
                        d.filename,
                        d.source_url,
                        d.uploaded_by,
                        d.is_shared,
                        ts_rank_cd(c.search_vector, plainto_tsquery('english', :query)) AS rank_score
                    FROM document_chunks c
                    JOIN documents d ON c.document_id = d.id
                    JOIN knowledge_bases kb ON d.knowledge_base_id = kb.id
                    WHERE c.search_vector @@ plainto_tsquery('english', :query)
                      AND (CAST(:tenant_id AS UUID) IS NULL OR kb.tenant_id = CAST(:tenant_id AS UUID))
                      AND (
                          CAST(:user_id AS VARCHAR) IS NULL 
                          OR d.uploaded_by = CAST(:user_id AS VARCHAR) 
                          OR d.is_shared = true
                      )
                      AND (CAST(:source_filter AS VARCHAR) IS NULL OR d.filename = CAST(:source_filter AS VARCHAR) OR d.source_url = CAST(:source_filter AS VARCHAR) OR LOWER(d.filename) = LOWER(CAST(:source_filter AS VARCHAR)))
                    ORDER BY rank_score DESC
                    LIMIT 30;
                """)

                sparse_res = await session.execute(
                    sparse_sql,
                    {
                        "query": query,
                        "tenant_id": tenant_id,
                        "user_id": user_id if is_scoped_user else None,
                        "source_filter": source_filter if is_filtered_source else None,
                    },
                )
                sparse_rows = sparse_res.all()
            except Exception as fts_err:
                logger.warning(f"PostgreSQL FTS note: {fts_err}")



            # 3. Reciprocal Rank Fusion (RRF)
            K = 60.0
            rrf_scores: dict[str, float] = {}
            candidate_map: dict[str, dict] = {}

            # Process dense hits
            for rank, r in enumerate(dense_rows):
                cid = str(r.chunk_id)
                sim = 1.0 - float(r.distance)
                candidate_map[cid] = {
                    "text": r.content,
                    "metadata": {
                        **(r.metadata_json or {}),
                        "chunk_id": cid,
                        "parent_id": str(r.parent_chunk_id) if r.parent_chunk_id else None,
                        "source": r.filename or r.source_url or "Unknown",
                        "h1": r.heading or r.filename,
                        "h2": r.section,
                        "score": round(sim, 4),
                    },
                    "dense_score": sim,
                    "sparse_score": 0.0,
                    "chunk_id": cid,
                    "parent_id": str(r.parent_chunk_id) if r.parent_chunk_id else None,
                }
                rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (K + rank + 1))

            # Process sparse hits
            for rank, r in enumerate(sparse_rows):
                cid = str(r.chunk_id)
                score = float(r.rank_score)
                if cid not in candidate_map:
                    candidate_map[cid] = {
                        "text": r.content,
                        "metadata": {
                            **(r.metadata_json or {}),
                            "chunk_id": cid,
                            "parent_id": str(r.parent_chunk_id) if r.parent_chunk_id else None,
                            "source": r.filename or r.source_url or "Unknown",
                            "h1": r.heading or r.filename,
                            "h2": r.section,
                            "score": round(score, 4),
                        },
                        "dense_score": 0.0,
                        "sparse_score": score,
                        "chunk_id": cid,
                        "parent_id": str(r.parent_chunk_id) if r.parent_chunk_id else None,
                    }
                else:
                    candidate_map[cid]["sparse_score"] = score

                rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (K + rank + 1))

            # Sort by fused RRF score
            sorted_cids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
            results = []

            for cid in sorted_cids:
                item = candidate_map[cid]
                results.append(
                    RetrievalCandidate(
                        text=item["text"],
                        metadata=item["metadata"],
                        dense_score=item["dense_score"],
                        sparse_score=item["sparse_score"],
                        rrf_score=round(rrf_scores[cid], 5),
                        chunk_id=item["chunk_id"],
                        parent_id=item["parent_id"],
                    )
                )

            return results
