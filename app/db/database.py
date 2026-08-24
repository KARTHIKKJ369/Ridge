"""
Ridge Database Engine, Session Management & Connection Pooling
==============================================================
Provides asynchronous and synchronous SQLAlchemy sessions for PostgreSQL with pgvector.
"""

import os
import uuid
import logging
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text, create_engine, select
from sqlalchemy.orm import sessionmaker


load_dotenv()

logger = logging.getLogger(__name__)

# Base Declarative Model
class Base(DeclarativeBase):
    pass


def get_database_url(sync: bool = False) -> str:
    """
    Returns the database URL formatted for asyncpg (default) or psycopg2/sync.
    """
    raw_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://ridge:ridge@localhost:5433/ridge"
    )
    if sync:
        sync_url = os.getenv("DATABASE_URL_SYNC")
        if sync_url:
            return sync_url
        # Convert async scheme to sync
        if raw_url.startswith("postgresql+asyncpg://"):
            return raw_url.replace("postgresql+asyncpg://", "postgresql://")
        if raw_url.startswith("postgres://"):
            return raw_url.replace("postgres://", "postgresql://")
        return raw_url

    # Asyncpg URL normalization
    if raw_url.startswith("postgres://"):
        return raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif raw_url.startswith("postgresql://") and not raw_url.startswith("postgresql+"):
        return raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return raw_url


def is_postgres_configured() -> bool:
    """Checks if a valid DATABASE_URL is defined."""
    url = os.getenv("DATABASE_URL")
    return bool(url and ("postgres" in url or "localhost" in url or "5432" in url or "5433" in url))


from sqlalchemy.pool import NullPool

# Asynchronous Engine & Session Factory
DATABASE_URL = get_database_url(sync=False)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    poolclass=NullPool,
    pool_pre_ping=True,
)


async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager for database sessions."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Dependency for database sessions."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# Synchronous Engine for Alembic & Scripts
def get_sync_engine():
    sync_url = get_database_url(sync=True)
    return create_engine(sync_url, pool_pre_ping=True)


def get_sync_session():
    sync_engine = get_sync_engine()
    Session = sessionmaker(bind=sync_engine)
    return Session()


async def init_db() -> None:
    """
    Initializes PostgreSQL extensions (pgvector) and creates tables if needed.
    """
    try:
        async with engine.begin() as conn:
            # Enable pgvector extension
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            # Enable UUID extension
            await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
            # Enable pg_trgm for fuzzy search if needed
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
            # Create tables
            await conn.run_sync(Base.metadata.create_all)
            
            # Idempotent Column Migrations for Multi-Tenant Support
            await conn.execute(text("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS slug VARCHAR(64) DEFAULT 'default' NOT NULL;"))
            await conn.execute(text("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE NOT NULL;"))
            await conn.execute(text("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS max_users INTEGER DEFAULT 50 NOT NULL;"))
            await conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS is_shared BOOLEAN DEFAULT FALSE NOT NULL;"))
            await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_tenants_slug ON tenants(slug);"))

            logger.info("  [PostgreSQL] Database tables & extensions initialized successfully.")

        # Seed default tenant and KB
        async with get_db_session() as session:
            from app.db.models.tenant import Tenant
            from app.db.models.knowledge_base import KnowledgeBase
            from app.db.repositories.user_repo import DEFAULT_TENANT_ID

            DEFAULT_KB_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
            t_res = await session.execute(select(Tenant).where(Tenant.id == DEFAULT_TENANT_ID))
            existing_tenant = t_res.scalar_one_or_none()
            if not existing_tenant:
                session.add(Tenant(
                    id=DEFAULT_TENANT_ID,
                    name="Default Tenant",
                    slug="default",
                    is_active=True,
                    max_users=999999,
                ))
                await session.flush()
            else:
                if not getattr(existing_tenant, "slug", None):
                    existing_tenant.slug = "default"
                    await session.flush()

            kb_res = await session.execute(select(KnowledgeBase).where(KnowledgeBase.id == DEFAULT_KB_ID))
            if not kb_res.scalar_one_or_none():
                session.add(KnowledgeBase(
                    id=DEFAULT_KB_ID,
                    tenant_id=DEFAULT_TENANT_ID,
                    name="Default Knowledge Base",
                    description="Primary system knowledge base",
                ))
                await session.flush()
    except Exception as e:
        logger.error(f"  [PostgreSQL] Database initialization warning: {e}")


