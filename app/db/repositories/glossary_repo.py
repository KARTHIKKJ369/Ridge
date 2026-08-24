"""
Glossary Repository for Domain Acronyms & Entity Definitions
============================================================
Provides PostgreSQL-backed glossary management, multi-tenant isolation,
and query expansion synchronization.
"""
import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy import select, delete, or_, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.glossary import GlossaryTerm
from app.db.repositories.user_repo import DEFAULT_TENANT_ID


async def index_glossary_terms(
    session: AsyncSession,
    terms_map: dict[str, str],
    source_name: str,
    user_id: str = "default",
    tenant_id: Optional[uuid.UUID] = None,
) -> int:
    """Inserts or updates acronym definitions extracted from text."""
    if not terms_map:
        return 0

    tid = tenant_id or DEFAULT_TENANT_ID
    source_filename = Path(source_name).name if ("/" in source_name or "\\" in source_name) else source_name
    count = 0

    for term, expansion in terms_map.items():
        stmt = (
            pg_insert(GlossaryTerm)
            .values(
                id=uuid.uuid4(),
                tenant_id=tid,
                term=term.strip().upper(),
                expansion=expansion.strip(),
                source_name=source_filename,
                confidence=1.0,
            )
            .on_conflict_do_update(
                index_elements=["tenant_id", "term"],
                set_={
                    "expansion": expansion.strip(),
                    "source_name": source_filename,
                    "updated_at": func.now(),
                },
            )
        )
        await session.execute(stmt)
        count += 1

    await session.flush()
    return count


async def get_glossary_for_user(
    session: AsyncSession,
    user_id: Optional[str] = None,
    active_sources: Optional[set[str]] = None,
    tenant_id: Optional[uuid.UUID] = None,
) -> list[dict]:
    """Retrieves glossary terms scoped by tenant and active sources."""
    tid = tenant_id or DEFAULT_TENANT_ID
    stmt = select(GlossaryTerm).where(GlossaryTerm.tenant_id == tid)

    if active_sources:
        norm_sources = [Path(s).name for s in active_sources if s] + list(active_sources)
        stmt = stmt.where(GlossaryTerm.source_name.in_(norm_sources))

    res = await session.execute(stmt)
    terms = res.scalars().all()

    return [
        {
            "term": t.term,
            "expansion": t.expansion,
            "source": t.source_name,
        }
        for t in terms
    ]


async def remove_source_from_glossary(
    session: AsyncSession,
    source_name: str,
    tenant_id: Optional[uuid.UUID] = None,
) -> int:
    """Removes glossary entries associated with a deleted source."""
    if not source_name:
        return 0

    tid = tenant_id or DEFAULT_TENANT_ID
    src_norm = Path(source_name).name
    stmt = delete(GlossaryTerm).where(
        GlossaryTerm.tenant_id == tid,
        or_(
            GlossaryTerm.source_name == source_name,
            GlossaryTerm.source_name == src_norm,
        ),
    )
    res = await session.execute(stmt)
    return res.rowcount


async def clear_glossary(
    session: AsyncSession,
    tenant_id: Optional[uuid.UUID] = None,
) -> int:
    """Clears all glossary terms for the tenant."""
    tid = tenant_id or DEFAULT_TENANT_ID
    stmt = delete(GlossaryTerm).where(GlossaryTerm.tenant_id == tid)
    res = await session.execute(stmt)
    return res.rowcount
