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
from main import build_app, get_settings, ingest_document
from auth import (
    get_current_user,
    get_auth_settings,
    create_access_token,
    register_user,
    authenticate_user,
    RegisterRequest,
    LoginRequest,
    UserProfile,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Ridge API",
    description="High-performance Corrective RAG (CRAG) platform with LangGraph state machine, ChromaDB, FlashRank, and Groq LLMs.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rag_app = build_app()

class ChatRequest(BaseModel):
    question: str
    web_search_enabled: bool = True

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

async def generate_chat_events(question: str, user: UserProfile, web_search_enabled: bool = True) -> AsyncGenerator[str, None]:
    initial_state = {
        "question": question,
        "original_question": question,
        "web_search_enabled": web_search_enabled,
        "documents": [],
        "documents_metadata": [],
        "generation": "",
        "loop_count": 0,
        "past_queries": [],
        "latency_ms": 0,
    }

    try:
        accumulated_answer = ""
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
                "retrieve_node", "grade_node", "web_search_node",
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

                if curr_node == "retrieve_node":
                    docs = output.get("documents", [])
                    trace_data["message"] = f"Retrieved {len(docs)} documents"
                    trace_data["documents"] = docs

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
                    trace_data["message"] = "Generated final answer"
                    trace_data["answer"] = gen
                    if conf:
                        trace_data["confidence"] = conf
                    if conflict_data:
                        trace_data["conflict_data"] = conflict_data

                elif curr_node == "check_hallucination_node":
                    h_grade = output.get("hallucination_grade", {})
                    conf = output.get("confidence", {})
                    trace_data["message"] = f"Hallucination audit: {h_grade.get('grounded', 'yes')}"
                    trace_data["hallucination_grade"] = h_grade
                    if conf:
                        trace_data["confidence"] = conf

                yield f"data: {json.dumps(trace_data)}\n\n"

    except Exception as e:
        logger.error(f"Error during streaming: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

    yield "data: [DONE]\n\n"


@app.post("/ask")
async def ask_question(req: ChatRequest, user: UserProfile = Depends(get_current_user)):
    return StreamingResponse(
        generate_chat_events(req.question, user, req.web_search_enabled),
        media_type="text/event-stream"
    )

@app.post("/ingest")
async def ingest(req: IngestRequest, user: UserProfile = Depends(get_current_user)):
    try:
        result = ingest_document(req.text_or_url)
        return result
    except Exception as e:
        logger.error(f"Error ingesting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), user: UserProfile = Depends(get_current_user)):
    try:
        suffix = ""
        if file.filename:
            _, suffix = os.path.splitext(file.filename)
        
        # Create a temp file to store the upload
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_path = temp_file.name
            
        try:
            result = ingest_document(temp_path, original_filename=file.filename)
            return result
        finally:
            # Cleanup temp file after ingestion
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    except Exception as e:
        logger.error(f"Error processing upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
def status():
    return {"status": "ok"}

@app.get("/api/suggestions")
def get_suggestions(force: bool = False, user: UserProfile = Depends(get_current_user)):
    """
    Returns suggested queries from the persistent suggestions.json cache.
    Does NOT make LLM or Chroma DB calls on refresh.
    Only re-generates when force=True or during document ingestion.
    """
    # 1. Check persistent cache file first
    if not force and os.path.exists("suggestions.json"):
        try:
            with open("suggestions.json", "r") as f:
                data = json.load(f)
                sugs = data.get("suggestions", [])
                if sugs:
                    return {"suggestions": sugs, "cached": True}
        except Exception as e:
            logger.warning(f"Error reading suggestions.json: {e}")

    # 2. Only if no cache file exists or force=True, generate from Chroma sample
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
                generate_suggestions(sample_text)
                if os.path.exists("suggestions.json"):
                    with open("suggestions.json", "r") as f:
                        data = json.load(f)
                        return {"suggestions": data.get("suggestions", []), "cached": False}
    except Exception as e:
        logger.warning(f"Could not generate suggestions: {e}")

    return {"suggestions": [], "empty": True}

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
    chunk_count = vectorstore._collection.count()
    data = vectorstore._collection.get(include=["metadatas"])
    metas = data.get("metadatas", [])
    unique_sources = set(m.get("source") for m in metas if m and m.get("source"))
    doc_count = len(unique_sources) if unique_sources else (1 if chunk_count > 0 else 0)
    return {"doc_count": doc_count, "chunk_count": chunk_count}


@app.get("/api/kb/sources")
def get_kb_sources(user: UserProfile = Depends(get_current_user)):
    from main import get_vectorstore
    from pathlib import Path
    try:
        vectorstore = get_vectorstore()
        coll = vectorstore._collection
        count = coll.count()
        if count == 0:
            return {"total_chunks": 0, "total_sources": 0, "sources": []}

        data = coll.get(limit=count + 100, include=["metadatas", "documents"])
        ids = data.get("ids", [])
        metas = data.get("metadatas", [])
        docs = data.get("documents", [])

        sources_map = {}
        for i, id_ in enumerate(ids):
            meta = metas[i] if i < len(metas) and metas[i] else {}
            raw_src = meta.get("source", "Unknown Source")
            name = Path(raw_src).name if ("/" in raw_src or "\\" in raw_src) else raw_src
            if not name:
                name = raw_src

            if raw_src not in sources_map:
                sources_map[raw_src] = {
                    "source": raw_src,
                    "name": name,
                    "type": meta.get("type", "document"),
                    "h1": meta.get("h1", name),
                    "chunk_count": 0,
                    "sample": docs[i][:180] if i < len(docs) else "",
                    "ids": []
                }
            sources_map[raw_src]["chunk_count"] += 1
            sources_map[raw_src]["ids"].append(id_)

        sources_list = list(sources_map.values())
        return {
            "total_chunks": len(ids),
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
    from main import get_vectorstore
    from pathlib import Path
    try:
        vectorstore = get_vectorstore()
        coll = vectorstore._collection

        if req.ids:
            coll.delete(ids=req.ids)
            remaining_chunks = coll.count()
            return {"status": "deleted", "remaining_chunks": remaining_chunks}

        if req.source:
            count = coll.count()
            if count > 0:
                data = coll.get(limit=count + 100, include=["metadatas"])
                matching_ids = []
                req_name = Path(req.source).name.lower()
                req_norm = req.source.rstrip("/").lower()
                
                for i, m in enumerate(data.get("metadatas", [])):
                    if not m:
                        continue
                    m_src = str(m.get("source", "")).strip()
                    m_norm = m_src.rstrip("/").lower()
                    m_name = Path(m_src).name.lower()
                    
                    if m_src == req.source or m_norm == req_norm or (req_name and m_name == req_name):
                        matching_ids.append(data["ids"][i])

                if matching_ids:
                    coll.delete(ids=matching_ids)
                else:
                    try:
                        coll.delete(where={"source": req.source})
                    except Exception:
                        pass

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
    from main import get_vectorstore
    try:
        vectorstore = get_vectorstore()
        coll = vectorstore._collection
        count = coll.count()
        if count > 0:
            data = coll.get(limit=count + 500)
            ids = data.get("ids", [])
            if ids:
                coll.delete(ids=ids)
    except Exception as e:
        logger.error(f"Error in clear_kb: {e}")

    if os.path.exists("suggestions.json"):
        try:
            os.remove("suggestions.json")
        except Exception:
            pass

    return {"status": "cleared", "remaining_chunks": 0}

# Mount the compiled React frontend
frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.isdir(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
else:
    @app.get("/")
    def index():
        return {"message": "Frontend not built yet. Run 'npm run build' in frontend/"}
