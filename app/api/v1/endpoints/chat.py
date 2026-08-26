"""
Streaming Chat & Corrective RAG Orchestration Endpoints
=======================================================
Executes the LangGraph state machine with pgvector semantic cache lookup,
token streaming, node trace events, persistent message recording,
authoritative citations mapping, and bidirectional WebSocket streaming.
"""
import os
import json
import time
import re
import uuid
import logging
import asyncio
from typing import AsyncGenerator, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

from main import get_app
from auth import get_current_user, check_and_increment_user_usage, UserProfile, decode_access_token
from app.db.database import get_db_session, is_postgres_configured
from app.db.repositories import conversation_repo, cache_repo, retrieval_repo, user_repo
from app.graph.observability import get_langfuse_handler, flush_langfuse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Chat"])

rag_app = get_app()


class ChatRequest(BaseModel):
    question: str
    web_search_enabled: bool = True
    source_filter: str | None = None
    conversation_id: str | None = None


def compute_authoritative_citations(
    clean_final_answer: str,
    last_doc_grades: list[dict],
) -> list[dict]:
    """
    Computes an authoritative list of grounded citation badges referenced in the synthesized answer.
    """
    cited_nums = [int(n) for n in re.findall(r"\[(\d+)\]", clean_final_answer)]
    cited_indices = set(cited_nums)

    relevant_grades = [g for g in last_doc_grades if g.get("score") == "yes"]
    if not relevant_grades:
        relevant_grades = last_doc_grades

    authoritative = []
    for idx in sorted(cited_indices):
        if 1 <= idx <= len(relevant_grades):
            g = relevant_grades[idx - 1]
            authoritative.append({
                "index": idx,
                "source": g.get("source", f"Source [{idx}]"),
                "breadcrumb": g.get("breadcrumb", ""),
                "score": g.get("score", "yes"),
                "rationale": g.get("rationale", "Verified by CRAG grading pipeline"),
                "text": g.get("text", ""),
                "relevance": float(g.get("relevance", 0.95)),
                "chunk_id": g.get("chunk_id", ""),
            })
        elif 1 <= idx <= len(last_doc_grades):
            g = last_doc_grades[idx - 1]
            authoritative.append({
                "index": idx,
                "source": g.get("source", f"Source [{idx}]"),
                "breadcrumb": g.get("breadcrumb", ""),
                "score": g.get("score", "yes"),
                "rationale": g.get("rationale", ""),
                "text": g.get("text", ""),
                "relevance": float(g.get("relevance", 0.85)),
                "chunk_id": g.get("chunk_id", ""),
            })

    return authoritative


async def generate_chat_events(
    question: str,
    user: UserProfile,
    web_search_enabled: bool = True,
    source_filter: str | None = None,
    conversation_id: str | None = None,
) -> AsyncGenerator[str, None]:
    t_start = time.time()
    db_conv_id = conversation_id
    captured_traces = []

    # ── Persistent Conversation & User Message Initialization ────────────────
    if is_postgres_configured():
        try:
            t_uuid = uuid.UUID(user.tenant_id) if user.tenant_id else None
            async with get_db_session() as session:
                if not db_conv_id:
                    # Auto-create new conversation
                    title_candidate = question.strip()[:60]
                    new_conv = await conversation_repo.create_conversation(
                        session, user_id=user.id, title=title_candidate or "New Research Ascent", tenant_id=t_uuid
                    )
                    db_conv_id = str(new_conv.id)
                else:
                    # Verify existence
                    existing_conv = await conversation_repo.get_conversation(session, db_conv_id, user_id=user.id)
                    if not existing_conv:
                        new_conv = await conversation_repo.create_conversation(
                            session, user_id=user.id, title=question.strip()[:60] or "New Research Ascent", tenant_id=t_uuid
                        )
                        db_conv_id = str(new_conv.id)

                # Persist User Message
                await conversation_repo.add_message(
                    session=session,
                    conversation_id=db_conv_id,
                    role="user",
                    content=question,
                    status="completed",
                )
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

        if cached:
            match_pct = int(round(cached.get("similarity", 0.99) * 100))
            yield f"data: {json.dumps({'type': 'trace', 'node': 'cache_hit_node', 'message': f'⚡ Semantic Cache Hit ({match_pct}% query match) — Instant Verified Ascent', 'latency_ms': 2})}\n\n"
            
            ans = re.sub(r'^\s*\{[\s\S]*?"summary":\s*"[^"]*"\s*\}\s*', '', cached.get("answer", "")).strip()
            yield f"data: {json.dumps({'type': 'token', 'token': ans})}\n\n"
            
            conf = cached.get("confidence") or {
                "score": 98,
                "level": "HIGH",
                "breakdown": {
                    "grader_consensus": 100.0,
                    "source_trust": "Semantic Vector Cache (Verified)",
                    "relevant_chunks": 1,
                    "reformulation_loops": 0,
                    "faithfulness": "Verified Cache Hit"
                }
            }
            conflict_data = cached.get("conflict_data") or {"detected": False, "summary": "", "sources": []}
            final_trace = {
                "type": "trace",
                "node": "cache_hit_node",
                "message": f"Verified match from semantic vector cache ({match_pct}%)",
                "latency_ms": 2,
                "confidence": conf,
                "conflict_data": conflict_data,
                "answer": ans,
            }
            yield f"data: {json.dumps(final_trace)}\n\n"

            # Check for citations in cached answer
            cached_citations = compute_authoritative_citations(ans, [])
            if cached_citations:
                yield f"data: {json.dumps({'type': 'citations', 'citations': cached_citations})}\n\n"

            # Persist Cached Message to PostgreSQL
            if is_postgres_configured() and db_conv_id and ans:
                try:
                    async with get_db_session() as session:
                        await conversation_repo.add_message(
                            session=session,
                            conversation_id=db_conv_id,
                            role="assistant",
                            content=ans,
                            model="pgvector-semantic-cache",
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
        "tenant_id": user.tenant_id,
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
        rewritten_query_str = ""

        # Langfuse tracing handler
        lf_handler = get_langfuse_handler()
        stream_config = {}
        if lf_handler:
            stream_config["callbacks"] = [lf_handler]

        async for event in rag_app.astream_events(initial_state, version="v2", config=stream_config if stream_config else None):
            kind = event.get("event")

            # 1. Live token streaming from Chat LLM during generation
            tags = event.get("tags") or []
            if kind == "on_chat_model_stream" and "generation_stream" in tags:
                chunk = event.get("data", {}).get("chunk")
                raw_c = chunk.content if hasattr(chunk, "content") else chunk
                if isinstance(raw_c, list):
                    parts = []
                    for p in raw_c:
                        if isinstance(p, str):
                            parts.append(p)
                        elif isinstance(p, dict) and "text" in p:
                            parts.append(str(p["text"]))
                        elif hasattr(p, "text"):
                            parts.append(str(p.text))
                        else:
                            parts.append(str(p))
                    content = "".join(parts)
                elif not isinstance(raw_c, str):
                    content = str(raw_c) if raw_c is not None else ""
                else:
                    content = raw_c

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
                    if isinstance(gen, list):
                        gen = "".join(str(p) for p in gen)
                    elif not isinstance(gen, str):
                        gen = str(gen) if gen is not None else ""
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
        clean_final_answer = re.sub(r'^\s*\{[\s\S]*?"summary":\s*"[^"]*"\s*\}\s*', '', accumulated_answer).strip()

        # ── 3. Authoritative Citation Mapping Event ────────────────────────────
        authoritative_cits = compute_authoritative_citations(clean_final_answer, last_doc_grades)
        if authoritative_cits:
            yield f"data: {json.dumps({'type': 'citations', 'citations': authoritative_cits})}\n\n"

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
                            "citations": authoritative_cits,
                        },
                    )

                    # 2. Add Structured Citations
                    for c in authoritative_cits:
                        await conversation_repo.add_citation(
                            session=session,
                            message_id=ast_msg.id,
                            citation_index=c.get("index", 1),
                            relevance_score=float(c.get("relevance", 0.9)),
                            rerank_score=float(c.get("relevance", 0.0)),
                            quoted_text=str(c.get("text", ""))[:500],
                        )

                    # 3. Log Retrieval Run
                    relevant_grades = [g for g in last_doc_grades if g.get("score") == "yes"]
                    await retrieval_repo.log_retrieval_run(
                        session=session,
                        query=question,
                        rewritten_query=rewritten_query_str,
                        retrieval_strategy="hybrid_rrf",
                        cache_hit=False,
                        latency_ms=total_latency,
                        results_list=[
                            {
                                "dense_score": float(g.get("relevance", 0.8)),
                                "sparse_score": float(g.get("relevance", 0.8)),
                                "rrf_score": 1.0 / (60 + i + 1),
                                "rerank_score": float(g.get("relevance", 0.8)),
                                "final_rank": i + 1,
                                "selected": True,
                            }
                            for i, g in enumerate(relevant_grades[:6])
                        ],
                        conversation_id=db_conv_id,
                        message_id=ast_msg.id,
                    )

            except Exception as save_err:
                logger.warning(f"Error persisting assistant message to PostgreSQL: {save_err}")

        # ── Store high-confidence result in pgvector ──
        if clean_final_answer and last_confidence.get("score", 0) >= 60:
            try:
                from main import get_embeddings
                emb = get_embeddings()
                q_vec = emb.embed_query(question)

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
                    asyncio.create_task(_async_store_pg_cache())

            except Exception as cache_store_err:
                logger.warning(f"Error storing query cache: {cache_store_err}")

    except Exception as e:
        logger.error(f"Error during streaming: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
    finally:
        flush_langfuse()

    yield "data: [DONE]\n\n"


@router.post("/chat")
@router.post("/ask")
@limiter.limit("15/minute")
async def ask_question_endpoint(request: Request, req: ChatRequest, user: UserProfile = Depends(get_current_user)):
    """Streaming chat endpoint for interactive Corrective RAG answers. Rate limited to 15 requests/minute per IP."""
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


@router.websocket("/ws/chat")
@router.websocket("/ws/ask")
async def websocket_chat_endpoint(websocket: WebSocket):
    """
    Bidirectional WebSocket endpoint for real-time chat streaming, live traces,
    authoritative citations, and generation cancellation signals.
    """
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
            except Exception:
                await websocket.send_json({"error": "Invalid JSON format."})
                continue

            action = payload.get("action", "ask")
            if action == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            question = payload.get("question", "").strip()
            if not question:
                await websocket.send_json({"error": "Question parameter is required."})
                continue

            # Token authentication from query params or payload
            token = payload.get("token") or websocket.query_params.get("token")
            user_profile = None
            if token:
                try:
                    tok_data = decode_access_token(token)
                    if tok_data:
                        async with get_db_session() as session:
                            user_db = await user_repo.get_user_by_id(session, tok_data.get("sub", ""))
                            if user_db:
                                user_profile = UserProfile(
                                    id=user_db.id,
                                    username=user_db.username,
                                    email=user_db.email,
                                    name=user_db.name,
                                    role=user_db.role,
                                    is_active=user_db.is_active,
                                    tenant_id=str(user_db.tenant_id) if user_db.tenant_id else None,
                                    tenant_slug=user_db.tenant.slug if user_db.tenant else None,
                                    tenant_name=user_db.tenant.name if user_db.tenant else None,
                                    is_guest=False,
                                )
                except Exception as auth_err:
                    logger.warning(f"WebSocket auth warning: {auth_err}")

            if not user_profile:
                user_profile = UserProfile(
                    id="guest",
                    username="guest",
                    email="guest@ridge.ai",
                    name="Guest Climber",
                    role="guest",
                    is_active=True,
                    tenant_id=None,
                    tenant_slug="public",
                    tenant_name="Public Ridge",
                    is_guest=True,
                )

            web_search_enabled = payload.get("web_search_enabled", True)
            source_filter = payload.get("source_filter")
            conversation_id = payload.get("conversation_id")

            # Stream events over WebSocket
            async for raw_sse in generate_chat_events(
                question=question,
                user=user_profile,
                web_search_enabled=web_search_enabled,
                source_filter=source_filter,
                conversation_id=conversation_id,
            ):
                if raw_sse.startswith("data: "):
                    content = raw_sse[6:].strip()
                    if content == "[DONE]":
                        await websocket.send_json({"type": "done"})
                    else:
                        try:
                            ev_json = json.loads(content)
                            await websocket.send_json(ev_json)
                        except Exception:
                            await websocket.send_text(content)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected.")
    except Exception as ws_err:
        logger.error(f"WebSocket session error: {ws_err}")
