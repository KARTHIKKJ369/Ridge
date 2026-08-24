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
from app.db.models.ingestion_run import IngestionRun
from app.db.models.document_table import DocumentTable
from app.db.models.document_figure import DocumentFigure
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
    is_shared: bool = False,
    knowledge_base_id: Optional[uuid.UUID] = None,
    ingestion_run_info: Optional[dict] = None,
    table_records: Optional[list[dict]] = None,
    figure_records: Optional[list[dict]] = None,
) -> Document:
    """
    Saves the complete document hierarchy and lineage in a single transaction:
    1. Document row
    2. IngestionRun lineage record
    3. Parent chunks in document_chunks
    4. Child chunks with parent_chunk_id FK, raw_content, and contextual_content
    5. Chunk embeddings in chunk_embeddings
    6. Structured DocumentTable and DocumentFigure records
    7. Generates tsvector search vectors for lexical search
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
        is_shared=is_shared,
        version=1,
    )
    session.add(doc)
    await session.flush()

    # 2. Record Ingestion Lineage
    run_id = None
    if ingestion_run_info:
        run_obj = IngestionRun(
            id=uuid.uuid4(),
            document_id=doc.id,
            parser_name=ingestion_run_info.get("parser_name", "unified"),
            parser_version=ingestion_run_info.get("parser_version", "1.0.0"),
            chunker_version=ingestion_run_info.get("chunker_version", "structure_v1"),
            embedding_model=embedding_model_name,
            contextualization_model=ingestion_run_info.get("contextualization_model"),
            processing_started_at=ingestion_run_info.get("started_at", datetime.now(timezone.utc)),
            processing_finished_at=datetime.now(timezone.utc),
            processing_time_ms=ingestion_run_info.get("processing_time_ms", 0),
            chunk_count=len(child_docs),
            parent_count=len(parent_records),
            table_count=len(table_records or []),
            figure_count=len(figure_records or []),
            ocr_page_count=ingestion_run_info.get("ocr_page_count", 0),
            dedup_removed_count=ingestion_run_info.get("dedup_removed_count", 0),
            status="completed",
        )
        session.add(run_obj)
        await session.flush()
        run_id = run_obj.id

    # 3. Map & Create Parent Chunks
    pid_to_uuid: dict[str, uuid.UUID] = {}
    for idx, p in enumerate(parent_records):
        p_uuid = uuid.uuid4()
        pid_to_uuid[p["id"]] = p_uuid
        p_meta = p.get("metadata", {})
        
        parent_chunk = DocumentChunk(
            id=p_uuid,
            document_id=doc.id,
            parent_chunk_id=None,
            ingestion_run_id=run_id,
            chunk_index=idx,
            content=p["text"],
            raw_content=p["text"],
            heading=str(p_meta.get("h1", "")),
            section=str(p_meta.get("h2", "")),
            page_number=p_meta.get("page"),
            content_type=p_meta.get("content_type", "text"),
            metadata_json={**p_meta, "is_parent": True, "source": filename or source_url},
        )
        session.add(parent_chunk)

    await session.flush()

    # 4. Create Child Chunks & Vector Embeddings
    for idx, (child_doc, emb_vec) in enumerate(zip(child_docs, embeddings_list)):
        c_meta = dict(getattr(child_doc, "metadata", {}) or {})
        c_text = getattr(child_doc, "page_content", str(child_doc))
        
        legacy_pid = c_meta.get("parent_id")
        parent_db_uuid = pid_to_uuid.get(legacy_pid) if legacy_pid else None

        child_chunk = DocumentChunk(
            id=uuid.uuid4(),
            document_id=doc.id,
            parent_chunk_id=parent_db_uuid,
            ingestion_run_id=run_id,
            chunk_index=idx,
            content=c_text,
            raw_content=c_meta.get("raw_content", c_text),
            contextual_content=c_meta.get("contextual_content"),
            content_type=c_meta.get("content_type", "text"),
            heading=str(c_meta.get("h1", "")),
            section=str(c_meta.get("h2", "")),
            page_number=c_meta.get("page"),
            metadata_json={**c_meta, "source": filename or source_url, "user_id": uploaded_by},
        )
        session.add(child_chunk)
        await session.flush()

        # Add Chunk Embedding
        chunk_emb = ChunkEmbedding(
            id=uuid.uuid4(),
            chunk_id=child_chunk.id,
            embedding_model=embedding_model_name,
            embedding=emb_vec,
        )
        session.add(chunk_emb)

    # 5. Persist Structured Tables if any
    if table_records:
        for t_idx, t_data in enumerate(table_records):
            tbl = DocumentTable(
                id=uuid.uuid4(),
                document_id=doc.id,
                page_number=t_data.get("page_number", 1),
                table_index=t_idx,
                caption=t_data.get("caption", ""),
                section_path=t_data.get("section_path", ""),
                headers_json=t_data.get("headers", []),
                rows_json=t_data.get("rows", []),
                markdown_text=t_data.get("markdown", ""),
                search_text=t_data.get("search_text", ""),
                metadata_json=t_data.get("metadata", {}),
            )
            session.add(tbl)

    # 6. Persist Structured Figures if any
    if figure_records:
        for f_idx, f_data in enumerate(figure_records):
            fig = DocumentFigure(
                id=uuid.uuid4(),
                document_id=doc.id,
                page_number=f_data.get("page_number", 1),
                figure_index=f_idx,
                caption=f_data.get("caption", ""),
                section_path=f_data.get("section_path", ""),
                image_path=f_data.get("image_path", ""),
                ocr_text=f_data.get("ocr_text", ""),
                description=f_data.get("description", ""),
                nearby_text=f_data.get("nearby_text", ""),
                metadata_json=f_data.get("metadata", {}),
            )
            session.add(fig)

    # 7. Populate search_vector tsvectors for lexical FTS
    await session.execute(
        text("""
            UPDATE document_chunks
            SET search_vector = to_tsvector('english', coalesce(heading, '') || ' ' || coalesce(section, '') || ' ' || coalesce(contextual_content, '') || ' ' || content)
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


async def get_document_by_id(session: AsyncSession, doc_id: uuid.UUID) -> Optional[Document]:
    """Fetch document by UUID."""
    res = await session.execute(select(Document).where(Document.id == doc_id))
    return res.scalar_one_or_none()


async def toggle_document_sharing(
    session: AsyncSession,
    doc_id: uuid.UUID,
    is_shared: bool,
    user_id: Optional[str] = None,
    is_admin: bool = False,
) -> Optional[Document]:
    """Toggles a document between private and organization-shared."""
    doc = await get_document_by_id(session, doc_id)
    if not doc:
        return None

    # Check permission (must be uploader or admin)
    if not is_admin and user_id and doc.uploaded_by != user_id:
        return None

    doc.is_shared = is_shared
    await session.flush()
    return doc


async def list_admin_documents(
    session: AsyncSession,
    tenant_id: Optional[uuid.UUID] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """Lists all documents with chunk counts, uploader username, and tenant metadata."""
    from app.db.models.tenant import Tenant
    from app.db.models.user import User

    query = (
        select(
            Document,
            KnowledgeBase.tenant_id.label("kb_tenant_id"),
            Tenant.name.label("tenant_name"),
            Tenant.slug.label("tenant_slug"),
            User.username.label("uploader_username"),
            User.name.label("uploader_name"),
            func.count(DocumentChunk.id).label("chunk_count"),
        )
        .join(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id)
        .outerjoin(Tenant, KnowledgeBase.tenant_id == Tenant.id)
        .outerjoin(User, Document.uploaded_by == User.id)
        .outerjoin(DocumentChunk, DocumentChunk.document_id == Document.id)
    )

    if tenant_id:
        query = query.where(KnowledgeBase.tenant_id == tenant_id)

    query = (
        query.group_by(
            Document.id,
            KnowledgeBase.tenant_id,
            Tenant.name,
            Tenant.slug,
            User.username,
            User.name,
        )
        .order_by(Document.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    res = await session.execute(query)
    rows = res.all()

    docs = []
    for doc, kb_tid, t_name, t_slug, u_username, u_name, c_count in rows:
        docs.append({
            "id": str(doc.id),
            "filename": doc.filename,
            "file_size": doc.file_size,
            "mime_type": doc.mime_type,
            "source_type": doc.source_type,
            "source_url": doc.source_url,
            "is_shared": doc.is_shared,
            "status": doc.status,
            "chunk_count": c_count or 0,
            "uploaded_by": doc.uploaded_by or "system",
            "uploader_username": u_username or "system",
            "uploader_name": u_name or "System Administrator",
            "tenant_id": str(kb_tid) if kb_tid else "",
            "tenant_name": t_name or "Default",
            "tenant_slug": t_slug or "default",
            "created_at": doc.created_at.isoformat() if doc.created_at else "",
        })
    return docs


async def bulk_delete_documents(
    session: AsyncSession,
    doc_ids: list[uuid.UUID],
) -> int:
    """Bulk deletes multiple documents and their cascaded chunks/embeddings."""
    if not doc_ids:
        return 0
    stmt = delete(Document).where(Document.id.in_(doc_ids))
    res = await session.execute(stmt)
    await session.flush()
    return res.rowcount


