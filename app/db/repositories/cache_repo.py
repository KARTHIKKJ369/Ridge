"""
Semantic Vector Query Cache Repository with pgvector
====================================================
Performs sub-10ms semantic cache lookups using pgvector cosine distance `<=>`.
"""
import uuid
from typing import Optional
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.query_cache import QueryCache
from app.db.repositories.user_repo import DEFAULT_TENANT_ID

DEFAULT_SIMILARITY_THRESHOLD = 0.96


async def get_cached_response(
    session: AsyncSession,
    query: str,
    query_vector: list[float],
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    source_filter: Optional[str] = None,
    tenant_id: Optional[uuid.UUID] = None,
) -> Optional[dict]:
    """
    Finds the most similar cached query response using pgvector cosine distance.
    Cosine distance d = 1 - cosine_similarity, so similarity = 1 - d >= threshold (d <= 1 - threshold).
    """
    tid = tenant_id or DEFAULT_TENANT_ID
    max_distance = 1.0 - threshold

    # Distance expression: QueryCache.embedding.cosine_distance(query_vector)
    distance_col = QueryCache.embedding.cosine_distance(query_vector).label("distance")

    stmt = (
        select(QueryCache, distance_col)
        .where(
            QueryCache.tenant_id == tid,
            distance_col <= max_distance,
        )
        .order_by(distance_col.asc())
        .limit(1)
    )

    if source_filter:
        stmt = stmt.where(
            (QueryCache.source_filter == source_filter) | (QueryCache.source_filter.is_(None))
        )

    res = await session.execute(stmt)
    row = res.first()
    if not row:
        return None

    entry, distance = row
    similarity = 1.0 - float(distance)

    return {
        "id": str(entry.id),
        "question": entry.question,
        "answer": entry.answer,
        "confidence": entry.confidence,
        "conflict_data": entry.conflict_data,
        "source_filter": entry.source_filter,
        "cache_hit": True,
        "similarity": round(similarity, 4),
    }


async def store_cached_response(
    session: AsyncSession,
    question: str,
    answer: str,
    confidence: dict,
    conflict_data: dict,
    query_vector: list[float],
    source_filter: Optional[str] = None,
    tenant_id: Optional[uuid.UUID] = None,
) -> None:
    """Saves a verified high-confidence response into the PostgreSQL vector cache."""
    if not question or not answer:
        return

    # Don't cache error responses or zero-coverage fallbacks
    if "could not find any relevant information" in answer.lower():
        return

    tid = tenant_id or DEFAULT_TENANT_ID

    stmt = (
        pg_insert(QueryCache)
        .values(
            id=uuid.uuid4(),
            tenant_id=tid,
            question=question.strip(),
            answer=answer.strip(),
            confidence=confidence or {},
            conflict_data=conflict_data or {},
            source_filter=source_filter,
            embedding=query_vector,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_update(
            index_elements=["tenant_id", "question"],
            set_={
                "answer": answer.strip(),
                "confidence": confidence or {},
                "conflict_data": conflict_data or {},
                "source_filter": source_filter,
                "embedding": query_vector,
                "updated_at": datetime.now(timezone.utc),
            },
        )
    )
    await session.execute(stmt)
    await session.flush()
