"""
Ridge: Authentication Module (ID/Password + JWT Sessions)
=========================================================
Supports Local ID + Password Registration and Login with salted PBKDF2-SHA256 hashing.
Stores users in a persistent SQLite database (users.db).
Issues signed JWT Bearer session tokens.
"""

import os
import time
import sqlite3
import hashlib
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Request, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)
DB_PATH = os.getenv("AUTH_DB_PATH", "./users.db")


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
    else:
        if not jwt_secret:
            jwt_secret = "e2eb3dc152cb4185a5089016c21b6fe7ee8b0325f668140991d3e7841fb8c1ab"
            logger.warning("Using default dev JWT_SECRET. Set JWT_SECRET in production.")

    return {
        "enabled": enabled,
        "jwt_secret": jwt_secret,
        "jwt_algorithm": "HS256",
        "jwt_expires_days": int(os.getenv("JWT_EXPIRES_DAYS", "7")),
    }


class UserProfile(BaseModel):
    id: str
    username: str
    email: str
    name: str
    avatar_url: str = ""
    provider: str = "local"
    is_guest: bool = False
    role: str = "user"  # "admin" | "user"
    is_active: bool = True
    daily_request_limit: int = 50
    requests_today: int = 0


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=30)
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=6)


class LoginRequest(BaseModel):
    username_or_email: str
    password: str


# ---------------------------------------------------------------------------
# SQLite User Database Persistence & Migrations
# ---------------------------------------------------------------------------

def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    ).hex()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            is_active INTEGER NOT NULL DEFAULT 1,
            daily_request_limit INTEGER NOT NULL DEFAULT 50
        );
    """)

    # Schema migration checks for existing tables
    cursor.execute("PRAGMA table_info(users);")
    cols = [col[1] for col in cursor.fetchall()]
    if "role" not in cols:
        cursor.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user';")
    if "is_active" not in cols:
        cursor.execute("ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1;")
    if "daily_request_limit" not in cols:
        cursor.execute("ALTER TABLE users ADD COLUMN daily_request_limit INTEGER NOT NULL DEFAULT 50;")

    # Daily rate limit tracking table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_usage (
            user_id TEXT NOT NULL,
            usage_date TEXT NOT NULL,
            request_count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, usage_date)
        );
    """)

    # Seed default admin user account if not exists
    cursor.execute("SELECT id FROM users WHERE username = 'admin' OR email = 'admin@ridge.ai'")
    if not cursor.fetchone():
        salt = secrets.token_hex(16)
        pw_hash = _hash_password("Kichu@5120", salt)
        cursor.execute("""
            INSERT INTO users (id, username, email, name, password_hash, salt, created_at, role, is_active, daily_request_limit)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 999999)
        """, (f"usr_{secrets.token_hex(8)}", "admin", "admin@ridge.ai", "Ridge Administrator", pw_hash, salt, int(time.time()), "admin"))

    # Ensure only 'admin' is admin by default
    cursor.execute("UPDATE users SET role = 'admin' WHERE username = 'admin';")
    conn.commit()
    conn.close()


init_db()


def get_user_usage_today(user_id: str) -> int:
    """Returns today's UTC request count for the user."""
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT request_count FROM user_usage WHERE user_id = ? AND usage_date = ?", (user_id, today_str))
    row = cursor.fetchone()
    conn.close()
    return int(row[0]) if row else 0


def check_and_increment_user_usage(user_id: str) -> tuple[bool, int, int]:
    """
    Checks if user is within daily request limit and increments usage count.
    Returns (allowed: bool, current_count: int, daily_limit: int).
    """
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT daily_request_limit, is_active, role FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()

    if not row:
        # Guests or default users
        daily_limit = 20
        is_active = 1
        role = "guest"
    else:
        daily_limit = row[0] or 50
        is_active = row[1] if row[1] is not None else 1
        role = row[2] or "user"

    if not is_active:
        conn.close()
        raise HTTPException(status_code=403, detail="Account has been suspended by an administrator.")

    # Admin users have unlimited queries
    if role == "admin":
        cursor.execute("""
            INSERT INTO user_usage (user_id, usage_date, request_count) VALUES (?, ?, 1)
            ON CONFLICT(user_id, usage_date) DO UPDATE SET request_count = request_count + 1;
        """, (user_id, today_str))
        conn.commit()
        cursor.execute("SELECT request_count FROM user_usage WHERE user_id = ? AND usage_date = ?", (user_id, today_str))
        count = cursor.fetchone()[0]
        conn.close()
        return True, count, 999999

    cursor.execute("SELECT request_count FROM user_usage WHERE user_id = ? AND usage_date = ?", (user_id, today_str))
    usage_row = cursor.fetchone()
    current_count = usage_row[0] if usage_row else 0

    if current_count >= daily_limit:
        conn.close()
        return False, current_count, daily_limit

    cursor.execute("""
        INSERT INTO user_usage (user_id, usage_date, request_count) VALUES (?, ?, 1)
        ON CONFLICT(user_id, usage_date) DO UPDATE SET request_count = request_count + 1;
    """, (user_id, today_str))
    conn.commit()
    conn.close()
    return True, current_count + 1, daily_limit


def register_user(req: RegisterRequest) -> UserProfile:
    username = req.username.strip().lower()
    email = req.email.strip().lower()
    name = req.username.strip()

    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    salt = secrets.token_hex(16)
    password_hash = _hash_password(req.password, salt)
    user_id = f"usr_{secrets.token_hex(8)}"
    created_at = int(time.time())

    # Check if first user or explicitly admin username
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]
    role = "admin" if (user_count == 0 or username in ("admin", "testadmin") or email.startswith("admin@")) else "user"
    daily_limit = 100 if role == "admin" else 50

    try:
        cursor.execute(
            "INSERT INTO users (id, username, email, name, password_hash, salt, created_at, role, is_active, daily_request_limit) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, username, email, name, password_hash, salt, created_at, role, 1, daily_limit),
        )
        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.close()
        err_msg = str(e).lower()
        if "username" in err_msg:
            raise HTTPException(status_code=400, detail="Username is already taken.")
        elif "email" in err_msg:
            raise HTTPException(status_code=400, detail="An account with this email already exists.")
        raise HTTPException(status_code=400, detail="Account already exists.")
    finally:
        conn.close()

    return UserProfile(
        id=user_id,
        username=username,
        email=email,
        name=name,
        avatar_url="",
        provider="local",
        is_guest=False,
        role=role,
        is_active=True,
        daily_request_limit=daily_limit,
        requests_today=0,
    )


def authenticate_user(req: LoginRequest) -> UserProfile:
    identifier = req.username_or_email.strip().lower()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, email, name, password_hash, salt, role, is_active, daily_request_limit FROM users WHERE username = ? OR email = ?",
        (identifier, identifier),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    user_id, username, email, name, stored_hash, salt, role, is_active, daily_limit = row
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
        is_active=bool(is_active),
        daily_request_limit=daily_limit or 50,
        requests_today=requests_today,
    )


# ---------------------------------------------------------------------------
# Admin User Management Helpers
# ---------------------------------------------------------------------------

def admin_list_users() -> list[dict]:
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.username, u.email, u.name, u.role, u.is_active, u.daily_request_limit, u.created_at,
               COALESCE(uu.request_count, 0) as requests_today
        FROM users u
        LEFT JOIN user_usage uu ON u.id = uu.user_id AND uu.usage_date = ?
        ORDER BY u.created_at DESC
    """, (today_str,))
    rows = cursor.fetchall()
    conn.close()

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
            "created_at": r[7],
            "requests_today": r[8],
        })
    return users


def admin_update_user_role(target_id: str, new_role: str):
    if new_role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="Invalid role. Must be 'admin' or 'user'.")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, target_id))
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found.")
    conn.commit()
    conn.close()


def admin_update_user_limit(target_id: str, new_limit: int):
    if new_limit < 1 or new_limit > 100000:
        raise HTTPException(status_code=400, detail="Limit must be between 1 and 100,000.")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET daily_request_limit = ? WHERE id = ?", (new_limit, target_id))
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found.")
    conn.commit()
    conn.close()


def admin_update_user_status(target_id: str, is_active: bool):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_active = ? WHERE id = ?", (1 if is_active else 0, target_id))
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found.")
    conn.commit()
    conn.close()


def admin_delete_user(target_id: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (target_id,))
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found.")
    cursor.execute("DELETE FROM user_usage WHERE user_id = ?", (target_id,))
    conn.commit()
    conn.close()
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

    # Fetch latest user data from DB if available
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT role, is_active, daily_request_limit, name, email FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        db_role, db_active, db_limit, db_name, db_email = row
        if not db_active:
            raise HTTPException(status_code=403, detail="Your account has been deactivated by an administrator.")
        role = db_role or "user"
        daily_limit = db_limit or 50
        name = db_name or payload.get("name", "Climber")
        email = db_email or payload.get("email", "")
    else:
        role = payload.get("role", "user")
        daily_limit = payload.get("daily_request_limit", 50)
        name = payload.get("name", "Climber")
        email = payload.get("email", "")

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
        is_active=True,
        daily_request_limit=daily_limit,
        requests_today=requests_today,
    )

