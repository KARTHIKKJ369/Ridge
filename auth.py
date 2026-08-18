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


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=30)
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=6)


class LoginRequest(BaseModel):
    username_or_email: str
    password: str


# ---------------------------------------------------------------------------
# SQLite User Database Persistence
# ---------------------------------------------------------------------------

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
            created_at INTEGER NOT NULL
        );
    """)
    conn.commit()
    conn.close()


init_db()


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    ).hex()


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

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (id, username, email, name, password_hash, salt, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, username, email, name, password_hash, salt, created_at),
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
    )


def authenticate_user(req: LoginRequest) -> UserProfile:
    identifier = req.username_or_email.strip().lower()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, email, name, password_hash, salt FROM users WHERE username = ? OR email = ?",
        (identifier, identifier),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    user_id, username, email, name, stored_hash, salt = row
    test_hash = _hash_password(req.password, salt)

    if not secrets.compare_digest(stored_hash, test_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    return UserProfile(
        id=user_id,
        username=username,
        email=email,
        name=name,
        avatar_url="",
        provider="local",
        is_guest=False,
    )


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

    return UserProfile(
        id=payload.get("id", "user"),
        username=payload.get("username", "user"),
        name=payload.get("name", "Climber"),
        email=payload.get("email", ""),
        avatar_url=payload.get("avatar_url", ""),
        provider=payload.get("provider", "local"),
        is_guest=payload.get("is_guest", False),
    )
