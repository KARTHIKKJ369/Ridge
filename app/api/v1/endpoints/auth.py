"""
Authentication & Multi-Tenant Organization Registration Endpoints
=================================================================
Handles user registration, institution provisioning, login, session inspection, and public tenant listing.
"""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from auth import (
    get_current_user,
    get_auth_settings,
    create_access_token,
    register_user,
    register_institution,
    authenticate_user,
    RegisterRequest,
    RegisterInstitutionRequest,
    LoginRequest,
    UserProfile,
)
from app.db.database import get_db_session, is_postgres_configured
from app.db.repositories import tenant_repo

router = APIRouter(tags=["Authentication"])


@router.get("/auth/config")
def auth_config():
    """Returns auth configuration status."""
    settings = get_auth_settings()
    return {
        "enabled": settings["enabled"],
        "mode": "password",
    }


@router.post("/auth/register")
def auth_register(req: RegisterRequest):
    """Registers a new user and issues a signed JWT session token."""
    user = register_user(req)
    token = create_access_token(user.model_dump())
    response = JSONResponse({"user": user.model_dump(), "token": token})
    response.set_cookie(
        key="ridge_token",
        value=token,
        max_age=7 * 86400,
        httponly=False,
        samesite="lax",
    )
    return response


@router.post("/auth/register-institution")
def auth_register_institution(req: RegisterInstitutionRequest):
    """Registers a new enterprise institution and sets the creator as its Admin."""
    user = register_institution(req)
    token = create_access_token(user.model_dump())
    response = JSONResponse({"user": user.model_dump(), "token": token})
    response.set_cookie(
        key="ridge_token",
        value=token,
        max_age=7 * 86400,
        httponly=False,
        samesite="lax",
    )
    return response


@router.get("/tenants/public")
async def list_public_tenants():
    """Lists active institutions for user registration selection."""
    if not is_postgres_configured():
        return {"tenants": [{"id": "00000000-0000-0000-0000-000000000001", "name": "Default Tenant", "slug": "default"}]}
    async with get_db_session() as session:
        tenants = await tenant_repo.list_tenants(session)
        public_list = [{"id": t["id"], "name": t["name"], "slug": t["slug"]} for t in tenants if t.get("is_active", True)]
        return {"tenants": public_list}


@router.post("/auth/login")
def auth_login(req: LoginRequest):
    """Authenticates username/email and password, returning JWT token."""
    user = authenticate_user(req)
    token = create_access_token(user.model_dump())
    response = JSONResponse({"user": user.model_dump(), "token": token})
    response.set_cookie(
        key="ridge_token",
        value=token,
        max_age=7 * 86400,
        httponly=False,
        samesite="lax",
    )
    return response


@router.get("/auth/me")
def get_me(user: UserProfile = Depends(get_current_user)):
    """Returns the authenticated user profile."""
    return user


@router.post("/auth/logout")
def logout():
    """Clears the authentication session."""
    response = JSONResponse({"status": "logged_out"})
    response.delete_cookie("ridge_token")
    return response
