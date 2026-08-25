"""
User Feedback & Accuracy Inquiry Endpoints
==========================================
Allows authenticated climbers to submit bug reports, accuracy reviews, and feature requests.
"""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from auth import get_current_user, UserProfile
from app.db.database import get_db_session
from app.db.repositories import feedback_repo

router = APIRouter(tags=["Feedback"])


class CreateFeedbackRequest(BaseModel):
    category: str = "general"  # accuracy, bug, feature, citation, general
    message: str = Field(..., min_length=3, max_length=5000)
    conversation_id: Optional[str] = ""


@router.post("/feedback")
async def submit_feedback_endpoint(
    req: CreateFeedbackRequest,
    user: UserProfile = Depends(get_current_user)
):
    """Submits a feedback or accuracy inquiry from a climber."""
    async with get_db_session() as session:
        t_uuid = uuid.UUID(user.tenant_id)
        fb = await feedback_repo.create_feedback(
            session=session,
            user_id=user.id,
            username=user.username or user.name or "climber",
            tenant_id=t_uuid,
            category=req.category,
            message=req.message,
            conversation_id=req.conversation_id or "",
        )
        await session.commit()
        return {
            "status": "created",
            "id": str(fb.id),
            "category": fb.category,
            "message": fb.message,
            "created_at": fb.created_at.isoformat(),
        }


@router.get("/feedback/mine")
async def list_my_feedback_endpoint(
    user: UserProfile = Depends(get_current_user)
):
    """Returns feedback and status resolutions for the authenticated climber."""
    async with get_db_session() as session:
        items = await feedback_repo.list_user_feedback(session, user.id)
        return {"feedback": items}
