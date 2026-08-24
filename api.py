import json
import logging
from typing import AsyncGenerator, Optional
import os
import tempfile
import shutil
import time
from contextlib import asynccontextmanager
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
from app.db.database import (
    init_db as init_postgres_db,
    is_postgres_configured,
    get_db_session,
)
from app.db.models import Document, DocumentChunk
from sqlalchemy import select, func, delete, or_

from app.db.repositories import (
    user_repo,
    conversation_repo,
    document_repo,
    glossary_repo,
    cache_repo,
    retrieval_repo,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if is_postgres_configured():
        try:
            await init_postgres_db()
            logger.info("✓ PostgreSQL & pgvector schema initialized on startup.")
        except Exception as e:
            logger.warning(f"Note on DB startup init: {e}")
    yield


app = FastAPI(
    title="Ridge API",
    description="High-performance Corrective RAG (CRAG) platform with LangGraph state machine, PostgreSQL/pgvector, FlashRank, and Groq LLMs.",
    version="2.1.0",
    lifespan=lifespan,
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
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

rag_app = get_app()


class ChatRequest(BaseModel):
    question: str
    web_search_enabled: bool = True
    source_filter: str | None = None
    conversation_id: str | None = None


class IngestRequest(BaseModel):
    text_or_url: str


class CreateConversationRequest(BaseModel):
    title: str = "New Research Ascent"


class UpdateConversationRequest(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None


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
# Conversation & Chat Persistence Endpoints (Protected)
# ---------------------------------------------------------------------------

@app.get("/api/conversations")
async def list_conversations(
    limit: int = 50,
    offset: int = 0,
    user: UserProfile = Depends(get_current_user),
):
    """Lists persistent conversations for the authenticated user."""
    if not is_postgres_configured():
        return {"conversations": []}
    async with get_db_session() as session:
        convs = await conversation_repo.list_conversations(session, user.id, limit=limit, offset=offset)
        return {"conversations": convs}


@app.post("/api/conversations")
async def create_conversation_endpoint(
    req: CreateConversationRequest = CreateConversationRequest(),
    user: UserProfile = Depends(get_current_user),
):
    """Creates a new persistent conversation."""
    if not is_postgres_configured():
        return {"id": str(int(time.time() * 1000)), "title": req.title, "createdAt": int(time.time() * 1000)}
    async with get_db_session() as session:
        conv = await conversation_repo.create_conversation(session, user.id, title=req.title)
        return {
            "id": str(conv.id),
            "title": conv.title,
            "createdAt": int(conv.created_at.timestamp() * 1000),
            "updatedAt": int(conv.updated_at.timestamp() * 1000),
            "messages": [],
        }


@app.get("/api/conversations/{conv_id}")
async def get_conversation_endpoint(
    conv_id: str,
    user: UserProfile = Depends(get_current_user),
):
    """Gets conversation metadata by ID."""
    if not is_postgres_configured():
        return {"id": conv_id, "title": "Research Ascent"}
    async with get_db_session() as session:
        conv = await conversation_repo.get_conversation(session, conv_id, user_id=user.id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        return {
            "id": str(conv.id),
            "title": conv.title,
            "summary": conv.summary,
            "createdAt": int(conv.created_at.timestamp() * 1000),
            "updatedAt": int(conv.updated_at.timestamp() * 1000),
        }


@app.patch("/api/conversations/{conv_id}")
async def update_conversation_endpoint(
    conv_id: str,
    req: UpdateConversationRequest,
    user: UserProfile = Depends(get_current_user),
):
    """Updates conversation title or summary."""
    if not is_postgres_configured():
        return {"status": "updated", "id": conv_id}
    async with get_db_session() as session:
        ok = await conversation_repo.update_conversation(
            session, conv_id, user.id, title=req.title, summary=req.summary
        )
        if not ok:
            raise HTTPException(status_code=404, detail="Conversation not found or unauthorized.")
        return {"status": "updated", "id": conv_id}


@app.delete("/api/conversations/{conv_id}")
async def delete_conversation_endpoint(
    conv_id: str,
    user: UserProfile = Depends(get_current_user),
):
    """Deletes a persistent conversation and its messages."""
    if not is_postgres_configured():
        return {"status": "deleted", "id": conv_id}
    async with get_db_session() as session:
        ok = await conversation_repo.delete_conversation(session, conv_id, user.id)
        if not ok:
            raise HTTPException(status_code=404, detail="Conversation not found or unauthorized.")
        return {"status": "deleted", "id": conv_id}


@app.get("/api/conversations/{conv_id}/messages")
async def get_conversation_messages_endpoint(
    conv_id: str,
    user: UserProfile = Depends(get_current_user),
):
    """Returns the message history and citations for a conversation."""
    if not is_postgres_configured():
        return {"messages": []}
    async with get_db_session() as session:
        msgs = await conversation_repo.get_conversation_messages(session, conv_id, user_id=user.id)
        return {"messages": msgs}


# ---------------------------------------------------------------------------
# Corrective RAG Chat & Knowledge Ingestion Endpoints (Protected)
# ---------------------------------------------------------------------------


async def generate_chat_events(
    question: str,
    user: UserProfile,
    web_search_enabled: bool = True,
    source_filter: str | None = None,
    conversation_id: str | None = None,
) -> AsyncGenerator[str, None]:
    t_start = time.time()
    db_conv_id = conversation_id
    user_msg_id = None
    captured_traces = []

    # ── Persistent Conversation & User Message Initialization ────────────────
    if is_postgres_configured():
        try:
            async with get_db_session() as session:
                if not db_conv_id:
                    # Auto-create new conversation
                    title_candidate = question.strip()[:60]
                    new_conv = await conversation_repo.create_conversation(
                        session, user_id=user.id, title=title_candidate or "New Research Ascent"
                    )
                    db_conv_id = str(new_conv.id)
                else:
                    # Verify existence
                    existing_conv = await conversation_repo.get_conversation(session, db_conv_id, user_id=user.id)
                    if not existing_conv:
                        new_conv = await conversation_repo.create_conversation(
                            session, user_id=user.id, title=question.strip()[:60] or "New Research Ascent"
                        )
                        db_conv_id = str(new_conv.id)

                # Persist User Message
                u_msg = await conversation_repo.add_message(
                    session=session,
                    conversation_id=db_conv_id,
                    role="user",
                    content=question,
                    status="completed",
                )
                user_msg_id = u_msg.id
        except Exception as db_init_err:
            logger.warning(f"Note creating conversation record: {db_init_err}")

    # Emit conversation ID trace event if we have one
    if db_conv_id:
        yield f"data: {json.dumps({'type': 'conversation_info', 'conversation_id': db_conv_id})}\n\n"

    # ── 0. Semantic Vector Query Cache Lookup ──────────────────────────────────
    try:
        from main import get_embeddings
        embedder = get_embeddings()
        q_emb = embedder.embed_query(question)
        cached = None

        # Check pgvector query cache first
        if is_postgres_configured():
            try:
                async with get_db_session() as session:
                    cached = await cache_repo.get_cached_response(
                        session=session,
                        query=question,
                        query_vector=q_emb,
                        threshold=0.96,
                        source_filter=source_filter,
                    )
            except Exception as pg_cache_err:
                logger.warning(f"pgvector query cache note: {pg_cache_err}")

        # Fallback to local query cache if not found
        if not cached:
            from query_cache import get_cached_response as get_local_cached_response
            cached = get_local_cached_response(question, embedder, threshold=0.96, source_filter=source_filter)

        if cached:
            match_pct = int(round(cached.get("similarity", 0.99) * 100))
            # Emit instant cache hit trace
            yield f"data: {json.dumps({'type': 'trace', 'node': 'cache_hit_node', 'message': f'⚡ Semantic Cache Hit ({match_pct}% query match) — Instant Verified Ascent', 'latency_ms': 2})}\n\n"
            
            # Stream clean cached answer
            import re
            ans = re.sub(r'^\s*\{[\s\S]*?"summary":\s*"[^"]*"\s*\}\s*', '', cached.get("answer", "")).strip()
            yield f"data: {json.dumps({'type': 'token', 'token': ans})}\n\n"
            
            conf = cached.get("confidence") or {
                "score": 98,
                "level": "HIGH",
                "breakdown": {
                    "grader_consensus": 100.0,
                    "source_trust": "Semantic Vector Cache (Verified)",
                    "relevant_chunks": 4,
                    "reformulation_loops": 0,
                    "faithfulness": "Verified Cache Hit"
                }
            }
            conflict_data = cached.get("conflict_data") or {"detected": False, "summary": "", "sources": []}

            # Emit final trace
            final_trace = {
                "type": "trace",
                "node": "generate_node",
                "message": "Loaded verified answer from Semantic Cache",
                "answer": ans,
                "confidence": conf,
                "conflict_data": conflict_data,
                "latency_ms": 2
            }
            yield f"data: {json.dumps(final_trace)}\n\n"


            # Persist Cached Assistant Message
            if is_postgres_configured() and db_conv_id:
                try:
                    async with get_db_session() as session:
                        await conversation_repo.add_message(
                            session=session,
                            conversation_id=db_conv_id,
                            role="assistant",
                            content=ans,
                            model="semantic_cache",
                            status="completed",
                            latency_ms=2,
                            metadata_json={
                                "confidence": conf,
                                "conflict_data": conflict_data,
                                "traces": [final_trace],
                            },
                        )
                except Exception as save_cached_err:
                    logger.warning(f"Error persisting cached assistant message: {save_cached_err}")

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
        last_doc_grades = []
        last_retrieved_docs = []
        rewritten_query_str = ""

        async for event in rag_app.astream_events(initial_state, version="v2"):
            kind = event.get("event")
            node_name = event.get("metadata", {}).get("langgraph_node")

            # 1. Live token-by-token streaming from ChatGroq exclusively during synthesis
            tags = event.get("tags") or []
            if kind == "on_chat_model_stream" and "generation_stream" in tags:
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
                    last_retrieved_docs = docs
                    base_msg = f"Retrieved {len(docs)} documents"
                    if expanded:
                        base_msg += f" · {expanded} expanded via Small-to-Big"
                    trace_data["message"] = base_msg
                    trace_data["documents"] = docs
                    trace_data["expanded_count"] = expanded

                elif curr_node == "grade_node":
                    decision = output.get("generation", "unknown")
                    docs = output.get("documents", [])
                    grades = output.get("doc_grades", [])
                    last_doc_grades = grades
                    trace_data["message"] = f"Grading decision: {decision} ({len(docs)} docs relevant)"
                    trace_data["doc_grades"] = grades

                elif curr_node == "web_search_node":
                    docs = output.get("documents", [])
                    grades = output.get("doc_grades", [])
                    if grades:
                        last_doc_grades.extend(grades)
                    trace_data["message"] = f"Performed web search ({len(docs)} sources retrieved)"
                    trace_data["documents"] = docs
                    trace_data["doc_grades"] = grades

                elif curr_node == "rewrite_node":
                    new_q = output.get("question", "")
                    rewritten_query_str = new_q
                    trace_data["message"] = f"Rewrote query to: {new_q}"

                elif curr_node == "generate_node":
                    gen = output.get("generation", "")
                    if gen and not accumulated_answer:
                        accumulated_answer = gen
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

                captured_traces.append(trace_data)
                yield f"data: {json.dumps(trace_data)}\n\n"

        total_latency = int((time.time() - t_start) * 1000)
        import re
        clean_final_answer = re.sub(r'^\s*\{[\s\S]*?"summary":\s*"[^"]*"\s*\}\s*', '', accumulated_answer).strip()

        # ── Persist Assistant Message, Citations & Observability to PostgreSQL ─
        if is_postgres_configured() and db_conv_id and clean_final_answer:
            try:
                async with get_db_session() as session:
                    # 1. Add Assistant Message
                    ast_msg = await conversation_repo.add_message(
                        session=session,
                        conversation_id=db_conv_id,
                        role="assistant",
                        content=clean_final_answer,
                        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
                        status="completed",
                        latency_ms=total_latency,
                        metadata_json={
                            "traces": captured_traces,
                            "confidence": last_confidence,
                            "conflict_data": last_conflict,
                        },
                    )

                    # 2. Add Structured Citations
                    relevant_grades = [g for g in last_doc_grades if g.get("score") == "yes"]
                    for idx, g in enumerate(relevant_grades, start=1):
                        await conversation_repo.add_citation(
                            session=session,
                            message_id=ast_msg.id,
                            citation_index=idx,
                            relevance_score=float(g.get("relevance", 0.9)),
                            rerank_score=float(g.get("relevance", 0.0)),
                            quoted_text=str(g.get("text", ""))[:500],
                        )

                    # 3. Log Retrieval Run
                    await retrieval_repo.log_retrieval_run(
                        session=session,
                        query=question,
                        rewritten_query=rewritten_query_str,
                        retrieval_strategy="hybrid_rrf",
                        cache_hit=False,
                        latency_ms=total_latency,
                        total_results=len(last_retrieved_docs),
                        confidence_score=last_confidence.get("score", 0),
                        conversation_id=db_conv_id,
                        message_id=ast_msg.id,
                    )
            except Exception as save_err:
                logger.warning(f"Error persisting assistant message to PostgreSQL: {save_err}")

        # ── Store high-confidence result in pgvector & local Semantic Cache ──
        if clean_final_answer and last_confidence.get("score", 0) >= 60:
            try:
                import threading
                from main import get_embeddings
                emb = get_embeddings()
                q_vec = emb.embed_query(question)

                # 1. Store in pgvector cache
                if is_postgres_configured():
                    async def _async_store_pg_cache():
                        async with get_db_session() as session:
                            await cache_repo.store_cached_response(
                                session=session,
                                question=question,
                                answer=clean_final_answer,
                                confidence=last_confidence,
                                conflict_data=last_conflict,
                                query_vector=q_vec,
                                source_filter=source_filter,
                            )
                    # Run async task
                    import asyncio
                    asyncio.create_task(_async_store_pg_cache())

                # 2. Store in local JSON cache
                from query_cache import store_cached_response as store_local_cache
                threading.Thread(
                    target=store_local_cache,
                    args=(question, clean_final_answer, last_confidence, last_conflict, emb, source_filter),
                    daemon=True
                ).start()
            except Exception as cache_store_err:
                logger.warning(f"Error storing query cache: {cache_store_err}")

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
        generate_chat_events(req.question, user, req.web_search_enabled, req.source_filter, req.conversation_id),
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
async def get_suggestions(force: bool = False, user: UserProfile = Depends(get_current_user)):
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

    # Only if no cached suggestions exist or force=True, generate from PostgreSQL sample
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


@app.get("/api/glossary")
async def get_glossary_terms(user: UserProfile = Depends(get_current_user)):
    """Returns the list of indexed acronyms and domain entity definitions."""
    try:
        from glossary import get_glossary_for_user, sync_glossary_with_active_sources
        from pathlib import Path

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
            user_id=None if is_admin else user.id,
            active_sources=active_sources if active_sources else set()
        )
        return {"total": len(terms_list), "glossary": terms_list}
    except Exception as e:
        logger.error(f"Error loading glossary: {e}")
        return {"total": 0, "glossary": []}


@app.get("/api/stats")
async def get_stats(user: UserProfile = Depends(get_current_user)):
    is_admin = user.role == "admin"
    async with get_db_session() as session:
        if is_admin:
            doc_stmt = select(func.count(Document.id))
            chunk_stmt = select(func.count(DocumentChunk.id))
        else:
            doc_stmt = select(func.count(Document.id)).where(or_(Document.uploaded_by == user.id, Document.uploaded_by.is_(None), Document.uploaded_by == "default"))
            chunk_stmt = select(func.count(DocumentChunk.id)).join(Document).where(or_(Document.uploaded_by == user.id, Document.uploaded_by.is_(None), Document.uploaded_by == "default"))
        
        doc_count = (await session.execute(doc_stmt)).scalar() or 0
        chunk_count = (await session.execute(chunk_stmt)).scalar() or 0
    
    return {
        "doc_count": doc_count,
        "chunk_count": chunk_count,
        "requests_today": user.requests_today,
        "daily_request_limit": user.daily_request_limit,
        "role": user.role
    }


@app.get("/api/kb/sources")
async def get_kb_sources(all_users: bool = False, user: UserProfile = Depends(get_current_user)):
    from pathlib import Path
    try:
        is_admin = user.role == "admin"
        show_all = all_users and is_admin

        async with get_db_session() as session:
            stmt = select(Document).order_by(Document.created_at.desc())
            if not show_all:
                stmt = stmt.where(or_(Document.uploaded_by == user.id, Document.uploaded_by.is_(None), Document.uploaded_by == "default"))
            
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
                    "source": raw_src,
                    "name": name,
                    "type": doc.source_type or "document",
                    "h1": name,
                    "user_id": doc.uploaded_by or "shared",
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


class DeleteKBRequest(BaseModel):
    source: str | None = None
    ids: list[str] | None = None


@app.post("/api/kb/delete")
async def delete_kb_source(req: DeleteKBRequest, user: UserProfile = Depends(get_current_user)):
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


@app.post("/api/kb/clear")
async def clear_kb(user: UserProfile = Depends(get_current_user)):
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
async def delete_user_account(target_id: str, admin: UserProfile = Depends(require_admin)):
    """Deletes a user account and purges their documents from PostgreSQL."""
    if target_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own administrator account.")
    
    # 1. Delete user files from PostgreSQL
    try:
        async with get_db_session() as session:
            await session.execute(delete(Document).where(Document.uploaded_by == target_id))
    except Exception as e:
        logger.warning(f"Note purging user docs on delete: {e}")

    # 2. Delete user record from auth repository
    admin_delete_user(target_id)
    return {"status": "deleted", "id": target_id}


@app.get("/api/admin/stats")
async def get_admin_stats(admin: UserProfile = Depends(require_admin)):
    """Returns global system metrics."""
    users = admin_list_users()
    total_users = len(users)
    active_users = sum(1 for u in users if u.get("is_active"))
    total_requests_today = sum(u.get("requests_today", 0) for u in users)

    try:
        async with get_db_session() as session:
            doc_count = (await session.execute(select(func.count(Document.id)))).scalar() or 0
            chunk_count = (await session.execute(select(func.count(DocumentChunk.id)))).scalar() or 0
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

