"""
Document Ingestion & Knowledge Base Management Endpoints
========================================================
Handles file upload parsing, web URL ingestion, KB source listing, document deletion,
sharing settings, and document text preview for the Source Viewer.
"""
import os
import uuid
import tempfile
import logging
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, UploadFile, File, Query, Body
from pydantic import BaseModel
from sqlalchemy import select, func, delete, or_
from sqlalchemy.orm import selectinload
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

from main import aingest_document, ingest_document
from auth import get_current_user, UserProfile
from app.db.database import get_db_session
from app.db.models import Document, DocumentChunk, KnowledgeBase
from app.db.repositories import document_repo

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Documents & Knowledge Base"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".pptx", ".xlsx", ".csv"}
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "50")) * 1024 * 1024


class IngestRequest(BaseModel):
    text_or_url: str
    is_shared: bool = False


class DeleteKBRequest(BaseModel):
    source: str | None = None
    ids: list[str] | None = None


class ShareDocumentRequest(BaseModel):
    is_shared: bool


@router.post("/ingest")
@limiter.limit("5/minute")
async def ingest_endpoint(
    request: Request,
    req: IngestRequest,
    background_tasks: BackgroundTasks,
    user: UserProfile = Depends(get_current_user),
):
    """Queues ingestion of raw text or URL into the user's knowledge base. Returns immediately."""
    async def _run_ingest():
        try:
            await aingest_document(
                req.text_or_url,
                user_id=user.id,
                tenant_id=user.tenant_id,
                is_shared=req.is_shared,
            )
        except Exception as e:
            logger.error(f"[BackgroundIngest] Error ingesting URL/text: {e}")

    background_tasks.add_task(_run_ingest)
    return {"status": "queued", "message": "Ingestion started in background. Sources will appear shortly."}


@router.post("/upload")
@router.post("/ingest/upload")
@limiter.limit("5/minute")
async def upload_file_endpoint(
    request: Request,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    is_shared: bool = False,
    user: UserProfile = Depends(get_current_user),
):
    """Uploads and queues a document for ingestion. Returns immediately after file is received."""
    filename = file.filename or ""
    _, ext = os.path.splitext(filename)
    ext = ext.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File extension '{ext}' is not supported. Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum upload size of {MAX_UPLOAD_BYTES // (1024 * 1024)}MB."
        )

    # Write temp file synchronously so background task has a stable path
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
        temp_file.write(content)
        temp_path = temp_file.name

    async def _run_upload():
        try:
            await aingest_document(
                temp_path,
                original_filename=filename,
                user_id=user.id,
                tenant_id=user.tenant_id,
                is_shared=is_shared,
            )
        except Exception as e:
            logger.error(f"[BackgroundIngest] Error ingesting '{filename}': {e}")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    background_tasks.add_task(_run_upload)
    return {"status": "queued", "filename": filename, "message": "Upload received. Processing in background."}


@router.get("/kb/sources")
async def get_kb_sources_endpoint(all_users: bool = False, user: UserProfile = Depends(get_current_user)):
    """Lists knowledge base documents available to the user."""
    try:
        is_admin = user.role in ("superadmin", "admin")
        show_all = all_users and is_admin
        t_uuid = uuid.UUID(user.tenant_id) if user.tenant_id else None

        async with get_db_session() as session:
            stmt = (
                select(Document)
                .options(selectinload(Document.chunks))
                .join(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id)
                .where(KnowledgeBase.tenant_id == t_uuid)
                .order_by(Document.created_at.desc())
            )
            if not show_all:
                stmt = stmt.where(or_(Document.uploaded_by == user.id, Document.is_shared == True))

            docs = (await session.execute(stmt)).scalars().all()
            sources_list = []
            for d in docs:
                display_name = d.filename
                if not display_name or display_name.startswith("tmp"):
                    if d.source_url:
                        display_name = d.source_url
                    elif d.chunks and d.chunks[0].content:
                        # Extract first meaningful line
                        first_line = d.chunks[0].content.strip().split("\n")[0][:60]
                        display_name = first_line or "Document Passage"
                    else:
                        display_name = "Indexed Document"

                sample_text = ""
                if d.chunks and d.chunks[0].content:
                    sample_text = d.chunks[0].content.strip()[:180]

                sources_list.append({
                    "id": str(d.id),
                    "name": display_name,
                    "filename": d.filename or display_name,
                    "source": d.filename or display_name,
                    "type": d.source_type or "file",
                    "source_type": d.source_type or "file",
                    "source_url": d.source_url or "",
                    "is_shared": d.is_shared,
                    "chunk_count": len(d.chunks) if d.chunks else 0,
                    "sample": sample_text,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                    "uploaded_by": d.uploaded_by,
                })

            return {
                "sources": sources_list,
                "total_sources": len(sources_list),
                "total_chunks": sum(s["chunk_count"] for s in sources_list),
            }
    except Exception as e:
        logger.error(f"Error fetching KB sources: {e}")
        return {"sources": [], "total_sources": 0, "total_chunks": 0}


@router.get("/documents/content")
async def get_document_content_endpoint(
    source: str = Query(..., description="Filename or source identifier"),
    doc_id: str | None = Query(None, description="Optional document UUID"),
    user: UserProfile = Depends(get_current_user),
):
    """
    Fetches the full text and chunk structure of an indexed document for the Document Preview viewer.
    """
    try:
        t_uuid = uuid.UUID(user.tenant_id) if user.tenant_id else None
        async with get_db_session() as session:
            stmt = (
                select(Document)
                .join(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id)
                .where(KnowledgeBase.tenant_id == t_uuid)
            )
            if doc_id:
                try:
                    stmt = stmt.where(Document.id == uuid.UUID(doc_id))
                except Exception:
                    stmt = stmt.where(Document.filename == source)
            else:
                stmt = stmt.where(or_(Document.filename == source, Document.source_url == source))

            if user.role not in ("superadmin", "admin"):
                stmt = stmt.where(or_(Document.uploaded_by == user.id, Document.is_shared == True))

            doc = (await session.execute(stmt)).scalars().first()
            if not doc:
                raise HTTPException(status_code=404, detail="Document not found or access restricted.")

            chunks_stmt = (
                select(DocumentChunk)
                .where(DocumentChunk.document_id == doc.id)
                .order_by(DocumentChunk.chunk_index.asc())
            )
            chunks = (await session.execute(chunks_stmt)).scalars().all()

            assembled_text = "\n\n".join(c.content for c in chunks)
            return {
                "id": str(doc.id),
                "filename": doc.filename,
                "source_type": doc.source_type,
                "source_url": doc.source_url,
                "is_shared": doc.is_shared,
                "chunk_count": len(chunks),
                "full_text": assembled_text,
                "chunks": [
                    {
                        "id": str(c.id),
                        "index": c.chunk_index,
                        "text": c.content,
                        "metadata": c.metadata_json or {},
                    }
                    for c in chunks
                ]
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching document content for '{source}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load document content: {str(e)}")


@router.post("/kb/delete")
@router.delete("/kb/delete")
@router.delete("/kb/source")
@router.delete("/kb/documents/{doc_id}")
async def delete_kb_source_endpoint(
    req: DeleteKBRequest = Body(default=None),
    source: str | None = None,
    doc_id: str | None = None,
    user: UserProfile = Depends(get_current_user),
):
    """Deletes a specific source file or chunks by source name, ID, or body payload."""
    target_source = (req.source if req else None) or source
    target_ids = (req.ids if req else None) or ([doc_id] if doc_id else None)

    if not target_source and not target_ids:
        raise HTTPException(status_code=400, detail="Must provide either 'source' or 'ids'.")

    try:
        t_uuid = uuid.UUID(user.tenant_id) if user.tenant_id else None
        async with get_db_session() as session:
            stmt = (
                select(Document)
                .join(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id)
                .where(KnowledgeBase.tenant_id == t_uuid)
            )
            if target_source:
                try:
                    src_uuid = uuid.UUID(target_source)
                    stmt = stmt.where(
                        or_(
                            Document.id == src_uuid,
                            Document.filename == target_source,
                            Document.source_url == target_source,
                        )
                    )
                except Exception:
                    stmt = stmt.where(
                        or_(
                            Document.filename == target_source,
                            Document.source_url == target_source,
                        )
                    )
            if target_ids:
                parsed_uuids = []
                str_names = []
                for i in target_ids:
                    try:
                        parsed_uuids.append(uuid.UUID(str(i)))
                    except Exception:
                        str_names.append(str(i))
                clauses = []
                if parsed_uuids:
                    clauses.append(Document.id.in_(parsed_uuids))
                if str_names:
                    clauses.append(Document.filename.in_(str_names))
                    clauses.append(Document.source_url.in_(str_names))
                if clauses:
                    stmt = stmt.where(or_(*clauses))

            if user.role not in ("superadmin", "admin"):
                stmt = stmt.where(Document.uploaded_by == user.id)

            docs_to_delete = (await session.execute(stmt)).scalars().all()
            for doc in docs_to_delete:
                await session.delete(doc)
            await session.commit()

        return {
            "status": "success",
            "message": f"Successfully removed {len(docs_to_delete)} document(s).",
            "deleted_count": len(docs_to_delete),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting KB source: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete source: {str(e)}")


@router.post("/kb/clear")
@router.delete("/kb/clear")
async def clear_kb_endpoint(
    user: UserProfile = Depends(get_current_user),
):
    """Clears all documents and chunks from the user's / organization's knowledge base."""
    try:
        t_uuid = uuid.UUID(user.tenant_id) if user.tenant_id else None
        async with get_db_session() as session:
            stmt = (
                select(Document)
                .join(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id)
                .where(KnowledgeBase.tenant_id == t_uuid)
            )
            if user.role not in ("superadmin", "admin"):
                stmt = stmt.where(Document.uploaded_by == user.id)

            docs_to_delete = (await session.execute(stmt)).scalars().all()
            for doc in docs_to_delete:
                await session.delete(doc)
            await session.commit()

        return {"status": "success", "message": f"Cleared {len(docs_to_delete)} documents from knowledge base."}
    except Exception as e:
        logger.error(f"Error clearing knowledge base: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear knowledge base: {str(e)}")


@router.patch("/kb/documents/{doc_id}/share")
@router.patch("/kb/source/share")
async def toggle_document_sharing_endpoint(
    req: ShareDocumentRequest,
    doc_id: str | None = None,
    source: str | None = None,
    user: UserProfile = Depends(get_current_user),
):
    """Toggles whether an uploaded document is shared organization-wide across the tenant."""
    try:
        t_uuid = uuid.UUID(user.tenant_id) if user.tenant_id else None
        async with get_db_session() as session:
            stmt = (
                select(Document)
                .join(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id)
                .where(KnowledgeBase.tenant_id == t_uuid)
            )
            if doc_id:
                try:
                    stmt = stmt.where(Document.id == uuid.UUID(doc_id))
                except Exception:
                    stmt = stmt.where(Document.filename == doc_id)
            elif source:
                stmt = stmt.where(Document.filename == source)
            else:
                raise HTTPException(status_code=400, detail="Must provide doc_id or source parameter.")

            if user.role not in ("superadmin", "admin"):
                stmt = stmt.where(Document.uploaded_by == user.id)

            doc = (await session.execute(stmt)).scalars().first()
            if not doc:
                raise HTTPException(status_code=404, detail="Document not found or access denied.")

            doc.is_shared = req.is_shared
            await session.commit()

            return {
                "status": "success",
                "id": str(doc.id),
                "filename": doc.filename,
                "is_shared": doc.is_shared,
                "message": f"Document sharing updated to {doc.is_shared}.",
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating document sharing: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update document sharing: {str(e)}")
