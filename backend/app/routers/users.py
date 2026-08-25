from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from app.core.database import get_session, async_session
from app.models.user import User
from app.models.rbac import Role, Permission, RolePermissionLink
from app.security.permission_guard import require_permission, is_super_admin, get_current_user
from app.services.audit_service import log_event
from app.core.security import get_password_hash
from app.services.user_service import assign_role_to_user

class UpdateUserRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    role_id: Optional[int] = None
    client_id: Optional[int] = None
    is_active: Optional[bool] = None

router = APIRouter(prefix="/users", tags=["User Management"])

@router.get("/", response_model=List[Dict[str, Any]], dependencies=[Depends(require_permission("manage_users"))])
async def list_users(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Lists all users with their roles. Restricted by client_id for non-platform users.
    """
    stmt = select(User)
    if not current_user.is_platform_user:
        stmt = stmt.where(User.client_id == current_user.client_id)
        
    res = await session.execute(stmt)
    users = res.scalars().all()
    
    output = []
    for u in users:
        role_name = "None"
        if u.role_id:
            role_stmt = select(Role).where(Role.id == u.role_id)
            role_res = await session.execute(role_stmt)
            role = role_res.scalar_one_or_none()
            role_name = role.name if role else "None"
            
        output.append({
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "is_active": u.is_active,
            "role_id": u.role_id,
            "role_name": role_name,
            "is_admin": u.is_admin,
            "is_platform_user": u.is_platform_user,
            "client_id": u.client_id
        })
    return output

@router.put("/{user_id}/role", dependencies=[Depends(require_permission("manage_users"))])
async def update_user_role(user_id: int, role_id: int = Body(..., embed=True), current_user: User = Depends(get_current_user)):
    """
    Assigns a role to a user. Uses hardening logic from AuthService.
    """
    from app.services.user_service import assign_role_to_user
    async with async_session() as session:
        user = await assign_role_to_user(session, user_id, role_id, current_user)
        
        log_event(
            user_id=current_user.id,
            action="UPDATE_USER_ROLE",
            entity=f"User: {user.username}",
            table_name="users",
            record_id=str(user_id),
            status="SUCCESS",
            details={"new_role_id": role_id}
        )
        
        return {"success": True, "message": f"Role updated"}

@router.patch("/{user_id}", dependencies=[Depends(require_permission("manage_users"))])
async def update_user(
    user_id: int, 
    payload: UpdateUserRequest, 
    current_user: User = Depends(get_current_user)
):
    """
    Updates user details (username, email, role, company, status).
    """
    async with async_session() as session:
        user = await session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Isolation check: non-platform admins can only update users within their own client
        if not current_user.is_platform_user and user.client_id != current_user.client_id:
             raise HTTPException(status_code=403, detail="Not authorized to manage this user")

        if payload.username is not None:
            # Check if username is already taken by ANOTHER user
            stmt = select(User).where(User.username == payload.username).where(User.id != user_id)
            res = await session.execute(stmt)
            if res.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Username already taken")
            user.username = payload.username

        if payload.email is not None:
            user.email = payload.email

        if payload.is_active is not None:
            user.is_active = payload.is_active

        if payload.role_id is not None:
            from app.services.user_service import assign_role_to_user
            await assign_role_to_user(session, user_id, payload.role_id, current_user)
            # user.role_id is updated inside the service call
        
        if payload.client_id is not None:
            if not current_user.is_platform_user:
                 raise HTTPException(status_code=403, detail="Only platform admins can change user company context")
            user.client_id = payload.client_id if payload.client_id != -1 else None

        session.add(user)
        
        log_event(
            user_id=str(current_user.id),
            action="UPDATE_USER_DETAILS",
            entity=f"User: {user.username}",
            table_name="users",
            record_id=str(user_id),
            status="SUCCESS",
            details=payload.dict(exclude_unset=True)
        )
        
        await session.commit()
        return {"success": True, "message": "User updated successfully"}

@router.get("/roles", dependencies=[Depends(require_permission("manage_users"))])
async def list_roles(session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    """
    Lists all roles and their associated permissions.
    """
    stmt = select(Role)
    if not current_user.is_platform_user:
        # Non-platform users only see global roles (NULL client_id) or their own company's roles
        stmt = stmt.where((Role.client_id == None) | (Role.client_id == current_user.client_id))
    
    res = await session.execute(stmt)
    roles = res.scalars().all()
    
    output = []
    for r in roles:
        # Fetch permissions manually to be safe with async
        perm_stmt = select(Permission).join(RolePermissionLink).where(RolePermissionLink.role_id == r.id)
        perm_res = await session.execute(perm_stmt)
        perms = perm_res.scalars().all()
        
        output.append({
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "permissions": [p.name for p in perms]
        })
    return output

@router.get("/permissions", dependencies=[Depends(require_permission("manage_users"))])
async def list_permissions(session: AsyncSession = Depends(get_session)):
    """
    Lists all available permissions.
    """
    stmt = select(Permission)
    res = await session.execute(stmt)
    return res.scalars().all()

@router.post("/roles", dependencies=[Depends(is_super_admin)])
async def create_role(name: str = Body(...), description: str = Body(None), permissions: List[str] = Body([]), current_user: User = Depends(get_current_user)):
    """
    Creates a new role with permissions.
    """
    async with async_session() as session:
        # Check if role exists in THIS context
        if current_user.is_platform_user:
             stmt = select(Role).where(Role.name == name).where(Role.client_id == None)
        else:
             stmt = select(Role).where(Role.name == name).where(Role.client_id == current_user.client_id)
             
        res = await session.execute(stmt)
        if res.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Role already exists in this context")
            
        # Restriction for Client Admins: Hide platform permissions
        if not current_user.is_platform_user:
            platform_perms = ['access_ai_settings', 'access_health', 'access_backups', 'access_tenants']
            for p in permissions:
                if p in platform_perms:
                    raise HTTPException(status_code=403, detail=f"Permission '{p}' is reserved for platform owners.")
            
        role = Role(
            name=name, 
            description=description, 
            client_id=None if current_user.is_platform_user else current_user.client_id
        )
        session.add(role)
        await session.flush()
        
        # Add permissions
        for p_name in permissions:
            p_stmt = select(Permission).where(Permission.name == p_name)
            p_res = await session.execute(p_stmt)
            perm = p_res.scalar_one_or_none()
            if perm:
                session.add(RolePermissionLink(role_id=role.id, permission_id=perm.id))
        
        log_event(
            user_id=str(current_user.id),
            action="CREATE_ROLE",
            entity=f"Role: {name}",
            table_name="roles",
            record_id=str(role.id),
            status="SUCCESS",
            details={"permissions": permissions}
        )
        
        await session.commit()
        return {"success": True, "role_id": role.id}

@router.put("/roles/{role_id}/permissions", dependencies=[Depends(require_permission("manage_users"))])
async def update_role_permissions(role_id: int, permissions: List[str] = Body(...), current_user: User = Depends(get_current_user)):
    """
    Updates permissions for an existing role.
    """
    async with async_session() as session:
        role = await session.get(Role, role_id)
        if not role:
            raise HTTPException(status_code=404, detail="Role not found")
        
        # Ownership check
        if not current_user.is_platform_user:
             if role.client_id != current_user.client_id:
                  raise HTTPException(status_code=403, detail="You do not have permission to modify this role.")
             
             # Restricted permissions check
             platform_perms = ['access_ai_settings', 'access_health', 'access_backups', 'access_tenants']
             for p in permissions:
                  if p in platform_perms:
                       raise HTTPException(status_code=403, detail=f"Permission '{p}' is reserved for platform owners.")

        # Delete existing links
        del_stmt = select(RolePermissionLink).where(RolePermissionLink.role_id == role_id)
        del_res = await session.execute(del_stmt)
        links = del_res.scalars().all()
        for link in links:
            await session.delete(link)
        
        # Add new links
        for p_name in permissions:
            p_stmt = select(Permission).where(Permission.name == p_name)
            p_res = await session.execute(p_stmt)
            perm = p_res.scalar_one_or_none()
            if perm:
                session.add(RolePermissionLink(role_id=role.id, permission_id=perm.id))
                
        await session.commit()
        return {"success": True}

@router.post("/", dependencies=[Depends(require_permission("manage_users"))])
async def create_user(
    username: str = Body(...),
    email: str = Body(...),
    password: str = Body(...),
    role_id: Optional[int] = Body(None),
    client_id: Optional[int] = Body(None),
    current_user: User = Depends(get_current_user)
):
    """
    Creates a new user account. Restricted by client_id for non-platform users.
    """
    async with async_session() as session:
        # Check if user exists
        stmt = select(User).where((User.username == username) | (User.email == email))
        res = await session.execute(stmt)
        if res.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Username or Email already taken")
            
        target_client_id = client_id
        if not current_user.is_platform_user:
            # Force client_id to current admin's client_id
            target_client_id = current_user.client_id
            
        hashed_pw = get_password_hash(password)
        user = User(
            username=username,
            email=email,
            hashed_password=hashed_pw,
            role_id=role_id,
            client_id=target_client_id,
            is_active=True,
            is_admin=False,
            is_platform_user=False # Default to false for new users
        )
        session.add(user)
        await session.flush()
        
        log_event(
            user_id=str(current_user.id),
            action="CREATE_USER",
            entity=f"User: {username}",
            table_name="users",
            record_id=str(user.id),
            status="SUCCESS",
            details={"role_id": role_id}
        )
        
        await session.commit()
        return {"success": True, "user_id": user.id}

@router.delete("/{user_id}", dependencies=[Depends(require_permission("manage_users"))])
async def delete_user(user_id: int, current_user: User = Depends(get_current_user)):
    """
    Deletes a user account.
    """
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account.")
        
    async with async_session() as session:
        user = await session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        if not current_user.is_platform_user and user.client_id != current_user.client_id:
            raise HTTPException(status_code=403, detail="Not authorized to delete this user")
            
        await session.delete(user)
        
        log_event(
            user_id=str(current_user.id),
            action="DELETE_USER",
            entity=f"User: {user.username}",
            table_name="users",
            record_id=str(user_id),
            status="SUCCESS"
        )
        await session.commit()
        return {"success": True, "message": "User deleted successfully"}

@router.delete("/roles/{role_id}", dependencies=[Depends(require_permission("manage_users"))])
async def delete_role(role_id: int, current_user: User = Depends(get_current_user)):
    """
    Deletes a custom role.
    """
    async with async_session() as session:
        role = await session.get(Role, role_id)
        if not role:
            raise HTTPException(status_code=404, detail="Role not found")
            
        if role.client_id is None:
            raise HTTPException(status_code=403, detail="Global platform roles cannot be deleted.")

        if not current_user.is_platform_user and role.client_id != current_user.client_id:
            raise HTTPException(status_code=403, detail="Not authorized to delete this role")
            
        # Check if users are assigned to this role
        user_stmt = select(User).where(User.role_id == role_id)
        user_res = await session.execute(user_stmt)
        if user_res.scalars().first():
             raise HTTPException(status_code=400, detail="Cannot delete role: users are currently assigned to it.")

        # Delete role permissions links
        del_stmt = select(RolePermissionLink).where(RolePermissionLink.role_id == role_id)
        del_res = await session.execute(del_stmt)
        for link in del_res.scalars().all():
            await session.delete(link)

        await session.delete(role)
        
        log_event(
            user_id=str(current_user.id),
            action="DELETE_ROLE",
            entity=f"Role: {role.name}",
            table_name="roles",
            record_id=str(role_id),
            status="SUCCESS"
        )
        await session.commit()
        return {"success": True}

