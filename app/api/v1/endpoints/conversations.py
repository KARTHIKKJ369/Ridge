"""
Conversation & Message History Persistence Endpoints
====================================================
Provides full conversation lifecycle management and message retrieval scoped to the authenticated user.
"""
import time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user, UserProfile
from app.db.database import get_db_session, is_postgres_configured
from app.db.repositories import conversation_repo

router = APIRouter(tags=["Conversations"])


class CreateConversationRequest(BaseModel):
    title: str = "New Research Ascent"


class UpdateConversationRequest(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None


@router.get("/conversations")
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


@router.post("/conversations")
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


@router.get("/conversations/{conv_id}")
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


@router.patch("/conversations/{conv_id}")
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


@router.delete("/conversations/{conv_id}")
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


@router.get("/conversations/{conv_id}/messages")
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
