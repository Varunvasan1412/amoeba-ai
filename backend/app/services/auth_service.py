from datetime import timedelta
from typing import Optional, Any
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.security import verify_password, create_access_token, Token
from app.models.user import User
from app.models.rbac import Role
from sqlalchemy.orm import joinedload
from app.services.audit_service import log_event
from app.models.client_config import ClientConfig

class AuthService:
    @staticmethod
    async def authenticate_user(
        session: AsyncSession, 
        username: str, 
        password: str,
        company_code: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Token:
        # 1. Lookup User (by username or email)
        statement = select(User).options(joinedload(User.role)).where(
            (User.username == username) | (User.email == username)
        )
        result = await session.execute(statement)
        user = result.scalars().first()
        
        # 2. Pre-verify Existence & Password
        if not user or not verify_password(password, user.hashed_password):
            reason = "Invalid credentials"
            await AuthService._log_login_attempt(
                session, username, status="FAILED", reason=reason, 
                ip_address=ip_address, user_agent=user_agent
            )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=reason)

        # 3. Handle Platform User Bypass
        if user.is_platform_user:
            # Platform users can login without company code or with any valid company code
            pass 
        else:
            # 4. Handle Client User Isolation
            if not company_code:
                reason = "Company Code is required for non-platform users"
                await AuthService._log_login_attempt(
                    session, username, status="FAILED", reason=reason, 
                    ip_address=ip_address, user_agent=user_agent
                )
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=reason)
            
            # Verify company code exists
            client_stmt = select(ClientConfig).where(ClientConfig.company_code == company_code)
            client_res = await session.execute(client_stmt)
            client = client_res.scalar_one_or_none()
            
            if not client:
                reason = "Invalid Company Code"
                await AuthService._log_login_attempt(
                    session, username, status="FAILED", reason=reason, 
                    ip_address=ip_address, user_agent=user_agent, company_code=company_code
                )
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=reason)
            
            # Verify user belongs to this client
            if user.client_id != client.id:
                reason = "User does not belong to this company"
                await AuthService._log_login_attempt(
                    session, username, status="FAILED", reason=reason, 
                    ip_address=ip_address, user_agent=user_agent, 
                    client_id=client.id, company_code=company_code, user_id=user.id
                )
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=reason)
            
        if not user.is_active:
            await AuthService._log_login_attempt(
                session, username, status="FAILED", reason="Inactive user", 
                ip_address=ip_address, user_agent=user_agent, 
                client_id=user.client_id, user_id=user.id
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )
            
        # Log SUCCESS to LoginAudit
        await AuthService._log_login_attempt(
            session, username, status="SUCCESS", 
            ip_address=ip_address, user_agent=user_agent, 
            client_id=user.client_id, company_code=company_code, user_id=user.id
        )
        
        # Original general audit log
        log_event(
            user_id=str(user.id),
            action="LOGIN",
            entity="User Account",
            source="USER",
            status="SUCCESS",
            details={},
            ip_address=ip_address,
            client_id=getattr(user, "client_id", None)
        )
        
        # Fetch permissions
        from app.services.rbac_service import get_user_permissions
        permissions = await get_user_permissions(user.id)
        role_name = getattr(user.role, "name", None)

        return {
            "access_token": create_access_token(user.id, client_id=user.client_id),
            "token_type": "bearer",
            "role": role_name,
            "permissions": permissions
        }

    @staticmethod
    async def _log_login_attempt(
        session: AsyncSession,
        email: str,
        status: str,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        client_id: Optional[int] = None,
        company_code: Optional[str] = None,
        user_id: Optional[int] = None
    ):
        from app.models.login_audit import LoginAudit
        audit = LoginAudit(
            user_id=user_id,
            email=email,
            client_id=client_id,
            company_code=company_code,
            ip_address=ip_address or "0.0.0.0",
            user_agent=user_agent or "Unknown",
            status=status,
            failure_reason=reason
        )
        session.add(audit)
        await session.commit()

    @staticmethod
    def logout_user(user_id: str, ip_address: Optional[str] = None):
        log_event(
            user_id=user_id,
            action="LOGOUT",
            entity="User Account",
            source="USER",
            status="SUCCESS",
            ip_address=ip_address
        )
