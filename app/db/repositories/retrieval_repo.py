"""
Retrieval Observability Repository
==================================
Logs and queries retrieval runs, RRF scores, rerank scores, and latencies.
"""
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.retrieval import RetrievalRun, RetrievalResult


async def log_retrieval_run(
    session: AsyncSession,
    query: str,
    rewritten_query: str,
    retrieval_strategy: str,
    cache_hit: bool,
    latency_ms: int,
    results_list: list[dict],
    conversation_id: Optional[str] = None,
    message_id: Optional[uuid.UUID] = None,
) -> RetrievalRun:
    conv_uuid = uuid.UUID(conversation_id) if conversation_id else None

    run = RetrievalRun(
        id=uuid.uuid4(),
        conversation_id=conv_uuid,
        message_id=message_id,
        query=query,
        rewritten_query=rewritten_query,
        retrieval_strategy=retrieval_strategy,
        cache_hit=cache_hit,
        latency_ms=latency_ms,
    )
    session.add(run)
    await session.flush()

    for r in results_list:
        chunk_uuid = None
        if r.get("chunk_id"):
            try:
                chunk_uuid = uuid.UUID(r["chunk_id"])
            except Exception:
                pass

        result_row = RetrievalResult(
            id=uuid.uuid4(),
            retrieval_run_id=run.id,
            chunk_id=chunk_uuid,
            dense_score=float(r.get("dense_score", 0.0)),
            sparse_score=float(r.get("sparse_score", 0.0)),
            rrf_score=float(r.get("rrf_score", 0.0)),
            rerank_score=float(r.get("rerank_score", 0.0)),
            final_rank=int(r.get("final_rank", 0)),
            selected=bool(r.get("selected", False)),
        )
        session.add(result_row)

    await session.flush()
    return run
