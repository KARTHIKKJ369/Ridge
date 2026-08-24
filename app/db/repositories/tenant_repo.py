"""
Tenant Repository
=================
Data access layer for multi-tenant organizations, membership stats, and knowledge bases.
"""

import uuid
from typing import Optional
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.tenant import Tenant
from app.db.models.user import User
from app.db.models.document import Document
from app.db.models.knowledge_base import KnowledgeBase
from app.db.models.document_chunk import DocumentChunk
from app.db.repositories.user_repo import DEFAULT_TENANT_ID


async def create_tenant(
    session: AsyncSession,
    name: str,
    slug: str,
    max_users: int = 50,
) -> Tenant:
    """Creates a new organization tenant and provisions its primary knowledge base."""
    slug_clean = slug.strip().lower()
    tenant = Tenant(
        name=name.strip(),
        slug=slug_clean,
        is_active=True,
        max_users=max_users,
    )
    session.add(tenant)
    await session.flush()

    # Automatically provision default knowledge base for the new tenant
    kb = KnowledgeBase(
        tenant_id=tenant.id,
        name=f"{name.strip()} Knowledge Base",
        description=f"Primary shared knowledge base for {name.strip()}",
    )
    session.add(kb)
    await session.flush()

    return tenant


async def get_tenant_by_id(session: AsyncSession, tenant_id: uuid.UUID) -> Optional[Tenant]:
    """Fetch tenant by UUID."""
    res = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    return res.scalar_one_or_none()


async def get_tenant_by_slug(session: AsyncSession, slug: str) -> Optional[Tenant]:
    """Fetch tenant by unique slug."""
    res = await session.execute(select(Tenant).where(Tenant.slug == slug.strip().lower()))
    return res.scalar_one_or_none()


async def list_tenants(session: AsyncSession) -> list[dict]:
    """Lists all tenants with member counts and document counts."""
    res = await session.execute(select(Tenant).order_by(Tenant.created_at.asc()))
    tenants = res.scalars().all()

    result = []
    for t in tenants:
        # Get member count
        u_res = await session.execute(
            select(func.count(User.id)).where(User.tenant_id == t.id)
        )
        user_count = u_res.scalar() or 0

        # Get document count
        d_res = await session.execute(
            select(func.count(Document.id))
            .join(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id)
            .where(KnowledgeBase.tenant_id == t.id)
        )
        doc_count = d_res.scalar() or 0

        result.append({
            "id": str(t.id),
            "name": t.name,
            "slug": t.slug,
            "is_active": t.is_active,
            "max_users": t.max_users,
            "user_count": user_count,
            "doc_count": doc_count,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        })

    return result


async def get_tenant_stats(session: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """Returns detailed storage and usage statistics for a specific tenant."""
    tenant = await get_tenant_by_id(session, tenant_id)
    if not tenant:
        return {}

    # User count
    u_res = await session.execute(
        select(func.count(User.id)).where(User.tenant_id == tenant_id)
    )
    user_count = u_res.scalar() or 0

    # Documents and chunks count
    docs_res = await session.execute(
        select(func.count(Document.id), func.coalesce(func.sum(Document.file_size), 0))
        .join(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id)
        .where(KnowledgeBase.tenant_id == tenant_id)
    )
    doc_count, total_bytes = docs_res.first() or (0, 0)

    # Chunks count
    chunks_res = await session.execute(
        select(func.count(DocumentChunk.id))
        .join(Document, DocumentChunk.document_id == Document.id)
        .join(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id)
        .where(KnowledgeBase.tenant_id == tenant_id)
    )
    chunk_count = chunks_res.scalar() or 0

    return {
        "tenant_id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "is_active": tenant.is_active,
        "max_users": tenant.max_users,
        "current_users": user_count,
        "total_documents": doc_count,
        "total_chunks": chunk_count,
        "storage_bytes": int(total_bytes),
        "storage_mb": round(int(total_bytes) / (1024 * 1024), 2),
    }


async def toggle_tenant_status(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    is_active: bool,
) -> Optional[Tenant]:
    """Activates or deactivates an organization tenant."""
    if tenant_id == DEFAULT_TENANT_ID:
        return None  # Cannot deactivate default tenant
    tenant = await get_tenant_by_id(session, tenant_id)
    if not tenant:
        return None
    tenant.is_active = is_active
    await session.flush()
    return tenant


async def delete_tenant(
    session: AsyncSession,
    tenant_id: uuid.UUID,
) -> bool:
    """Permanently deletes a tenant and all its associated knowledge bases, documents, chunks, and users."""
    if tenant_id == DEFAULT_TENANT_ID:
        return False  # Cannot delete default tenant

    tenant = await get_tenant_by_id(session, tenant_id)
    if not tenant:
        return False

    # 1. Find all KB IDs for this tenant
    kb_res = await session.execute(
        select(KnowledgeBase.id).where(KnowledgeBase.tenant_id == tenant_id)
    )
    kb_ids = kb_res.scalars().all()

    if kb_ids:
        # 2. Find all document IDs in these KBs
        doc_res = await session.execute(
            select(Document.id).where(Document.knowledge_base_id.in_(kb_ids))
        )
        doc_ids = doc_res.scalars().all()

        if doc_ids:
            # Delete chunks
            from sqlalchemy import delete as sql_delete
            await session.execute(
                sql_delete(DocumentChunk).where(DocumentChunk.document_id.in_(doc_ids))
            )
            # Delete documents
            await session.execute(
                sql_delete(Document).where(Document.id.in_(doc_ids))
            )

        # Delete KBs
        from sqlalchemy import delete as sql_delete
        await session.execute(
            sql_delete(KnowledgeBase).where(KnowledgeBase.id.in_(kb_ids))
        )

    # 3. Delete users in this tenant
    from sqlalchemy import delete as sql_delete
    await session.execute(
        sql_delete(User).where(User.tenant_id == tenant_id)
    )

    # 4. Delete tenant
    await session.delete(tenant)
    await session.flush()
    return True


async def get_or_create_tenant_kb(session: AsyncSession, tenant_id: uuid.UUID) -> uuid.UUID:
    """Returns the primary knowledge base ID for a given tenant."""
    res = await session.execute(
        select(KnowledgeBase.id)
        .where(KnowledgeBase.tenant_id == tenant_id)
        .order_by(KnowledgeBase.created_at.asc())
    )
    kb_id = res.scalar_one_or_none()
    if kb_id:
        return kb_id

    # Create if missing
    tenant = await get_tenant_by_id(session, tenant_id)
    t_name = tenant.name if tenant else "Organization"
    kb = KnowledgeBase(
        tenant_id=tenant_id,
        name=f"{t_name} Knowledge Base",
        description=f"Primary knowledge base for {t_name}",
    )
    session.add(kb)
    await session.flush()
    return kb.id


