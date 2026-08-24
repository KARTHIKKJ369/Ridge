"""
Conversation, Message & Citation Repository
===========================================
Provides CRUD operations for persistent chat sessions, message histories,
and structured citation provenance.
"""
import uuid
import time
from typing import Optional
from datetime import datetime, timezone

from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.db.models.conversation import Conversation
from app.db.models.message import Message
from app.db.models.citation import MessageCitation
from app.db.models.tenant import Tenant
from app.db.repositories.user_repo import DEFAULT_TENANT_ID

async def ensure_user_exists(session: AsyncSession, user_id: str, tenant_id: uuid.UUID) -> None:

    """Ensures a user record exists in PostgreSQL to satisfy foreign key constraints."""
    user = await session.get(User, user_id)
    if not user:
        # Create a stub user record for this user_id
        uname = user_id.replace("usr_", "") if user_id.startswith("usr_") else user_id
        new_user = User(
            id=user_id,
            tenant_id=tenant_id,
            username=f"user_{uname}",
            email=f"{uname}@ridge.local",
            name=f"Climber {uname}",
            password_hash="stub_hash",
            salt="stub_salt",
            role="user",
        )
        session.add(new_user)
        await session.flush()


async def create_conversation(
    session: AsyncSession,
    user_id: str,
    title: str = "New Research Ascent",
    tenant_id: Optional[uuid.UUID] = None,
) -> Conversation:
    tid = tenant_id or DEFAULT_TENANT_ID
    await ensure_user_exists(session, user_id, tid)

    conv = Conversation(
        id=uuid.uuid4(),
        tenant_id=tid,
        user_id=user_id,
        title=title.strip() or "New Research Ascent",
        summary="",
    )
    session.add(conv)
    await session.flush()
    return conv



async def list_conversations(
    session: AsyncSession,
    user_id: str,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    stmt = (
        select(Conversation)
        .where(
            Conversation.user_id == user_id,
            Conversation.archived_at.is_(None),
        )
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    res = await session.execute(stmt)
    convs = res.scalars().all()
    return [
        {
            "id": str(c.id),
            "title": c.title,
            "summary": c.summary,
            "created_at": int(c.created_at.timestamp() * 1000) if c.created_at else int(time.time() * 1000),
            "updated_at": int(c.updated_at.timestamp() * 1000) if c.updated_at else int(time.time() * 1000),
        }
        for c in convs
    ]


async def get_conversation(
    session: AsyncSession,
    conversation_id: str,
    user_id: Optional[str] = None,
) -> Optional[Conversation]:
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except (ValueError, TypeError):
        return None

    stmt = (
        select(Conversation)
        .options(
            selectinload(Conversation.messages).selectinload(Message.citations)
        )
        .where(Conversation.id == conv_uuid)
    )
    if user_id and user_id not in ("admin", "system"):
        stmt = stmt.where(Conversation.user_id == user_id)

    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def update_conversation(
    session: AsyncSession,
    conversation_id: str,
    user_id: str,
    title: Optional[str] = None,
    summary: Optional[str] = None,
) -> bool:
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except (ValueError, TypeError):
        return False

    values = {"updated_at": datetime.now(timezone.utc)}
    if title is not None:
        values["title"] = title.strip()
    if summary is not None:
        values["summary"] = summary.strip()

    stmt = (
        update(Conversation)
        .where(Conversation.id == conv_uuid, Conversation.user_id == user_id)
        .values(**values)
    )
    res = await session.execute(stmt)
    return res.rowcount > 0


async def delete_conversation(
    session: AsyncSession,
    conversation_id: str,
    user_id: str,
) -> bool:
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except (ValueError, TypeError):
        return False

    stmt = delete(Conversation).where(
        Conversation.id == conv_uuid,
        Conversation.user_id == user_id,
    )
    res = await session.execute(stmt)
    return res.rowcount > 0


async def add_message(
    session: AsyncSession,
    conversation_id: str,
    role: str,
    content: str,
    model: str = "",
    status: str = "completed",
    token_count: int = 0,
    latency_ms: int = 0,
    metadata_json: Optional[dict] = None,
) -> Message:
    conv_uuid = uuid.UUID(conversation_id)
    msg = Message(
        id=uuid.uuid4(),
        conversation_id=conv_uuid,
        role=role,
        content=content,
        model=model,
        status=status,
        token_count=token_count,
        latency_ms=latency_ms,
        metadata_json=metadata_json or {},
    )
    session.add(msg)
    # Touch conversation updated_at
    await session.execute(
        update(Conversation)
        .where(Conversation.id == conv_uuid)
        .values(updated_at=datetime.now(timezone.utc))
    )
    await session.flush()
    return msg


async def add_citation(
    session: AsyncSession,
    message_id: uuid.UUID,
    citation_index: int,
    relevance_score: float = 0.0,
    rerank_score: float = 0.0,
    quoted_text: str = "",
    chunk_id: Optional[uuid.UUID] = None,
) -> MessageCitation:
    citation = MessageCitation(
        id=uuid.uuid4(),
        message_id=message_id,
        chunk_id=chunk_id,
        citation_index=citation_index,
        relevance_score=relevance_score,
        rerank_score=rerank_score,
        quoted_text=quoted_text,
    )
    session.add(citation)
    await session.flush()
    return citation


async def get_conversation_messages(
    session: AsyncSession,
    conversation_id: str,
    user_id: Optional[str] = None,
) -> list[dict]:
    conv = await get_conversation(session, conversation_id, user_id=user_id)
    if not conv:
        return []

    result = []
    for m in conv.messages:
        citations_data = [
            {
                "index": c.citation_index,
                "relevance_score": c.relevance_score,
                "rerank_score": c.rerank_score,
                "quoted_text": c.quoted_text,
                "chunk_id": str(c.chunk_id) if c.chunk_id else None,
            }
            for c in m.citations
        ]
        meta = dict(m.metadata_json or {})
        msg_dict = {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "model": m.model,
            "status": m.status,
            "token_count": m.token_count,
            "latency_ms": m.latency_ms,
            "traces": meta.get("traces", []),
            "confidence": meta.get("confidence"),
            "conflict_data": meta.get("conflict_data"),
            "citations": citations_data,
            "timestamp": m.created_at.strftime("%I:%M %p") if m.created_at else "",
            "createdAt": int(m.created_at.timestamp() * 1000) if m.created_at else int(time.time() * 1000),
        }
        result.append(msg_dict)

    return result
