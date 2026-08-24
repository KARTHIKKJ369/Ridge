"""
Ridge: Authentication Module (PostgreSQL Stored Users & JWT Sessions)
=====================================================================
Supports Local Registration and Login with salted PBKDF2-SHA256 hashing.
Stores users and usage in PostgreSQL.
Issues signed JWT Bearer session tokens.
"""

import os
import time
import hashlib
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Request, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.db.database import get_sync_session, is_postgres_configured
from app.db.repositories.user_repo import DEFAULT_TENANT_ID

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


KNOWN_INSECURE_DEV_SECRETS = {
    "e2eb3dc152cb4185a5089016c21b6fe7ee8b0325f668140991d3e7841fb8c1ab",
    "change_me",
    "secret",
    "your_jwt_secret_here",
}


def is_production_environment() -> bool:
    """Detect if running in a production or deployed cloud environment."""
    env_name = (os.getenv("ENV") or os.getenv("ENVIRONMENT") or os.getenv("NODE_ENV") or "").lower().strip()
    if env_name in ("production", "prod"):
        return True
    # Auto-detect common cloud platforms (Railway, Render, Fly.io, HuggingFace Spaces, Cloud Run)
    if any(os.getenv(k) for k in ("RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID", "RENDER", "FLY_APP_NAME", "SPACE_ID", "K_SERVICE")):
        return True
    return False


def get_auth_settings() -> dict:
    raw_enabled = os.getenv("AUTH_ENABLED", "true").lower().strip()
    enabled = raw_enabled not in ("false", "0", "no")
    jwt_secret = os.getenv("JWT_SECRET") or os.getenv("JWT_SECRET_KEY")
    is_prod = is_production_environment()

    if is_prod:
        if not jwt_secret or jwt_secret.strip() in KNOWN_INSECURE_DEV_SECRETS:
            raise RuntimeError(
                "CRITICAL SECURITY ERROR: JWT_SECRET environment variable is missing or using "
                "an insecure default secret in production/cloud environment. Refusing to start. "
                "Please set a strong, unique JWT_SECRET in your Railway / cloud dashboard."
            )
    elif not jwt_secret:
        jwt_secret = "ridge-default-insecure-dev-secret-replace-in-prod-xyz789"

    return {
        "jwt_secret": jwt_secret,
        "jwt_algorithm": os.getenv("JWT_ALGORITHM", "HS256"),
        "jwt_expires_days": int(os.getenv("JWT_EXPIRES_DAYS", "30")),
        "enabled": enabled,
    }


class UserProfile(BaseModel):
    id: str
    username: str
    name: str
    email: str
    avatar_url: str = ""
    provider: str = "local"
    is_guest: bool = False
    role: str = "user"  # "superadmin" | "admin" | "user" | "guest"
    tenant_id: str = str(DEFAULT_TENANT_ID)
    tenant_name: str = "Default Tenant"
    tenant_slug: str = "default"
    is_active: bool = True
    daily_request_limit: int = 50
    requests_today: int = 0


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=6)
    name: Optional[str] = None
    tenant_slug: Optional[str] = None


class RegisterInstitutionRequest(BaseModel):
    institution_name: str = Field(..., min_length=2, max_length=100)
    slug: str = Field(..., min_length=2, max_length=64)
    admin_name: str = Field(..., min_length=2, max_length=100)
    admin_username: str = Field(..., min_length=3, max_length=50)
    admin_email: str = Field(..., min_length=5)
    admin_password: str = Field(..., min_length=6)


class AdminCreateUserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=6)
    name: Optional[str] = None
    role: str = "user"
    daily_request_limit: int = 50
    tenant_id: Optional[str] = None


class LoginRequest(BaseModel):
    username_or_email: str
    password: str


# ---------------------------------------------------------------------------
# PostgreSQL User Database Persistence & Rate Limiting
# ---------------------------------------------------------------------------

def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    ).hex()


def init_db():
    """Initializes and seeds default admin and tenant in PostgreSQL."""
    try:
        with get_sync_session() as session:
            # Check for existing admin
            admin_check = session.execute(
                text("SELECT id FROM users WHERE username = 'admin' OR email = 'admin@ridge.ai'")
            ).first()

            if not admin_check:
                salt = secrets.token_hex(16)
                pw_hash = _hash_password("Kichu@5120", salt)
                admin_id = f"usr_{secrets.token_hex(8)}"
                session.execute(
                    text("""
                        INSERT INTO users (id, tenant_id, username, email, name, password_hash, salt, role, is_active, daily_request_limit, created_at, updated_at)
                        VALUES (:uid, :tid, 'admin', 'admin@ridge.ai', 'Ridge Administrator', :hash, :salt, 'superadmin', true, 999999, NOW(), NOW())
                        ON CONFLICT (username) DO NOTHING
                    """),
                    {"uid": admin_id, "tid": DEFAULT_TENANT_ID, "hash": pw_hash, "salt": salt}
                )
                session.commit()
            else:
                # Ensure existing admin is elevated to superadmin
                session.execute(
                    text("UPDATE users SET role = 'superadmin', daily_request_limit = 999999 WHERE username = 'admin'")
                )
                session.commit()

    except Exception as e:
        logger.warning(f"Auth DB init notice: {e}")



def get_user_usage_today(user_id: str) -> int:
    """Returns today's UTC request count for the user from PostgreSQL."""
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        with get_sync_session() as session:
            row = session.execute(
                text("SELECT request_count FROM user_usage WHERE user_id = :uid AND usage_date = :udate"),
                {"uid": user_id, "udate": today_str}
            ).first()
            return int(row[0]) if row else 0
    except Exception as e:
        logger.warning(f"Error reading usage: {e}")
        return 0


def check_and_increment_user_usage(user_id: str) -> tuple[bool, int, int]:
    """
    Checks if user is within daily request limit and increments usage count in PostgreSQL.
    Returns (allowed: bool, current_count: int, daily_limit: int).
    """
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        with get_sync_session() as session:
            row = session.execute(
                text("SELECT daily_request_limit, is_active, role FROM users WHERE id = :uid"),
                {"uid": user_id}
            ).first()

            if not row:
                daily_limit = 50
                is_active = True
                role = "user"
            else:
                daily_limit = row[0] or 50
                is_active = bool(row[1]) if row[1] is not None else True
                role = row[2] or "user"

            if not is_active:
                raise HTTPException(status_code=403, detail="Account has been suspended by an administrator.")

            if role == "admin":
                session.execute(
                    text("""
                        INSERT INTO user_usage (user_id, usage_date, request_count) VALUES (:uid, :udate, 1)
                        ON CONFLICT (user_id, usage_date) DO UPDATE SET request_count = user_usage.request_count + 1
                    """),
                    {"uid": user_id, "udate": today_str}
                )
                session.commit()
                count_row = session.execute(
                    text("SELECT request_count FROM user_usage WHERE user_id = :uid AND usage_date = :udate"),
                    {"uid": user_id, "udate": today_str}
                ).first()
                count = count_row[0] if count_row else 1
                return True, count, 999999

            usage_row = session.execute(
                text("SELECT request_count FROM user_usage WHERE user_id = :uid AND usage_date = :udate"),
                {"uid": user_id, "udate": today_str}
            ).first()
            current_count = usage_row[0] if usage_row else 0

            if current_count >= daily_limit:
                return False, current_count, daily_limit

            session.execute(
                text("""
                    INSERT INTO user_usage (user_id, usage_date, request_count) VALUES (:uid, :udate, 1)
                    ON CONFLICT (user_id, usage_date) DO UPDATE SET request_count = user_usage.request_count + 1
                """),
                {"uid": user_id, "udate": today_str}
            )
            session.commit()
            return True, current_count + 1, daily_limit
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Error checking user usage: {e}")
        return True, 1, 50



def register_user(req: RegisterRequest) -> UserProfile:
    username = req.username.strip().lower()
    email = req.email.strip().lower()
    name = req.username.strip()
    req_slug = (req.tenant_slug or "default").strip().lower()

    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    salt = secrets.token_hex(16)
    password_hash = _hash_password(req.password, salt)
    user_id = f"usr_{secrets.token_hex(8)}"

    try:
        with get_sync_session() as session:
            # 1. Resolve Tenant
            t_row = session.execute(
                text("SELECT id, name, slug, is_active, max_users FROM tenants WHERE slug = :slug"),
                {"slug": req_slug}
            ).first()

            if not t_row:
                raise HTTPException(status_code=400, detail=f"Organization '{req_slug}' not found.")

            target_tenant_id, target_tenant_name, target_tenant_slug, is_active, max_users = t_row
            if not is_active:
                raise HTTPException(status_code=403, detail="This organization has been deactivated.")

            # Check tenant user capacity
            u_count_row = session.execute(
                text("SELECT count(*) FROM users WHERE tenant_id = :tid"),
                {"tid": target_tenant_id}
            ).first()
            tenant_user_count = u_count_row[0] if u_count_row else 0
            if tenant_user_count >= (max_users or 50):
                raise HTTPException(status_code=400, detail="This organization has reached its maximum member capacity.")

            # Role assignment
            all_users_count = session.execute(text("SELECT count(*) FROM users")).scalar() or 0
            if all_users_count == 0 or username in ("admin", "superadmin"):
                role = "superadmin"
            elif tenant_user_count == 0:
                role = "admin"
            else:
                role = "user"

            daily_limit = 999999 if role in ("superadmin", "admin") else 50

            session.execute(
                text("""
                    INSERT INTO users (id, tenant_id, username, email, name, password_hash, salt, role, is_active, daily_request_limit, created_at, updated_at)
                    VALUES (:uid, :tid, :uname, :email, :name, :hash, :salt, :role, true, :limit, NOW(), NOW())
                """),
                {"uid": user_id, "tid": target_tenant_id, "uname": username, "email": email, "name": name, "hash": password_hash, "salt": salt, "role": role, "limit": daily_limit}
            )
            session.commit()

    except HTTPException:
        raise
    except Exception as e:
        err_msg = str(e).lower()
        if "username" in err_msg or "unique" in err_msg:
            raise HTTPException(status_code=400, detail="Username or email is already registered.")
        raise HTTPException(status_code=400, detail=f"Registration failed: {e}")

    return UserProfile(
        id=user_id,
        username=username,
        email=email,
        name=name,
        avatar_url="",
        provider="local",
        is_guest=False,
        role=role,
        tenant_id=str(target_tenant_id),
        tenant_name=target_tenant_name,
        tenant_slug=target_tenant_slug,
        is_active=True,
        daily_request_limit=daily_limit,
        requests_today=0,
    )


def register_institution(req: RegisterInstitutionRequest) -> UserProfile:
    import uuid
    inst_name = req.institution_name.strip()
    slug = req.slug.strip().lower()
    uname = req.admin_username.strip().lower()
    email = req.admin_email.strip().lower()
    name = req.admin_name.strip()

    if len(req.admin_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    try:
        with get_sync_session() as session:
            # 1. Check slug uniqueness
            existing_t = session.execute(
                text("SELECT id FROM tenants WHERE slug = :slug"),
                {"slug": slug}
            ).first()
            if existing_t:
                raise HTTPException(status_code=400, detail=f"Institution slug '{slug}' is already taken.")

            # 2. Check username/email uniqueness
            existing_u = session.execute(
                text("SELECT id FROM users WHERE username = :uname OR email = :email"),
                {"uname": uname, "email": email}
            ).first()
            if existing_u:
                raise HTTPException(status_code=400, detail="Username or email is already registered.")

            # 3. Create Tenant
            tenant_id = uuid.uuid4()
            session.execute(
                text("""
                    INSERT INTO tenants (id, name, slug, is_active, max_users, created_at, updated_at)
                    VALUES (:tid, :name, :slug, true, 50, NOW(), NOW())
                """),
                {"tid": tenant_id, "name": inst_name, "slug": slug}
            )

            # 4. Create primary KB for Tenant
            kb_id = uuid.uuid4()
            session.execute(
                text("""
                    INSERT INTO knowledge_bases (id, tenant_id, name, description, created_at, updated_at)
                    VALUES (:kbid, :tid, :name, :desc, NOW(), NOW())
                """),
                {
                    "kbid": kb_id,
                    "tid": tenant_id,
                    "name": f"{inst_name} Knowledge Base",
                    "desc": f"Primary knowledge base for {inst_name}",
                }
            )

            # 5. Create Admin User
            salt = secrets.token_hex(16)
            pw_hash = _hash_password(req.admin_password, salt)
            user_id = f"usr_{secrets.token_hex(8)}"

            session.execute(
                text("""
                    INSERT INTO users (id, tenant_id, username, email, name, password_hash, salt, role, is_active, daily_request_limit, created_at, updated_at)
                    VALUES (:uid, :tid, :uname, :email, :name, :hash, :salt, 'admin', true, 999999, NOW(), NOW())
                """),
                {
                    "uid": user_id,
                    "tid": tenant_id,
                    "uname": uname,
                    "email": email,
                    "name": name,
                    "hash": pw_hash,
                    "salt": salt,
                }
            )
            session.commit()

            return UserProfile(
                id=user_id,
                username=uname,
                email=email,
                name=name,
                avatar_url="",
                provider="local",
                is_guest=False,
                role="admin",
                tenant_id=str(tenant_id),
                tenant_name=inst_name,
                tenant_slug=slug,
                is_active=True,
                daily_request_limit=999999,
                requests_today=0,
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering institution: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to register institution: {e}")


def authenticate_user(req: LoginRequest) -> UserProfile:
    identifier = req.username_or_email.strip().lower()
    try:
        with get_sync_session() as session:
            row = session.execute(
                text("""
                    SELECT u.id, u.username, u.email, u.name, u.password_hash, u.salt, u.role, u.is_active, u.daily_request_limit,
                           t.id as tenant_id, t.name as tenant_name, t.slug as tenant_slug
                    FROM users u
                    JOIN tenants t ON u.tenant_id = t.id
                    WHERE u.username = :ident OR u.email = :ident
                """),
                {"ident": identifier}
            ).first()

            if not row:
                raise HTTPException(status_code=401, detail="Invalid username or password.")

            (user_id, username, email, name, stored_hash, salt, role, is_active, daily_limit,
             tenant_id, tenant_name, tenant_slug) = row

            test_hash = _hash_password(req.password, salt)

            if not secrets.compare_digest(stored_hash, test_hash):
                raise HTTPException(status_code=401, detail="Invalid username or password.")

            if not is_active:
                raise HTTPException(status_code=403, detail="Your account has been deactivated. Please contact an administrator.")

            requests_today = get_user_usage_today(user_id)

            return UserProfile(
                id=user_id,
                username=username,
                email=email,
                name=name,
                avatar_url="",
                provider="local",
                is_guest=False,
                role=role or "user",
                tenant_id=str(tenant_id),
                tenant_name=tenant_name or "Default Tenant",
                tenant_slug=tenant_slug or "default",
                is_active=bool(is_active),
                daily_request_limit=daily_limit or 50,
                requests_today=requests_today,
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(status_code=401, detail="Invalid username or password.")



# ---------------------------------------------------------------------------
# Admin User Management Helpers (PostgreSQL - Tenant Scoped)
# ---------------------------------------------------------------------------

def admin_list_users(current_user: UserProfile, tenant_filter: Optional[str] = None) -> list[dict]:
    import uuid
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    is_superadmin = current_user.role == "superadmin"

    try:
        with get_sync_session() as session:
            query = """
                SELECT u.id, u.username, u.email, u.name, u.role, u.is_active, u.daily_request_limit, u.created_at,
                       COALESCE(uu.request_count, 0) as requests_today,
                       t.id as tenant_id, t.name as tenant_name, t.slug as tenant_slug
                FROM users u
                LEFT JOIN tenants t ON u.tenant_id = t.id
                LEFT JOIN user_usage uu ON u.id = uu.user_id AND uu.usage_date = :udate
            """
            params: dict = {"udate": today_str}

            if not is_superadmin:
                query += " WHERE u.tenant_id = :tid"
                params["tid"] = uuid.UUID(current_user.tenant_id)
            elif tenant_filter and tenant_filter.strip():
                tf = tenant_filter.strip()
                try:
                    tf_uuid = uuid.UUID(tf)
                    query += " WHERE (u.tenant_id = :tf_uuid OR t.slug = :tf)"
                    params["tf_uuid"] = tf_uuid
                    params["tf"] = tf
                except Exception:
                    query += " WHERE t.slug = :tf"
                    params["tf"] = tf

            query += " ORDER BY u.created_at DESC"

            rows = session.execute(text(query), params).all()

            users = []
            for r in rows:
                users.append({
                    "id": r[0],
                    "username": r[1],
                    "email": r[2],
                    "name": r[3],
                    "role": r[4] or "user",
                    "is_active": bool(r[5]),
                    "daily_request_limit": r[6] or 50,
                    "created_at": int(r[7].timestamp()) if hasattr(r[7], "timestamp") else int(time.time()),
                    "requests_today": r[8],
                    "tenant_id": str(r[9]) if r[9] else "",
                    "tenant_name": r[10] or "Default",
                    "tenant_slug": r[11] or "default",
                })
            return users
    except Exception as e:
        logger.error(f"Error listing admin users: {e}")
        return []


def admin_create_user(admin_user: UserProfile, req: AdminCreateUserRequest) -> UserProfile:
    import uuid
    uname = req.username.strip().lower()
    email = req.email.strip().lower()
    name = (req.name or req.username).strip()
    role = req.role.strip().lower()

    if role not in ("admin", "user", "superadmin"):
        raise HTTPException(status_code=400, detail="Invalid role. Must be 'user' or 'admin'.")
    if role == "superadmin" and admin_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Only SuperAdmin can grant SuperAdmin role.")

    # Determine tenant
    if admin_user.role == "superadmin" and req.tenant_id:
        try:
            target_tenant_id = uuid.UUID(req.tenant_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid tenant_id UUID.")
    else:
        target_tenant_id = uuid.UUID(admin_user.tenant_id)

    try:
        with get_sync_session() as session:
            t_row = session.execute(
                text("SELECT name, slug, is_active, max_users FROM tenants WHERE id = :tid"),
                {"tid": target_tenant_id}
            ).first()
            if not t_row:
                raise HTTPException(status_code=404, detail="Enterprise not found.")
            t_name, t_slug, is_active, max_users = t_row
            if not is_active:
                raise HTTPException(status_code=403, detail="Enterprise has been deactivated.")

            u_count = session.execute(
                text("SELECT count(*) FROM users WHERE tenant_id = :tid"),
                {"tid": target_tenant_id}
            ).scalar() or 0
            if u_count >= (max_users or 50):
                raise HTTPException(status_code=400, detail="Enterprise has reached maximum member capacity.")

            existing = session.execute(
                text("SELECT id FROM users WHERE username = :uname OR email = :email"),
                {"uname": uname, "email": email}
            ).first()
            if existing:
                raise HTTPException(status_code=400, detail="Username or email is already registered.")

            salt = secrets.token_hex(16)
            pw_hash = _hash_password(req.password, salt)
            user_id = f"usr_{secrets.token_hex(8)}"
            limit = 999999 if role in ("superadmin", "admin") else max(1, req.daily_request_limit)

            session.execute(
                text("""
                    INSERT INTO users (id, tenant_id, username, email, name, password_hash, salt, role, is_active, daily_request_limit, created_at, updated_at)
                    VALUES (:uid, :tid, :uname, :email, :name, :hash, :salt, :role, true, :limit, NOW(), NOW())
                """),
                {"uid": user_id, "tid": target_tenant_id, "uname": uname, "email": email, "name": name, "hash": pw_hash, "salt": salt, "role": role, "limit": limit}
            )
            session.commit()

            return UserProfile(
                id=user_id,
                username=uname,
                email=email,
                name=name,
                avatar_url="",
                provider="local",
                is_guest=False,
                role=role,
                tenant_id=str(target_tenant_id),
                tenant_name=t_name,
                tenant_slug=t_slug,
                is_active=True,
                daily_request_limit=limit,
                requests_today=0,
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to create user: {e}")


def admin_update_user_role(admin_user: UserProfile, target_id: str, new_role: str):
    role_clean = new_role.strip().lower()
    if role_clean not in ("admin", "user", "superadmin"):
        raise HTTPException(status_code=400, detail="Invalid role. Must be 'admin' or 'user'.")
    if role_clean == "superadmin" and admin_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Only SuperAdmin can grant SuperAdmin role.")

    with get_sync_session() as session:
        target = session.execute(
            text("SELECT id, role, tenant_id FROM users WHERE id = :uid"),
            {"uid": target_id}
        ).first()
        if not target:
            raise HTTPException(status_code=404, detail="User not found.")

        t_uid, t_role, t_tenant_id = target
        if t_role == "superadmin" and admin_user.role != "superadmin":
            raise HTTPException(status_code=403, detail="Cannot modify SuperAdmin account.")
        if admin_user.role != "superadmin" and str(t_tenant_id) != str(admin_user.tenant_id):
            raise HTTPException(status_code=403, detail="You can only manage users within your own enterprise.")

        session.execute(
            text("UPDATE users SET role = :role, updated_at = NOW() WHERE id = :uid"),
            {"role": role_clean, "uid": target_id}
        )
        session.commit()


def admin_update_user_limit(admin_user: UserProfile, target_id: str, new_limit: int):
    if new_limit < 1 or new_limit > 1000000:
        raise HTTPException(status_code=400, detail="Limit must be between 1 and 1,000,000.")

    with get_sync_session() as session:
        target = session.execute(
            text("SELECT id, role, tenant_id FROM users WHERE id = :uid"),
            {"uid": target_id}
        ).first()
        if not target:
            raise HTTPException(status_code=404, detail="User not found.")

        t_uid, t_role, t_tenant_id = target
        if admin_user.role != "superadmin" and str(t_tenant_id) != str(admin_user.tenant_id):
            raise HTTPException(status_code=403, detail="You can only manage users within your own enterprise.")

        session.execute(
            text("UPDATE users SET daily_request_limit = :lim, updated_at = NOW() WHERE id = :uid"),
            {"lim": new_limit, "uid": target_id}
        )
        session.commit()


def admin_update_user_status(admin_user: UserProfile, target_id: str, is_active: bool):
    with get_sync_session() as session:
        target = session.execute(
            text("SELECT id, role, tenant_id FROM users WHERE id = :uid"),
            {"uid": target_id}
        ).first()
        if not target:
            raise HTTPException(status_code=404, detail="User not found.")

        t_uid, t_role, t_tenant_id = target
        if t_role == "superadmin":
            raise HTTPException(status_code=403, detail="Cannot deactivate SuperAdmin account.")
        if admin_user.role != "superadmin" and str(t_tenant_id) != str(admin_user.tenant_id):
            raise HTTPException(status_code=403, detail="You can only manage users within your own enterprise.")

        session.execute(
            text("UPDATE users SET is_active = :act, updated_at = NOW() WHERE id = :uid"),
            {"act": is_active, "uid": target_id}
        )
        session.commit()


def admin_delete_user(admin_user: UserProfile, target_id: str) -> bool:
    if target_id == admin_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account.")

    with get_sync_session() as session:
        target = session.execute(
            text("SELECT id, role, tenant_id FROM users WHERE id = :uid"),
            {"uid": target_id}
        ).first()
        if not target:
            raise HTTPException(status_code=404, detail="User not found.")

        t_uid, t_role, t_tenant_id = target
        if t_role == "superadmin":
            raise HTTPException(status_code=403, detail="Cannot delete SuperAdmin account.")
        if admin_user.role != "superadmin" and str(t_tenant_id) != str(admin_user.tenant_id):
            raise HTTPException(status_code=403, detail="You can only delete users within your own enterprise.")

        session.execute(text("DELETE FROM user_usage WHERE user_id = :uid"), {"uid": target_id})
        session.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": target_id})
        session.commit()
        return True



# ---------------------------------------------------------------------------
# JWT Session Helpers
# ---------------------------------------------------------------------------

def create_access_token(user_data: dict, expires_delta: Optional[timedelta] = None) -> str:
    settings = get_auth_settings()
    to_encode = user_data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings["jwt_expires_days"])

    to_encode.update({"exp": int(expire.timestamp()), "iat": int(now.timestamp())})
    encoded_jwt = jwt.encode(to_encode, settings["jwt_secret"], algorithm=settings["jwt_algorithm"])
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    settings = get_auth_settings()
    try:
        payload = jwt.decode(
            token,
            settings["jwt_secret"],
            algorithms=[settings["jwt_algorithm"]],
            options={"require": ["exp", "iat"]}
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {e}")
        return None


# ---------------------------------------------------------------------------
# FastAPI Dependency: get_current_user
# ---------------------------------------------------------------------------

async def get_current_user(
    request: Request,
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> UserProfile:
    settings = get_auth_settings()

    # If auth is explicitly turned off via AUTH_ENABLED=false
    if not settings["enabled"]:
        return UserProfile(
            id="guest_climber",
            username="guest",
            name="Climber Guest",
            email="guest@ridge.local",
            avatar_url="",
            provider="guest",
            is_guest=True,
            role="user",
            is_active=True,
            daily_request_limit=50,
            requests_today=0,
        )

    # Extract Bearer token from Header, Cookie, or Query parameter (for SSE stream)
    token = None
    if auth_header and auth_header.credentials:
        token = auth_header.credentials
    elif "Authorization" in request.headers:
        val = request.headers["Authorization"]
        if val.startswith("Bearer "):
            token = val[7:]
    elif "ridge_token" in request.cookies:
        token = request.cookies["ridge_token"]
    elif "token" in request.query_params:
        token = request.query_params["token"]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in or register.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("id", "user")

    # Fetch latest user data from PostgreSQL if available
    tenant_id = str(DEFAULT_TENANT_ID)
    tenant_name = "Default Tenant"
    tenant_slug = "default"

    try:
        with get_sync_session() as session:
            row = session.execute(
                text("""
                    SELECT u.role, u.is_active, u.daily_request_limit, u.name, u.email,
                           t.id as tenant_id, t.name as tenant_name, t.slug as tenant_slug
                    FROM users u
                    JOIN tenants t ON u.tenant_id = t.id
                    WHERE u.id = :uid
                """),
                {"uid": user_id}
            ).first()

            if row:
                db_role, db_active, db_limit, db_name, db_email, t_id, t_name, t_slug = row
                if not db_active:
                    raise HTTPException(status_code=403, detail="Your account has been deactivated by an administrator.")
                role = db_role or "user"
                daily_limit = db_limit or 50
                name = db_name or payload.get("name", "Climber")
                email = db_email or payload.get("email", "")
                tenant_id = str(t_id)
                tenant_name = t_name or "Default Tenant"
                tenant_slug = t_slug or "default"
            else:
                role = payload.get("role", "user")
                daily_limit = payload.get("daily_request_limit", 50)
                name = payload.get("name", "Climber")
                email = payload.get("email", "")
                tenant_id = str(payload.get("tenant_id", DEFAULT_TENANT_ID))
                tenant_name = payload.get("tenant_name", "Default Tenant")
                tenant_slug = payload.get("tenant_slug", "default")
    except HTTPException:
        raise
    except Exception:
        role = payload.get("role", "user")
        daily_limit = payload.get("daily_request_limit", 50)
        name = payload.get("name", "Climber")
        email = payload.get("email", "")
        tenant_id = str(payload.get("tenant_id", DEFAULT_TENANT_ID))
        tenant_name = payload.get("tenant_name", "Default Tenant")
        tenant_slug = payload.get("tenant_slug", "default")

    requests_today = get_user_usage_today(user_id)

    return UserProfile(
        id=user_id,
        username=payload.get("username", "user"),
        name=name,
        email=email,
        avatar_url=payload.get("avatar_url", ""),
        provider=payload.get("provider", "local"),
        is_guest=payload.get("is_guest", False),
        role=role,
        tenant_id=tenant_id,
        tenant_name=tenant_name,
        tenant_slug=tenant_slug,
        is_active=True,
        daily_request_limit=daily_limit,
        requests_today=requests_today,
    )



