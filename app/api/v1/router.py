"""
Ridge API v1 Router Aggregator
==============================
Mounts and organizes all sub-module endpoint routers for authentication, chat, documents,
conversations, administration, feedback, and system telemetry.
"""
from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.conversations import router as conversations_router
from app.api.v1.endpoints.chat import router as chat_router
from app.api.v1.endpoints.documents import router as documents_router
from app.api.v1.endpoints.admin import router as admin_router
from app.api.v1.endpoints.feedback import router as feedback_router
from app.api.v1.endpoints.system import router as system_router

api_v1_router = APIRouter()

# Include all sub-routers under API v1
api_v1_router.include_router(auth_router)
api_v1_router.include_router(conversations_router)
api_v1_router.include_router(chat_router)
api_v1_router.include_router(documents_router)
api_v1_router.include_router(admin_router)
api_v1_router.include_router(feedback_router)
api_v1_router.include_router(system_router)
