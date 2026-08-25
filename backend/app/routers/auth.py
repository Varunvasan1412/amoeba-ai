from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from pydantic import BaseModel

from app.core.database import get_session
from app.core.security import create_access_token, verify_password, Token
from app.core.auth_deps import get_current_user
from app.models.user import User

from app.services.auth_service import AuthService

class LoginRequest(BaseModel):
    username: str
    password: str
    company_code: Optional[str] = None

router = APIRouter()

from app.core.rate_limiter import limiter
from app.core.config import settings

@router.post("/login/access-token", response_model=Token)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def login_access_token(
    request_data: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_session)
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    return await AuthService.authenticate_user(
        session=session,
        username=request_data.username,
        password=request_data.password,
        company_code=request_data.company_code,
        ip_address=request.client.host if request.client else "0.0.0.0",
        user_agent=request.headers.get("user-agent", "Unknown")
    )
@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user)
):
    """
    Log out of the system.
    """
    AuthService.logout_user(user_id=current_user.id)
    return {"status": "success"}

@router.get("/me")
async def read_user_me(
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get current user with role and permissions.
    """
    from app.services.rbac_service import get_user_permissions
    permissions = await get_user_permissions(current_user.id)
    role_name = getattr(current_user.role, "name", None)
    
    user_dict = current_user.dict()
    user_dict["role"] = role_name
    user_dict["permissions"] = permissions
    return user_dict

