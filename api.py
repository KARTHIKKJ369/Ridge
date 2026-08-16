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

async def generate_chat_events(question: str, user: UserProfile) -> AsyncGenerator[str, None]:
    initial_state = {
        "question": question,
        "original_question": question,
        "documents": [],
        "documents_metadata": [],
        "generation": "",
        "loop_count": 0,
        "past_queries": [],
        "latency_ms": 0,
    }

    try:
        for event in rag_app.stream(initial_state):
            node_name = list(event.keys())[0]
            node_output = event[node_name]
            
            trace_data = {
                "node": node_name,
                "message": f"Finished node {node_name}",
            }
            if "latency_ms" in node_output:
                trace_data["latency_ms"] = node_output["latency_ms"]
            
            if node_name == "retrieve_node":
                docs = node_output.get("documents", [])
                trace_data["message"] = f"Retrieved {len(docs)} documents"
                trace_data["documents"] = docs
            
            elif node_name == "grade_node":
                decision = node_output.get("generation", "unknown")
                docs = node_output.get("documents", [])
                trace_data["message"] = f"Grading decision: {decision} ({len(docs)} docs relevant)"
                trace_data["doc_grades"] = node_output.get("doc_grades", [])
            
            elif node_name == "web_search_node":
                docs = node_output.get("documents", [])
                trace_data["message"] = f"Performed web search"
                trace_data["documents"] = docs

            elif node_name == "rewrite_node":
                new_q = node_output.get("question", "")
                trace_data["message"] = f"Rewrote query to: {new_q}"
            
            elif node_name == "generate_node":
                gen = node_output.get("generation", "")
                trace_data["message"] = "Generated final answer"
                trace_data["answer"] = gen
            
            yield f"data: {json.dumps(trace_data)}\n\n"
            
    except Exception as e:
        logger.error(f"Error during streaming: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
    yield "data: [DONE]\n\n"


@app.post("/ask")
async def ask_question(req: ChatRequest, user: UserProfile = Depends(get_current_user)):
    return StreamingResponse(
        generate_chat_events(req.question, user),
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
            result = ingest_document(temp_path)
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

@app.get("/api/stats")
def get_stats(user: UserProfile = Depends(get_current_user)):
    from main import get_vectorstore
    vectorstore = get_vectorstore()
    chunk_count = vectorstore._collection.count()
    # Rough estimate of docs based on chunks if doc_count metadata isn't unique easily
    return {"doc_count": max(1, chunk_count // 10) if chunk_count > 0 else 0, "chunk_count": chunk_count}

# Mount the compiled React frontend
frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.isdir(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
else:
    @app.get("/")
    def index():
        return {"message": "Frontend not built yet. Run 'npm run build' in frontend/"}
