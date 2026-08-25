"""
Document Ingestion & Knowledge Base Management Endpoints
========================================================
Handles file upload parsing, web URL ingestion, KB source listing, document deletion, and sharing settings.
"""
import os
import tempfile
import logging
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import select, func, delete, or_
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

from main import ingest_document
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
    def _run_ingest():
        try:
            ingest_document(
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

    def _run_ingest():
        try:
            ingest_document(
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

    background_tasks.add_task(_run_ingest)
    return {"status": "queued", "filename": filename, "message": "Upload received. Processing in background."}


@router.get("/kb/sources")
async def get_kb_sources_endpoint(all_users: bool = False, user: UserProfile = Depends(get_current_user)):
    """Lists knowledge base documents available to the user."""
    import uuid
    try:
        is_admin = user.role in ("superadmin", "admin")
        show_all = all_users and is_admin
        t_uuid = uuid.UUID(user.tenant_id)

        async with get_db_session() as session:
            stmt = (
                select(Document)
                .join(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id)
                .where(KnowledgeBase.tenant_id == t_uuid)
                .order_by(Document.created_at.desc())
            )
            if not show_all:
                stmt = stmt.where(or_(Document.uploaded_by == user.id, Document.is_shared == True))

            docs = (await session.execute(stmt)).scalars().all()
            if not docs:
                return {"total_chunks": 0, "total_sources": 0, "sources": []}

            sources_list = []
            total_chunks = 0

            for doc in docs:
                chunk_cnt_stmt = select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == doc.id)
                c_count = (await session.execute(chunk_cnt_stmt)).scalar() or 0
                total_chunks += c_count

                sample_stmt = select(DocumentChunk.content).where(DocumentChunk.document_id == doc.id).limit(1)
                sample = (await session.execute(sample_stmt)).scalar() or ""

                raw_src = doc.filename or doc.source_url or "Unknown Source"
                name = Path(raw_src).name if ("/" in raw_src or "\\" in raw_src) else raw_src

                sources_list.append({
                    "id": str(doc.id),
                    "source": raw_src,
                    "name": name,
                    "type": doc.source_type or "document",
                    "h1": name,
                    "user_id": doc.uploaded_by or "shared",
                    "is_shared": doc.is_shared,
                    "tenant_id": str(t_uuid),
                    "chunk_count": c_count,
                    "sample": sample[:180],
                    "ids": [str(doc.id)]
                })

            return {
                "total_chunks": total_chunks,
                "total_sources": len(sources_list),
                "sources": sources_list
            }
    except Exception as e:
        logger.error(f"Failed to get KB sources: {e}")
        return {"total_chunks": 0, "total_sources": 0, "sources": [], "error": str(e)}


@router.post("/kb/delete")
async def delete_kb_source_endpoint(req: DeleteKBRequest, user: UserProfile = Depends(get_current_user)):
    """Deletes specific documents from the knowledge base."""
    try:
        is_admin = user.role == "admin"

        async with get_db_session() as session:
            if req.ids:
                import uuid
                doc_uuids = []
                for i in req.ids:
                    try:
                        doc_uuids.append(uuid.UUID(i))
                    except Exception:
                        pass
                if doc_uuids:
                    stmt = delete(Document).where(Document.id.in_(doc_uuids))
                    if not is_admin:
                        stmt = stmt.where(or_(Document.uploaded_by == user.id, Document.uploaded_by.is_(None)))
                    await session.execute(stmt)

            elif req.source:
                stmt = delete(Document).where(Document.filename == req.source)
                if not is_admin:
                    stmt = stmt.where(or_(Document.uploaded_by == user.id, Document.uploaded_by.is_(None)))
                await session.execute(stmt)

                try:
                    from glossary import remove_source_from_glossary
                    remove_source_from_glossary(req.source, user_id=None if is_admin else user.id)
                except Exception as ge:
                    logger.warning(f"Error removing source from glossary: {ge}")
            else:
                raise HTTPException(status_code=400, detail="Must provide 'source' or 'ids'")

            rem_stmt = select(func.count(DocumentChunk.id))
            remaining_chunks = (await session.execute(rem_stmt)).scalar() or 0
            return {"status": "deleted", "remaining_chunks": remaining_chunks}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete_kb_source: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/kb/clear")
async def clear_kb_endpoint(user: UserProfile = Depends(get_current_user)):
    """Clears all knowledge base documents for the user or organization."""
    try:
        is_admin = user.role == "admin"
        async with get_db_session() as session:
            if is_admin:
                await session.execute(delete(Document))
            else:
                await session.execute(delete(Document).where(Document.uploaded_by == user.id))
    except Exception as e:
        logger.error(f"Error in clear_kb: {e}")

    try:
        from glossary import clear_glossary
        clear_glossary(user_id=None if user.role == "admin" else user.id)
    except Exception as ge:
        logger.warning(f"Error clearing glossary: {ge}")

    from main import clear_suggestions_cache
    clear_suggestions_cache()
    if os.path.exists("suggestions.json"):
        try:
            os.remove("suggestions.json")
        except Exception:
            pass

    return {"status": "cleared", "remaining_chunks": 0}


@router.patch("/kb/documents/{document_id}/share")
async def toggle_document_sharing_endpoint(
    document_id: str,
    req: ShareDocumentRequest,
    user: UserProfile = Depends(get_current_user)
):
    """Toggles a document between private and organization-shared."""
    import uuid
    try:
        doc_uuid = uuid.UUID(document_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid document UUID.")

    is_admin = user.role in ("superadmin", "admin")
    async with get_db_session() as session:
        doc = await document_repo.toggle_document_sharing(
            session=session,
            doc_id=doc_uuid,
            is_shared=req.is_shared,
            user_id=user.id,
            is_admin=is_admin,
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found or unauthorized.")
        await session.commit()
        return {"status": "updated", "document_id": str(doc.id), "is_shared": doc.is_shared}
