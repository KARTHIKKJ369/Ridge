"""
System Status, Health, Telemetry & Glossary Endpoints
=====================================================
Provides health checks, query suggestions cache, acronym glossary, and user quota telemetry.
"""
import uuid
import logging
from pathlib import Path
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, or_

from auth import get_current_user, UserProfile
from app.db.database import get_db_session
from app.db.models import Document, DocumentChunk, KnowledgeBase
from app.db.repositories import tenant_repo

logger = logging.getLogger(__name__)
router = APIRouter(tags=["System & Telemetry"])


@router.get("/health")
@router.get("/status")
def health():
    """Returns the service health status."""
    return {"status": "ok", "service": "Ridge RAG"}


@router.get("/suggestions")
async def get_suggestions_endpoint(force: bool = False, user: UserProfile = Depends(get_current_user)):
    """
    Returns suggested queries from the in-memory / persistent cache.
    Does NOT make LLM or DB calls on normal refresh.
    Only re-generates when force=True or during document ingestion.
    """
    from main import get_suggestions_cache
    if not force:
        sugs = get_suggestions_cache()
        if sugs:
            return {"suggestions": sugs, "cached": True}

    try:
        from main import generate_suggestions
        async with get_db_session() as session:
            stmt = select(DocumentChunk.content).limit(4)
            result = await session.execute(stmt)
            chunks = [r[0] for r in result.all() if r[0]]
            if chunks:
                sample_text = " ".join(chunks)[:1500]
                new_sugs = generate_suggestions(sample_text)
                if new_sugs:
                    return {"suggestions": new_sugs, "cached": False}
    except Exception as e:
        logger.warning(f"Could not generate suggestions: {e}")

    cached_fallback = get_suggestions_cache()
    return {"suggestions": cached_fallback, "empty": len(cached_fallback) == 0}


@router.get("/glossary")
async def get_glossary_terms_endpoint(user: UserProfile = Depends(get_current_user)):
    """Returns the list of indexed acronyms and domain entity definitions."""
    try:
        from glossary import get_glossary_for_user, sync_glossary_with_active_sources

        is_admin = user.role == "admin"
        active_sources = set()

        async with get_db_session() as session:
            stmt = select(Document.filename, Document.uploaded_by)
            if not is_admin:
                stmt = stmt.where(or_(Document.uploaded_by == user.id, Document.uploaded_by.is_(None), Document.uploaded_by == "default"))
            res = await session.execute(stmt)
            for row in res.all():
                fn = row[0]
                if fn:
                    active_sources.add(fn)
                    active_sources.add(Path(fn).name)

        if is_admin and active_sources:
            sync_glossary_with_active_sources(active_sources)

        terms_list = get_glossary_for_user(
            user_id=user.id,
            active_sources=active_sources if active_sources else set()
        )
        return {"total": len(terms_list), "glossary": terms_list}
    except Exception as e:
        logger.error(f"Error loading glossary: {e}")
        return {"total": 0, "glossary": []}


@router.get("/stats")
async def get_stats_endpoint(user: UserProfile = Depends(get_current_user)):
    """Returns climber usage metrics, document counts, and quota status."""
    t_uuid = uuid.UUID(user.tenant_id)
    async with get_db_session() as session:
        doc_stmt = (
            select(func.count(Document.id))
            .join(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id)
            .where(
                KnowledgeBase.tenant_id == t_uuid,
                or_(Document.uploaded_by == user.id, Document.is_shared == True)
            )
        )
        chunk_stmt = (
            select(func.count(DocumentChunk.id))
            .join(Document, DocumentChunk.document_id == Document.id)
            .join(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id)
            .where(
                KnowledgeBase.tenant_id == t_uuid,
                or_(Document.uploaded_by == user.id, Document.is_shared == True)
            )
        )

        doc_count = (await session.execute(doc_stmt)).scalar() or 0
        chunk_count = (await session.execute(chunk_stmt)).scalar() or 0

    return {
        "doc_count": doc_count,
        "chunk_count": chunk_count,
        "requests_today": user.requests_today,
        "daily_request_limit": user.daily_request_limit,
        "role": user.role,
        "tenant_id": user.tenant_id,
        "tenant_name": user.tenant_name,
        "tenant_slug": user.tenant_slug,
    }


@router.get("/tenant/info")
async def get_tenant_info_endpoint(user: UserProfile = Depends(get_current_user)):
    """Returns profile and resource quota statistics for the user's organization."""
    async with get_db_session() as session:
        t_uuid = uuid.UUID(user.tenant_id)
        stats = await tenant_repo.get_tenant_stats(session, t_uuid)
        return {"tenant": stats}
