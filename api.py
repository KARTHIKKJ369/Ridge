"""
Ridge: High-Performance Corrective RAG (CRAG) API
=================================================
FastAPI backend orchestrating LangGraph state machines, pgvector HNSW hybrid retrieval,
multi-tenant security, and real-time streaming intelligence.
"""
import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.db.database import (
    init_db as init_postgres_db,
    is_postgres_configured,
)
from app.api.v1.router import api_v1_router
from app.api.v1.endpoints.chat import generate_chat_events, ask_question_endpoint, ChatRequest
from app.api.v1.endpoints.documents import upload_file_endpoint, ingest_endpoint, IngestRequest
from app.api.v1.endpoints.system import health
from app.api.v1.endpoints.admin import require_admin, require_superadmin
from app.api.v1.endpoints.conversations import CreateConversationRequest, UpdateConversationRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes PostgreSQL + pgvector schema and async resources on startup."""
    if is_postgres_configured():
        try:
            await init_postgres_db()
            logger.info("✓ PostgreSQL & pgvector schema verified and initialized on startup.")
        except Exception as e:
            logger.warning(f"Note on DB startup init: {e}")
    yield


# Rate Limiter — keyed by client IP
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Ridge API",
    description="High-performance Corrective RAG (CRAG) platform with LangGraph state machine, PostgreSQL/pgvector, FlashRank, and Groq LLMs.",
    version="2.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Configuration
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

# Mount API Routers
app.include_router(api_v1_router, prefix="/api")
app.include_router(api_v1_router, prefix="/api/v1")

# Backward-Compatible Root Endpoints
app.add_api_route("/ask", ask_question_endpoint, methods=["POST"], include_in_schema=False)
app.add_api_route("/upload", upload_file_endpoint, methods=["POST"], include_in_schema=False)
app.add_api_route("/ingest", ingest_endpoint, methods=["POST"], include_in_schema=False)
app.add_api_route("/health", health, methods=["GET"], include_in_schema=False)
app.add_api_route("/status", health, methods=["GET"], include_in_schema=False)

from app.api.v1.endpoints.chat import websocket_chat_endpoint
app.add_api_websocket_route("/ws/chat", websocket_chat_endpoint)
app.add_api_websocket_route("/ws/ask", websocket_chat_endpoint)


# Mount the compiled React frontend static files
frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.isdir(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
else:
    @app.get("/")
    def index():
        return {"message": "Ridge API is running. Build frontend with 'npm run build' inside frontend/ to serve the UI."}
