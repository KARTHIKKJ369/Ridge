import json
import logging
from typing import AsyncGenerator
import os
import tempfile
import shutil
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from main import build_app, get_settings, ingest_document

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

async def generate_chat_events(question: str) -> AsyncGenerator[str, None]:
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
async def ask_question(req: ChatRequest):
    return StreamingResponse(
        generate_chat_events(req.question),
        media_type="text/event-stream"
    )

@app.post("/ingest")
async def ingest(req: IngestRequest):
    try:
        result = ingest_document(req.text_or_url)
        return result
    except Exception as e:
        logger.error(f"Error ingesting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
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
def get_suggestions(force: bool = False):
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
def get_stats():
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
