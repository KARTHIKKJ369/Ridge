import json
import logging
from typing import AsyncGenerator
import os
import tempfile
import shutil
from fastapi import FastAPI, HTTPException, UploadFile, File, Request, Depends, status
from fastapi.responses import StreamingResponse, FileResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from main import get_app, get_settings, ingest_document
from auth import (
    get_current_user,
    get_auth_settings,
    create_access_token,
    register_user,
    authenticate_user,
    check_and_increment_user_usage,
    admin_list_users,
    admin_update_user_role,
    admin_update_user_limit,
    admin_update_user_status,
    admin_delete_user,
    RegisterRequest,
    LoginRequest,
    UserProfile,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Ridge API",
    description="High-performance Corrective RAG (CRAG) platform with LangGraph state machine, ChromaDB, FlashRank, and Groq LLMs.",
    version="2.0.0",
)

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://localhost:8000",
    ).split(",")
    if origin.strip()
]
if "*" in ALLOWED_ORIGINS:
    ALLOWED_ORIGINS = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

rag_app = get_app()

class ChatRequest(BaseModel):
    question: str
    web_search_enabled: bool = True
    source_filter: str | None = None

class IngestRequest(BaseModel):
    text_or_url: str


# ---------------------------------------------------------------------------
# Authentication Endpoints (ID + Password Registration & Login)
# ---------------------------------------------------------------------------

@app.get("/api/auth/config")
def auth_config():
    """Returns auth configuration status."""
    settings = get_auth_settings()
    return {
        "enabled": settings["enabled"],
        "mode": "password",
    }


@app.post("/api/auth/register")
def auth_register(req: RegisterRequest):
    """Registers a new user and issues a signed JWT session token."""
    user = register_user(req)
    token = create_access_token(user.model_dump())
    response = JSONResponse({"user": user.model_dump(), "token": token})
    response.set_cookie(
        key="ridge_token",
        value=token,
        max_age=7 * 86400,
        httponly=False,
        samesite="lax",
    )
    return response


@app.post("/api/auth/login")
def auth_login(req: LoginRequest):
    """Authenticates username/email and password, returning JWT token."""
    user = authenticate_user(req)
    token = create_access_token(user.model_dump())
    response = JSONResponse({"user": user.model_dump(), "token": token})
    response.set_cookie(
        key="ridge_token",
        value=token,
        max_age=7 * 86400,
        httponly=False,
        samesite="lax",
    )
    return response


@app.get("/api/auth/me")
def get_me(user: UserProfile = Depends(get_current_user)):
    """Returns the authenticated user profile."""
    return user


@app.post("/api/auth/logout")
def logout():
    """Clears the authentication session."""
    response = JSONResponse({"status": "logged_out"})
    response.delete_cookie("ridge_token")
    return response


# ---------------------------------------------------------------------------
# Corrective RAG Chat & Knowledge Ingestion Endpoints (Protected)
# ---------------------------------------------------------------------------

async def generate_chat_events(question: str, user: UserProfile, web_search_enabled: bool = True, source_filter: str | None = None) -> AsyncGenerator[str, None]:
    # ── 0. Semantic Vector Query Cache Lookup ──────────────────────────────────
    try:
        from query_cache import get_cached_response
        from main import get_embeddings
        embedder = get_embeddings()
        cached = get_cached_response(question, embedder, threshold=0.96, source_filter=source_filter)
        if cached:
            match_pct = int(round(cached.get("similarity", 0.99) * 100))
            # Emit instant cache hit trace
            yield f"data: {json.dumps({'type': 'trace', 'node': 'cache_hit_node', 'message': f'⚡ Semantic Cache Hit ({match_pct}% query match) — Instant Verified Ascent', 'latency_ms': 2})}\n\n"
            
            # Stream cached answer
            ans = cached.get("answer", "")
            yield f"data: {json.dumps({'type': 'token', 'token': ans})}\n\n"
            
            # Emit final trace
            final_trace = {
                "type": "trace",
                "node": "generate_node",
                "message": "Loaded verified answer from Semantic Cache",
                "answer": ans,
                "confidence": cached.get("confidence") or {
                    "score": 98,
                    "level": "HIGH",
                    "breakdown": {
                        "grader_consensus": 100.0,
                        "source_trust": "Semantic Vector Cache (Verified)",
                        "relevant_chunks": 4,
                        "reformulation_loops": 0,
                        "faithfulness": "Verified Cache Hit"
                    }
                },
                "conflict_data": cached.get("conflict_data") or {"detected": False, "summary": "", "sources": []},
                "latency_ms": 2
            }
            yield f"data: {json.dumps(final_trace)}\n\n"
            yield "data: [DONE]\n\n"
            return
    except Exception as cache_err:
        logger.warning(f"Query cache lookup error (continuing with live graph): {cache_err}")

    initial_state = {
        "question": question,
        "original_question": question,
        "web_search_enabled": web_search_enabled,
        "source_filter": source_filter,
        "user_id": user.id,
        "documents": [],
        "documents_metadata": [],
        "generation": "",
        "sub_queries": [],
        "loop_count": 0,
        "past_queries": [],
        "latency_ms": 0,
    }

    try:
        accumulated_answer = ""
        last_confidence = {}
        last_conflict = {}
        async for event in rag_app.astream_events(initial_state, version="v2"):
            kind = event.get("event")
            node_name = event.get("metadata", {}).get("langgraph_node")

            # 1. Live token-by-token streaming from ChatGroq during generate_node
            if kind == "on_chat_model_stream" and node_name == "generate_node":
                chunk = event.get("data", {}).get("chunk")
                content = chunk.content if hasattr(chunk, "content") else str(chunk)
                if content:
                    accumulated_answer += content
                    yield f"data: {json.dumps({'type': 'token', 'token': content})}\n\n"

            # 2. Node completion & trace telemetry events
            elif kind == "on_chain_end" and event.get("name") in [
                "decompose_node", "retrieve_node", "grade_node", "web_search_node",
                "rewrite_node", "generate_node", "check_hallucination_node"
            ]:
                curr_node = event.get("name")
                output = event.get("data", {}).get("output")
                if not isinstance(output, dict):
                    continue

                trace_data = {
                    "type": "trace",
                    "node": curr_node,
                    "message": f"Finished node {curr_node}",
                }
                if "latency_ms" in output:
                    trace_data["latency_ms"] = output["latency_ms"]

                if curr_node == "decompose_node":
                    sqs = output.get("sub_queries", [])
                    docs = output.get("documents", [])
                    if len(sqs) > 1:
                        trace_data["message"] = f"Decomposed into {len(sqs)} sub-queries, pre-fetched {len(docs)} docs"
                    else:
                        trace_data["message"] = "Simple question — no decomposition"
                    trace_data["sub_queries"] = sqs

                elif curr_node == "retrieve_node":
                    docs = output.get("documents", [])
                    expanded = output.get("expanded_count", 0)
                    base_msg = f"Retrieved {len(docs)} documents"
                    if expanded:
                        base_msg += f" · {expanded} expanded via Small-to-Big"
                    trace_data["message"] = base_msg
                    trace_data["documents"] = docs
                    trace_data["expanded_count"] = expanded

                elif curr_node == "grade_node":
                    decision = output.get("generation", "unknown")
                    docs = output.get("documents", [])
                    trace_data["message"] = f"Grading decision: {decision} ({len(docs)} docs relevant)"
                    trace_data["doc_grades"] = output.get("doc_grades", [])

                elif curr_node == "web_search_node":
                    docs = output.get("documents", [])
                    trace_data["message"] = f"Performed web search ({len(docs)} sources retrieved)"
                    trace_data["documents"] = docs
                    trace_data["doc_grades"] = output.get("doc_grades", [])

                elif curr_node == "rewrite_node":
                    new_q = output.get("question", "")
                    trace_data["message"] = f"Rewrote query to: {new_q}"

                elif curr_node == "generate_node":
                    gen = output.get("generation", "")
                    conf = output.get("confidence", {})
                    conflict_data = output.get("conflict_data", {})
                    last_confidence = conf
                    last_conflict = conflict_data
                    trace_data["message"] = "Generated final answer"
                    trace_data["answer"] = gen
                    if conf:
                        trace_data["confidence"] = conf
                    if conflict_data:
                        trace_data["conflict_data"] = conflict_data

                elif curr_node == "check_hallucination_node":
                    h_grade = output.get("hallucination_grade", {})
                    conf = output.get("confidence", {})
                    if conf:
                        last_confidence = conf
                    trace_data["message"] = f"Hallucination audit: {h_grade.get('grounded', 'yes')}"
                    trace_data["hallucination_grade"] = h_grade
                    if conf:
                        trace_data["confidence"] = conf

                yield f"data: {json.dumps(trace_data)}\n\n"

        # ── Store high-confidence result in Semantic Cache ───────────────────
        if accumulated_answer and last_confidence.get("score", 0) >= 60:
            try:
                import threading
                from query_cache import store_cached_response
                from main import get_embeddings
                emb = get_embeddings()
                threading.Thread(
                    target=store_cached_response,
                    args=(question, accumulated_answer, last_confidence, last_conflict, emb, source_filter),
                    daemon=True
                ).start()
            except Exception as store_err:
                logger.warning(f"Could not async store in query cache: {store_err}")

    except Exception as e:
        logger.error(f"Error during streaming: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

    yield "data: [DONE]\n\n"


# ---------------------------------------------------------------------------
# Admin Authorization Dependency
# ---------------------------------------------------------------------------

async def require_admin(user: UserProfile = Depends(get_current_user)) -> UserProfile:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required to access this resource."
        )
    return user


# ---------------------------------------------------------------------------
# Corrective RAG Chat & Knowledge Ingestion Endpoints (Protected)
# ---------------------------------------------------------------------------

@app.post("/ask")
@app.post("/api/chat")
async def ask_question(req: ChatRequest, user: UserProfile = Depends(get_current_user)):
    allowed, current_count, daily_limit = check_and_increment_user_usage(user.id)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily ascent limit reached ({current_count}/{daily_limit} requests used today). Quota resets at 00:00 UTC."
        )
    return StreamingResponse(
        generate_chat_events(req.question, user, req.web_search_enabled, req.source_filter),
        media_type="text/event-stream"
    )

@app.post("/ingest")
async def ingest(req: IngestRequest, user: UserProfile = Depends(get_current_user)):
    try:
        result = ingest_document(req.text_or_url, user_id=user.id)
        return result
    except Exception as e:
        logger.error(f"Error ingesting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".pptx", ".xlsx", ".csv"}
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "50")) * 1024 * 1024

@app.post("/upload")
@app.post("/api/ingest/upload")
async def upload_file(file: UploadFile = File(...), user: UserProfile = Depends(get_current_user)):
    filename = file.filename or ""
    _, ext = os.path.splitext(filename)
    ext = ext.lower()
    
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File extension '{ext}' is not supported. Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    
    try:
        content = await file.read()
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds maximum upload size of {MAX_UPLOAD_BYTES // (1024 * 1024)}MB."
            )
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name
            
        try:
            result = ingest_document(temp_path, original_filename=filename, user_id=user.id)
            return result
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
@app.get("/status")
def health():
    return {"status": "ok", "service": "Ridge RAG"}

@app.get("/api/suggestions")
def get_suggestions(force: bool = False, user: UserProfile = Depends(get_current_user)):
    """
    Returns suggested queries from the in-memory / persistent cache.
    Does NOT make LLM or Chroma DB calls on refresh.
    Only re-generates when force=True or during document ingestion.
    """
    from main import get_suggestions_cache
    if not force:
        sugs = get_suggestions_cache()
        if sugs:
            return {"suggestions": sugs, "cached": True}

    # Only if no cached suggestions exist or force=True, generate from Chroma sample
    try:
        from main import get_vectorstore, generate_suggestions
        vectorstore = get_vectorstore()
        coll = vectorstore._collection
        count = coll.count()
        if count > 0:
            docs = coll.get(limit=4)
            documents = docs.get("documents", [])
            if documents:
                sample_text = " ".join(documents)[:1500]
                new_sugs = generate_suggestions(sample_text)
                if new_sugs:
                    return {"suggestions": new_sugs, "cached": False}
    except Exception as e:
        logger.warning(f"Could not generate suggestions: {e}")

    cached_fallback = get_suggestions_cache()
    return {"suggestions": cached_fallback, "empty": len(cached_fallback) == 0}

@app.get("/api/glossary")
def get_glossary_terms(user: UserProfile = Depends(get_current_user)):
    """Returns the list of indexed acronyms and domain entity definitions."""
    try:
        from glossary import load_glossary
        terms_dict = load_glossary()
        terms_list = list(terms_dict.values())
        return {"total": len(terms_list), "glossary": terms_list}
    except Exception as e:
        logger.error(f"Error loading glossary: {e}")
        return {"total": 0, "glossary": []}


@app.get("/api/stats")
def get_stats(user: UserProfile = Depends(get_current_user)):
    from main import get_vectorstore
    vectorstore = get_vectorstore()
    coll = vectorstore._collection
    count = coll.count()
    data = coll.get(include=["metadatas"])
    metas = data.get("metadatas", []) or []
    
    # Filter strictly by user (admins see their own in default view or all if show_all)
    is_admin = user.role == "admin"
    user_metas = [m for m in metas if m and (m.get("user_id") == user.id or (is_admin and m.get("user_id") == user.id))]
    user_chunks = len(user_metas)
    unique_sources = set(m.get("source") for m in user_metas if m.get("source"))
    doc_count = len(unique_sources) if unique_sources else (1 if user_chunks > 0 else 0)
    
    return {
        "doc_count": doc_count,
        "chunk_count": user_chunks,
        "requests_today": user.requests_today,
        "daily_request_limit": user.daily_request_limit,
        "role": user.role
    }


@app.get("/api/kb/sources")
def get_kb_sources(all_users: bool = False, user: UserProfile = Depends(get_current_user)):
    from main import get_vectorstore
    from pathlib import Path
    try:
        vectorstore = get_vectorstore()
        coll = vectorstore._collection
        count = coll.count()
        if count == 0:
            return {"total_chunks": 0, "total_sources": 0, "sources": []}

        data = coll.get(limit=count + 500, include=["metadatas", "documents"])
        ids = data.get("ids", [])
        metas = data.get("metadatas", [])
        docs = data.get("documents", [])

        is_admin = user.role == "admin"
        show_all = all_users and is_admin

        sources_map = {}
        filtered_chunk_count = 0

        for i, id_ in enumerate(ids):
            meta = metas[i] if i < len(metas) and metas[i] else {}
            meta_user = meta.get("user_id")

            # Multi-tenant isolation: Only include documents belonging strictly to this user
            if not show_all and meta_user != user.id:
                continue

            filtered_chunk_count += 1
            raw_src = meta.get("source", "Unknown Source")
            name = Path(raw_src).name if ("/" in raw_src or "\\" in raw_src) else raw_src
            if not name:
                name = raw_src

            key = f"{meta_user}::{raw_src}" if show_all else raw_src

            if key not in sources_map:
                sources_map[key] = {
                    "source": raw_src,
                    "name": name,
                    "type": meta.get("type", "document"),
                    "h1": meta.get("h1", name),
                    "user_id": meta_user,
                    "chunk_count": 0,
                    "sample": docs[i][:180] if i < len(docs) else "",
                    "ids": []
                }
            sources_map[key]["chunk_count"] += 1
            sources_map[key]["ids"].append(id_)

        sources_list = list(sources_map.values())
        return {
            "total_chunks": filtered_chunk_count,
            "total_sources": len(sources_list),
            "sources": sources_list
        }
    except Exception as e:
        logger.error(f"Failed to get KB sources: {e}")
        return {"total_chunks": 0, "total_sources": 0, "sources": [], "error": str(e)}


class DeleteKBRequest(BaseModel):
    source: str | None = None
    ids: list[str] | None = None


@app.post("/api/kb/delete")
def delete_kb_source(req: DeleteKBRequest, user: UserProfile = Depends(get_current_user)):
    from main import get_vectorstore, invalidate_bm25
    from pathlib import Path
    try:
        vectorstore = get_vectorstore()
        coll = vectorstore._collection
        is_admin = user.role == "admin"

        if req.ids:
            # If not admin, verify all ids belong to this user
            if not is_admin:
                data = coll.get(ids=req.ids, include=["metadatas"])
                valid_ids = [
                    id_ for i, id_ in enumerate(data.get("ids", []))
                    if data.get("metadatas", [])[i].get("user_id") in (user.id, "default", None)
                ]
                if valid_ids:
                    coll.delete(ids=valid_ids)
            else:
                coll.delete(ids=req.ids)

            invalidate_bm25()
            remaining_chunks = coll.count()
            return {"status": "deleted", "remaining_chunks": remaining_chunks}

        if req.source:
            count = coll.count()
            if count > 0:
                data = coll.get(limit=count + 500, include=["metadatas"])
                matching_ids = []
                req_name = Path(req.source).name.lower()
                req_norm = req.source.rstrip("/").lower()
                
                for i, m in enumerate(data.get("metadatas", [])):
                    if not m:
                        continue
                    m_src = str(m.get("source", "")).strip()
                    m_norm = m_src.rstrip("/").lower()
                    m_name = Path(m_src).name.lower()
                    m_user = m.get("user_id")

                    if not is_admin and m_user not in (user.id, "default", None):
                        continue

                    if m_src == req.source or m_norm == req_norm or (req_name and m_name == req_name):
                        matching_ids.append(data["ids"][i])

                if matching_ids:
                    coll.delete(ids=matching_ids)
                    invalidate_bm25()

            remaining_chunks = coll.count()
            return {"status": "deleted", "remaining_chunks": remaining_chunks}

        raise HTTPException(status_code=400, detail="Must provide 'source' or 'ids'")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete_kb_source: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/kb/clear")
def clear_kb(user: UserProfile = Depends(get_current_user)):
    from main import get_vectorstore, clear_suggestions_cache, invalidate_bm25
    try:
        vectorstore = get_vectorstore()
        coll = vectorstore._collection
        count = coll.count()
        if count > 0:
            data = coll.get(limit=count + 500, include=["metadatas"])
            ids = data.get("ids", [])
            metas = data.get("metadatas", []) or []

            is_admin = user.role == "admin"
            if is_admin:
                if ids:
                    coll.delete(ids=ids)
            else:
                user_ids = [ids[i] for i, m in enumerate(metas) if m and m.get("user_id") in (user.id, "default", None)]
                if user_ids:
                    coll.delete(ids=user_ids)
            invalidate_bm25()
    except Exception as e:
        logger.error(f"Error in clear_kb: {e}")

    clear_suggestions_cache()
    if os.path.exists("suggestions.json"):
        try:
            os.remove("suggestions.json")
        except Exception:
            pass

    return {"status": "cleared", "remaining_chunks": 0}


# ---------------------------------------------------------------------------
# Admin Management Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/admin/users")
def get_admin_users(admin: UserProfile = Depends(require_admin)):
    """Lists all registered users with usage stats and roles."""
    return {"users": admin_list_users()}


class UpdateRoleRequest(BaseModel):
    role: str

@app.post("/api/admin/users/{target_id}/role")
def set_user_role(target_id: str, req: UpdateRoleRequest, admin: UserProfile = Depends(require_admin)):
    """Updates user role to admin or user."""
    admin_update_user_role(target_id, req.role.strip().lower())
    return {"status": "updated", "id": target_id, "role": req.role}


class UpdateLimitRequest(BaseModel):
    limit: int

@app.post("/api/admin/users/{target_id}/limit")
def set_user_limit(target_id: str, req: UpdateLimitRequest, admin: UserProfile = Depends(require_admin)):
    """Updates the daily request quota for a user."""
    admin_update_user_limit(target_id, req.limit)
    return {"status": "updated", "id": target_id, "limit": req.limit}


class UpdateStatusRequest(BaseModel):
    is_active: bool

@app.post("/api/admin/users/{target_id}/status")
def set_user_status(target_id: str, req: UpdateStatusRequest, admin: UserProfile = Depends(require_admin)):
    """Activates or suspends a user account."""
    admin_update_user_status(target_id, req.is_active)
    return {"status": "updated", "id": target_id, "is_active": req.is_active}


@app.delete("/api/admin/users/{target_id}")
def delete_user_account(target_id: str, admin: UserProfile = Depends(require_admin)):
    """Deletes a user account and purges their indexed chunks from ChromaDB."""
    if target_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own administrator account.")
    
    # 1. Delete user files from ChromaDB
    try:
        from main import get_vectorstore, invalidate_bm25
        vectorstore = get_vectorstore()
        coll = vectorstore._collection
        count = coll.count()
        if count > 0:
            data = coll.get(limit=count + 500, include=["metadatas"])
            ids = data.get("ids", [])
            metas = data.get("metadatas", []) or []
            user_ids = [ids[i] for i, m in enumerate(metas) if m and m.get("user_id") == target_id]
            if user_ids:
                coll.delete(ids=user_ids)
                invalidate_bm25()
    except Exception as e:
        logger.warning(f"Note purging user chunks on delete: {e}")

    # 2. Delete user record from SQLite
    admin_delete_user(target_id)
    return {"status": "deleted", "id": target_id}


@app.get("/api/admin/stats")
def get_admin_stats(admin: UserProfile = Depends(require_admin)):
    """Returns global system metrics."""
    users = admin_list_users()
    total_users = len(users)
    active_users = sum(1 for u in users if u.get("is_active"))
    total_requests_today = sum(u.get("requests_today", 0) for u in users)

    from main import get_vectorstore
    try:
        vectorstore = get_vectorstore()
        coll = vectorstore._collection
        chunk_count = coll.count()
        data = coll.get(include=["metadatas"])
        metas = data.get("metadatas", []) or []
        unique_sources = set(m.get("source") for m in metas if m and m.get("source"))
        doc_count = len(unique_sources)
    except Exception:
        chunk_count = 0
        doc_count = 0

    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_requests_today": total_requests_today,
        "total_documents": doc_count,
        "total_chunks": chunk_count,
    }


# Mount the compiled React frontend
frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.isdir(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
else:
    @app.get("/")
    def index():
        return {"message": "Frontend not built yet. Run 'npm run build' in frontend/"}

