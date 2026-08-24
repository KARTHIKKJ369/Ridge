"""
Document, Chunk & pgvector Ingestion Repository
===============================================
Handles persistence of ingested documents, semantic parents, child chunks,
pgvector embeddings, and PostgreSQL tsvector full-text search generation.
"""
import uuid
import os
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

from sqlalchemy import select, delete, func, or_, text
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import Document
from app.db.models.document_chunk import DocumentChunk
from app.db.models.embedding import ChunkEmbedding
from app.db.models.knowledge_base import KnowledgeBase
from app.db.repositories.user_repo import DEFAULT_TENANT_ID

DEFAULT_KB_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def get_or_create_default_kb(session: AsyncSession) -> uuid.UUID:
    from app.db.models.tenant import Tenant
    t_res = await session.execute(select(Tenant).where(Tenant.id == DEFAULT_TENANT_ID))
    tenant = t_res.scalar_one_or_none()
    if not tenant:
        tenant = Tenant(
            id=DEFAULT_TENANT_ID,
            name="Default Tenant",
            slug="default",
            plan="enterprise",
            is_active=True,
        )
        session.add(tenant)
        await session.flush()

    res = await session.execute(select(KnowledgeBase).where(KnowledgeBase.id == DEFAULT_KB_ID))
    kb = res.scalar_one_or_none()
    if not kb:
        kb = KnowledgeBase(
            id=DEFAULT_KB_ID,
            tenant_id=DEFAULT_TENANT_ID,
            name="Default Knowledge Base",
            description="Primary system knowledge base",
        )
        session.add(kb)
        await session.flush()
    return kb.id



async def save_ingested_document(
    session: AsyncSession,
    uploaded_by: str,
    filename: str,
    source_type: str,
    source_url: str,
    parent_records: list[dict],
    child_docs: list,
    embeddings_list: list[list[float]],
    embedding_model_name: str,
    mime_type: str = "text/plain",
    file_size: int = 0,
    content_hash: str = "",
    knowledge_base_id: Optional[uuid.UUID] = None,
) -> Document:
    """
    Saves the complete document hierarchy in a single transaction:
    1. Document row
    2. Parent chunks in document_chunks
    3. Child chunks with parent_chunk_id FK
    4. Chunk embeddings in chunk_embeddings
    5. Generates tsvector search vectors for lexical search
    """
    kb_id = knowledge_base_id or await get_or_create_default_kb(session)

    # Ensure user exists in PostgreSQL users table to satisfy foreign key constraint
    if uploaded_by and uploaded_by not in ("shared", "default", "system"):
        from app.db.models.user import User
        u_check = await session.get(User, uploaded_by)
        if not u_check:
            stub_user = User(
                id=uploaded_by,
                tenant_id=DEFAULT_TENANT_ID,
                username=uploaded_by,
                email=f"{uploaded_by}@ridge.ai",
                name=uploaded_by,
                password_hash="",
                salt="",
                role="user",
                is_active=True,
                daily_request_limit=50,
            )
            session.add(stub_user)
            await session.flush()

    # 1. Create Document
    doc = Document(
        id=uuid.uuid4(),
        knowledge_base_id=kb_id,
        uploaded_by=uploaded_by if uploaded_by not in ("shared", "default", "system") else None,
        filename=filename,
        mime_type=mime_type,
        file_size=file_size,
        source_type=source_type,
        source_url=source_url,
        content_hash=content_hash,
        status="indexed",
        version=1,
    )

    session.add(doc)
    await session.flush()

    # 2. Map & Create Parent Chunks
    # parent_records: list of {"id": pid_str, "text": content, "metadata": dict}
    pid_to_uuid: dict[str, uuid.UUID] = {}
    for idx, p in enumerate(parent_records):
        p_uuid = uuid.uuid4()
        pid_to_uuid[p["id"]] = p_uuid
        p_meta = p.get("metadata", {})
        
        parent_chunk = DocumentChunk(
            id=p_uuid,
            document_id=doc.id,
            parent_chunk_id=None,
            chunk_index=idx,
            content=p["text"],
            heading=str(p_meta.get("h1", "")),
            section=str(p_meta.get("h2", "")),
            page_number=p_meta.get("page"),
            metadata_json={**p_meta, "is_parent": True, "source": filename or source_url},
        )
        session.add(parent_chunk)

    await session.flush()

    # 3. Create Child Chunks & Vector Embeddings
    for idx, (child_doc, emb_vec) in enumerate(zip(child_docs, embeddings_list)):
        c_meta = dict(getattr(child_doc, "metadata", {}) or {})
        c_text = getattr(child_doc, "page_content", str(child_doc))
        
        legacy_pid = c_meta.get("parent_id")
        parent_db_uuid = pid_to_uuid.get(legacy_pid) if legacy_pid else None

        child_chunk = DocumentChunk(
            id=uuid.uuid4(),
            document_id=doc.id,
            parent_chunk_id=parent_db_uuid,
            chunk_index=idx,
            content=c_text,
            heading=str(c_meta.get("h1", "")),
            section=str(c_meta.get("h2", "")),
            page_number=c_meta.get("page"),
            metadata_json={**c_meta, "source": filename or source_url, "user_id": uploaded_by},
        )
        session.add(child_chunk)
        await session.flush()

        # 4. Add Chunk Embedding
        chunk_emb = ChunkEmbedding(
            id=uuid.uuid4(),
            chunk_id=child_chunk.id,
            embedding_model=embedding_model_name,
            embedding=emb_vec,
        )
        session.add(chunk_emb)

    # 5. Populate search_vector tsvectors for lexical FTS
    await session.execute(
        text("""
            UPDATE document_chunks
            SET search_vector = to_tsvector('english', coalesce(heading, '') || ' ' || coalesce(section, '') || ' ' || content)
            WHERE document_id = :doc_id
        """),
        {"doc_id": doc.id}
    )

    await session.flush()
    return doc


async def get_kb_sources_summary(
    session: AsyncSession,
    user_id: str,
    all_users: bool = False,
    is_admin: bool = False,
) -> dict:
    """Returns aggregated list of sources with chunk counts for the user."""
    stmt = (
        select(
            Document.id,
            Document.filename,
            Document.source_type,
            Document.source_url,
            Document.uploaded_by,
            func.count(DocumentChunk.id).label("chunk_count"),
        )
        .outerjoin(DocumentChunk, Document.id == DocumentChunk.document_id)
        .group_by(Document.id)
        .order_by(Document.created_at.desc())
    )

    if not (all_users and is_admin):
        stmt = stmt.where(
            or_(
                Document.uploaded_by == user_id,
                Document.uploaded_by == "default",
                Document.uploaded_by.is_(None),
            )
        )

    res = await session.execute(stmt)
    rows = res.all()

    sources_list = []
    total_chunks = 0

    for r in rows:
        raw_src = r.filename or r.source_url or "Unknown Source"
        name = Path(raw_src).name if ("/" in raw_src or "\\" in raw_src) else raw_src
        chunks = r.chunk_count or 0
        total_chunks += chunks

        sources_list.append({
            "id": str(r.id),
            "source": raw_src,
            "name": name,
            "type": r.source_type,
            "h1": name,
            "user_id": r.uploaded_by,
            "chunk_count": chunks,
            "sample": "",
            "ids": [str(r.id)],
        })

    return {
        "total_chunks": total_chunks,
        "total_sources": len(sources_list),
        "sources": sources_list,
    }


async def delete_kb_source(
    session: AsyncSession,
    source_name: Optional[str] = None,
    doc_ids: Optional[list[str]] = None,
    user_id: Optional[str] = None,
    is_admin: bool = False,
) -> int:
    """Deletes documents matching source or doc_ids with cascade to chunks and embeddings."""
    stmt = delete(Document)

    if doc_ids:
        uuids = []
        for d in doc_ids:
            try:
                uuids.append(uuid.UUID(d))
            except Exception:
                pass
        if uuids:
            stmt = stmt.where(Document.id.in_(uuids))
    elif source_name:
        req_name = Path(source_name).name.lower()
        stmt = stmt.where(
            or_(
                Document.filename == source_name,
                Document.source_url == source_name,
                func.lower(Document.filename) == req_name,
            )
        )

    if not is_admin and user_id:
        stmt = stmt.where(
            or_(
                Document.uploaded_by == user_id,
                Document.uploaded_by == "default",
                Document.uploaded_by.is_(None),
            )
        )

    res = await session.execute(stmt)
    return res.rowcount


async def clear_all_kb(
    session: AsyncSession,
    user_id: Optional[str] = None,
    is_admin: bool = False,
) -> int:
    """Clears all documents for a user or globally if admin."""
    stmt = delete(Document)
    if not is_admin and user_id:
        stmt = stmt.where(
            or_(
                Document.uploaded_by == user_id,
                Document.uploaded_by == "default",
                Document.uploaded_by.is_(None),
            )
        )
    res = await session.execute(stmt)
    return res.rowcount
