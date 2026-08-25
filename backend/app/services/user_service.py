from fastapi import HTTPException
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.models.rbac import Role
import logging

logger = logging.getLogger(__name__)

async def assign_role_to_user(session: AsyncSession, user_id: int, role_id: int, current_user: User):
    """
    Assigns a role to a user with strict multi-tenant validation.
    """
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # 1. Isolation check: Can current user manage this target user?
    if not current_user.is_platform_user and user.client_id != current_user.client_id:
        raise HTTPException(status_code=403, detail="Not authorized to manage this user")

    role = await session.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    # 2. FEATURE 2 — CROSS-TENANT ROLE ASSIGNMENT PROTECTION
    if not current_user.is_platform_user:
        # Prevent assigning roles from another tenant
        if role.client_id is not None and role.client_id != current_user.client_id:
            logger.warning(f"Blocked cross-tenant role assignment attempt by user {current_user.id}")
            raise HTTPException(
                status_code=403,
                detail="Cannot assign role from another tenant"
            )
        
        # Prevent assigning platform roles like SUPER_ADMIN
        if role.client_id is None:
            # We allow global roles like 'ADMIN' if it's a global public role?
            # User specifically mentioned SUPER_ADMIN block.
            if role.name == "SUPER_ADMIN":
                logger.warning(f"Blocked SUPER_ADMIN assignment attempt by user {current_user.id}")
                raise HTTPException(
                    status_code=403,
                    detail="SUPER_ADMIN role cannot be assigned"
                )
            
            # If the architecture says client admins can ONLY assign roles with their client_id
            # then we should check if they can assign NULL client_id roles.
            # Usually 'ADMIN' (Global) is allowed, but 'SUPER_ADMIN' is not.

    old_role_id = user.role_id
    user.role_id = role_id
    session.add(user)
    await session.commit()
    return user
