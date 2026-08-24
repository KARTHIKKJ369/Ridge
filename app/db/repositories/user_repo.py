"""
User & Authentication Repository
================================
Provides database operations for users, roles, rate-limits, and usage tracking.
Supports compatibility with existing salted PBKDF2-SHA256 password hashing.
"""
import uuid
import time
import secrets
import hashlib
from datetime import datetime, timezone, date
from typing import Optional

from sqlalchemy import select, update, delete, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.db.models.user_usage import UserUsage
from app.db.models.tenant import Tenant
from app.db.database import get_db_session

DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def hash_password(password: str, salt: str) -> str:
    """PBKDF2-SHA256 hash compatible with existing Ridge auth."""
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    ).hex()


async def get_or_create_default_tenant(session: AsyncSession) -> uuid.UUID:
    result = await session.execute(select(Tenant).where(Tenant.id == DEFAULT_TENANT_ID))
    tenant = result.scalar_one_or_none()
    if not tenant:
        tenant = Tenant(id=DEFAULT_TENANT_ID, name="Default Tenant")
        session.add(tenant)
        await session.flush()
    return tenant.id


async def get_user_by_id(session: AsyncSession, user_id: str) -> Optional[User]:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_username_or_email(session: AsyncSession, identifier: str) -> Optional[User]:
    ident = identifier.strip().lower()
    result = await session.execute(
        select(User).where((User.username == ident) | (User.email == ident))
    )
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    username: str,
    email: str,
    password: str,
    name: Optional[str] = None,
    role: str = "user",
    daily_request_limit: int = 50,
    tenant_id: Optional[uuid.UUID] = None,
) -> User:
    tid = tenant_id or await get_or_create_default_tenant(session)
    salt = secrets.token_hex(16)
    pw_hash = hash_password(password, salt)
    user_id = f"usr_{secrets.token_hex(8)}"

    user = User(
        id=user_id,
        tenant_id=tid,
        username=username.strip().lower(),
        email=email.strip().lower(),
        name=name.strip() if name else username.strip(),
        password_hash=pw_hash,
        salt=salt,
        role=role,
        is_active=True,
        daily_request_limit=daily_request_limit,
    )
    session.add(user)
    await session.flush()
    return user


async def verify_user_credentials(
    session: AsyncSession,
    identifier: str,
    password: str,
) -> Optional[User]:
    user = await get_user_by_username_or_email(session, identifier)
    if not user:
        return None

    test_hash = hash_password(password, user.salt)
    if not secrets.compare_digest(user.password_hash, test_hash):
        return None

    return user


async def check_and_increment_usage(
    session: AsyncSession,
    user_id: str,
) -> tuple[bool, int, int]:
    """
    Atomically checks user daily request quota and increments count.
    Returns (allowed: bool, current_count: int, daily_limit: int).
    """
    user = await get_user_by_id(session, user_id)
    if not user:
        # Default/guest
        return True, 1, 50

    if not user.is_active:
        return False, 0, user.daily_request_limit

    if user.role == "admin":
        today = datetime.now(timezone.utc).date()
        stmt = (
            pg_insert(UserUsage)
            .values(user_id=user_id, usage_date=today, request_count=1)
            .on_conflict_do_update(
                index_elements=["user_id", "usage_date"],
                set_={"request_count": UserUsage.request_count + 1},
            )
            .returning(UserUsage.request_count)
        )
        res = await session.execute(stmt)
        count = res.scalar_one()
        return True, count, 999999

    today = datetime.now(timezone.utc).date()
    res = await session.execute(
        select(UserUsage.request_count).where(
            UserUsage.user_id == user_id,
            UserUsage.usage_date == today,
        )
    )
    current_count = res.scalar_one_or_none() or 0

    if current_count >= user.daily_request_limit:
        return False, current_count, user.daily_request_limit

    stmt = (
        pg_insert(UserUsage)
        .values(user_id=user_id, usage_date=today, request_count=1)
        .on_conflict_do_update(
            index_elements=["user_id", "usage_date"],
            set_={"request_count": UserUsage.request_count + 1},
        )
        .returning(UserUsage.request_count)
    )
    res = await session.execute(stmt)
    new_count = res.scalar_one()
    return True, new_count, user.daily_request_limit


async def get_usage_today(session: AsyncSession, user_id: str) -> int:
    today = datetime.now(timezone.utc).date()
    res = await session.execute(
        select(UserUsage.request_count).where(
            UserUsage.user_id == user_id,
            UserUsage.usage_date == today,
        )
    )
    return res.scalar_one_or_none() or 0


async def list_all_users(session: AsyncSession) -> list[dict]:
    today = datetime.now(timezone.utc).date()
    stmt = (
        select(
            User.id,
            User.username,
            User.email,
            User.name,
            User.role,
            User.is_active,
            User.daily_request_limit,
            User.created_at,
            func.coalesce(UserUsage.request_count, 0).label("requests_today"),
        )
        .outerjoin(
            UserUsage,
            (User.id == UserUsage.user_id) & (UserUsage.usage_date == today),
        )
        .order_by(User.created_at.desc())
    )
    res = await session.execute(stmt)
    rows = res.all()
    return [
        {
            "id": r.id,
            "username": r.username,
            "email": r.email,
            "name": r.name,
            "role": r.role,
            "is_active": r.is_active,
            "daily_request_limit": r.daily_request_limit,
            "created_at": int(r.created_at.timestamp()) if r.created_at else int(time.time()),
            "requests_today": r.requests_today,
        }
        for r in rows
    ]


async def update_user_role(session: AsyncSession, user_id: str, new_role: str) -> bool:
    res = await session.execute(
        update(User).where(User.id == user_id).values(role=new_role)
    )
    return res.rowcount > 0


async def update_user_limit(session: AsyncSession, user_id: str, new_limit: int) -> bool:
    res = await session.execute(
        update(User).where(User.id == user_id).values(daily_request_limit=new_limit)
    )
    return res.rowcount > 0


async def update_user_status(session: AsyncSession, user_id: str, is_active: bool) -> bool:
    res = await session.execute(
        update(User).where(User.id == user_id).values(is_active=is_active)
    )
    return res.rowcount > 0


async def delete_user(session: AsyncSession, user_id: str) -> bool:
    res = await session.execute(delete(User).where(User.id == user_id))
    return res.rowcount > 0
