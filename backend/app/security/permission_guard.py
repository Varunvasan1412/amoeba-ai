from fastapi import Depends, HTTPException, status
from app.core.auth_deps import get_current_user
from app.models.user import User
from app.services.rbac_service import get_user_permissions

def require_permission(permission_name: str):
    """
    FastAPI dependency factory to enforce RBAC permissions.
    """
    async def permission_checker(current_user: User = Depends(get_current_user)):
        permissions = await get_user_permissions(current_user.id)
        
        # SUPER_ADMIN bypass or explicit permission check
        if "SUPER_ADMIN" == getattr(current_user.role, "name", None) or permission_name in permissions:
            return current_user
            
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing required permission: {permission_name}"
        )
        
    return permission_checker

async def is_super_admin(current_user: User = Depends(get_current_user)):
    """
    Helper dependency for SUPER_ADMIN only access.
    """
    if getattr(current_user.role, "name", None) != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super Admin access required"
        )
    return current_user
