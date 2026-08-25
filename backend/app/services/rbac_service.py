from sqlmodel import select
from app.core.database import async_session
from app.models.rbac import Role, Permission, RolePermissionLink
from app.models.user import User
from app.core.security import get_password_hash

async def seed_rbac_data():
    """
    Initializes default roles and permissions in the database.
    """
    async with async_session() as session:
        # 1. Define Permissions
        permissions_data = [
            ("create_record", "Allow creating new database entries"),
            ("update_record", "Allow updating existing database entries"),
            ("delete_record", "Allow deleting records (non-system)"),
            ("restore_backup", "Allow restoring system backups"),
            ("delete_system_data", "Allow deleting backups and critical system files"),
            ("upload_document", "Allow uploading files to knowledge base"),
            ("view_logs", "Allow viewing system and audit logs"),
            ("manage_users", "Allow creating and editing users/roles"),
            ("configure_system", "Allow changing system settings and schedules"),
        ]
        
        perms_map = {}
        for name, desc in permissions_data:
            stmt = select(Permission).where(Permission.name == name)
            res = await session.execute(stmt)
            perm = res.scalar_one_or_none()
            if not perm:
                perm = Permission(name=name, description=desc)
                session.add(perm)
                await session.flush()
            perms_map[name] = perm

        # 2. Define Roles and their Permission mappings
        roles_data = {
            "SUPER_ADMIN": list(perms_map.keys()),
            "ADMIN": ["create_record", "update_record", "delete_record", "upload_document", "view_logs", "manage_users"],
            "OPERATOR": ["create_record", "update_record", "upload_document"],
            "VIEWER": [],
            "AUDITOR": ["view_logs"]
        }

        for role_name, allowed_perms in roles_data.items():
            stmt = select(Role).where(Role.name == role_name)
            res = await session.execute(stmt)
            role = res.scalar_one_or_none()
            if not role:
                role = Role(name=role_name, description=f"Default {role_name} role")
                session.add(role)
                await session.flush()
            
            # Map permissions
            for p_name in allowed_perms:
                perm = perms_map[p_name]
                # Check if link exists
                link_stmt = select(RolePermissionLink).where(
                    RolePermissionLink.role_id == role.id,
                    RolePermissionLink.permission_id == perm.id
                )
                link_res = await session.execute(link_stmt)
                if not link_res.scalar_one_or_none():
                    session.add(RolePermissionLink(role_id=role.id, permission_id=perm.id))

        await session.commit()

        # 3. Create Default Platform User: you@amoeba.ai
        # Password: admin123
        platform_user_stmt = select(User).where(User.email == "you@amoeba.ai")
        platform_user_res = await session.execute(platform_user_stmt)
        platform_user = platform_user_res.scalar_one_or_none()
        
        if not platform_user:
            super_admin_role_stmt = select(Role).where(Role.name == "SUPER_ADMIN")
            super_admin_role_res = await session.execute(super_admin_role_stmt)
            super_admin_role = super_admin_role_res.scalar_one()
            
            platform_user = User(
                username="amoeba_admin",
                email="you@amoeba.ai",
                hashed_password=get_password_hash("admin123"),
                is_active=True,
                is_admin=True,
                is_platform_user=True,
                role_id=super_admin_role.id
            )
            session.add(platform_user)
            await session.commit()
            print("🚀 Platform Super Admin seeded: you@amoeba.ai / admin123")

        # 4. Assign SUPER_ADMIN to any existing 'is_admin' users if they don't have a role
        stmt = select(User).where(User.is_admin == True, User.role_id == None)
        res = await session.execute(stmt)
        admin_users = res.scalars().all()
        
        if admin_users:
            role_stmt = select(Role).where(Role.name == "SUPER_ADMIN")
            role_res = await session.execute(role_stmt)
            super_role = role_res.scalar_one()
            for u in admin_users:
                u.role_id = super_role.id
                session.add(u)
            await session.commit()

async def get_user_permissions(user_id: int) -> list[str]:
    """
    Returns a flat list of permission names for a given user.
    """
    async with async_session() as session:
        stmt = select(User).where(User.id == user_id)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()
        
        if not user or not user.role_id:
            return []
            
        role_stmt = select(Role).where(Role.id == user.role_id)
        role_res = await session.execute(role_stmt)
        role = role_res.scalar_one_or_none()
        
        if not role:
            return []
            
        # Manually fetch permissions to avoid lazy loading
        perm_stmt = select(Permission).join(RolePermissionLink).where(RolePermissionLink.role_id == role.id)
        perm_res = await session.execute(perm_stmt)
        return [p.name for p in perm_res.scalars().all()]
