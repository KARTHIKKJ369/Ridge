"""
Feedback Repository
Handles CRUD and status resolution for user feedback and accuracy reports.
"""
import uuid
from typing import Optional, List, Dict, Any
from sqlalchemy import select, delete, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.feedback import Feedback
from app.db.models.tenant import Tenant


async def create_feedback(
    session: AsyncSession,
    user_id: Optional[str],
    username: str,
    tenant_id: uuid.UUID,
    category: str,
    message: str,
    conversation_id: str = "",
) -> Feedback:
    """Creates a new feedback item from a climber."""
    fb = Feedback(
        user_id=user_id,
        username=username,
        tenant_id=tenant_id,
        category=category,
        message=message,
        conversation_id=conversation_id,
        status="open",
    )
    session.add(fb)
    await session.flush()
    return fb


async def list_feedback(
    session: AsyncSession,
    tenant_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Lists feedback items with tenant isolation and optional filtering."""
    query = (
        select(Feedback, Tenant.name.label("tenant_name"), Tenant.slug.label("tenant_slug"))
        .outerjoin(Tenant, Feedback.tenant_id == Tenant.id)
    )

    if tenant_id:
        query = query.where(Feedback.tenant_id == tenant_id)
    if status and status != "all":
        query = query.where(Feedback.status == status)
    if category and category != "all":
        query = query.where(Feedback.category == category)

    query = query.order_by(desc(Feedback.created_at)).limit(limit).offset(offset)
    res = await session.execute(query)
    rows = res.all()

    items = []
    for fb, t_name, t_slug in rows:
        items.append({
            "id": str(fb.id),
            "user_id": fb.user_id,
            "username": fb.username,
            "tenant_id": str(fb.tenant_id),
            "tenant_name": t_name or "Default",
            "tenant_slug": t_slug or "default",
            "category": fb.category,
            "message": fb.message,
            "conversation_id": fb.conversation_id,
            "status": fb.status,
            "admin_notes": fb.admin_notes,
            "resolved_by": fb.resolved_by,
            "created_at": fb.created_at.isoformat() if fb.created_at else "",
            "updated_at": fb.updated_at.isoformat() if fb.updated_at else "",
        })
    return items


async def get_feedback_by_id(
    session: AsyncSession,
    feedback_id: uuid.UUID,
) -> Optional[Feedback]:
    """Retrieves a single feedback item by ID."""
    res = await session.execute(select(Feedback).where(Feedback.id == feedback_id))
    return res.scalar_one_or_none()


async def update_feedback_status(
    session: AsyncSession,
    feedback_id: uuid.UUID,
    status: str,
    admin_notes: Optional[str] = None,
    resolved_by: Optional[str] = None,
) -> Optional[Feedback]:
    """Updates status (open/in_review/resolved) and adds optional admin resolution notes."""
    fb = await get_feedback_by_id(session, feedback_id)
    if not fb:
        return None

    fb.status = status
    if admin_notes is not None:
        fb.admin_notes = admin_notes
    if resolved_by is not None:
        fb.resolved_by = resolved_by

    await session.flush()
    return fb


async def delete_feedback(
    session: AsyncSession,
    feedback_id: uuid.UUID,
) -> bool:
    """Permanently deletes a feedback item."""
    fb = await get_feedback_by_id(session, feedback_id)
    if not fb:
        return False
    await session.delete(fb)
    await session.flush()
    return True


async def list_user_feedback(
    session: AsyncSession,
    user_id: str,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Lists feedback submitted by a specific user."""
    query = (
        select(Feedback)
        .where(Feedback.user_id == user_id)
        .order_by(desc(Feedback.created_at))
        .limit(limit)
    )
    res = await session.execute(query)
    rows = res.scalars().all()

    return [
        {
            "id": str(fb.id),
            "category": fb.category,
            "message": fb.message,
            "conversation_id": fb.conversation_id,
            "status": fb.status,
            "admin_notes": fb.admin_notes,
            "resolved_by": fb.resolved_by,
            "created_at": fb.created_at.isoformat() if fb.created_at else "",
            "updated_at": fb.updated_at.isoformat() if fb.updated_at else "",
        }
        for fb in rows
    ]
