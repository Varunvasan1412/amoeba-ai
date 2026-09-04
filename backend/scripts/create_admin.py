
import asyncio
from sqlmodel import select
from app.core.database import engine
from app.models.user import User
from app.core.security import get_password_hash
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.rbac import Role

async def create_admin():
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        # Get or Create SUPER_ADMIN role
        role_result = await session.execute(select(Role).where(Role.name == "SUPER_ADMIN"))
        super_admin_role = role_result.scalars().first()
        if not super_admin_role:
            super_admin_role = Role(name="SUPER_ADMIN", description="Platform Super Admin")
            session.add(super_admin_role)
            await session.commit()

        result = await session.execute(select(User).where(User.username == "admin"))
        existing = result.scalars().first()
        
        if not existing:
            print("👤 Creating Admin User...")
            admin_user = User(
                username="Admin@ahattrickz#2026",
                hashed_password=get_password_hash("1Q2w3e4r@#123"),
                is_admin=True,
                is_platform_user=True,
                is_active=True,
                role_id=super_admin_role.id
            )
            session.add(admin_user)
            await session.commit()
            print("✅ Admin User created successfully!")
        else:
            print("👤 Admin user already exists. Updating credentials and permissions...")
            existing.hashed_password = get_password_hash("1Q2w3e4r@#123")
            existing.is_admin = True
            existing.is_platform_user = True
            existing.is_active = True
            existing.role_id = super_admin_role.id
            session.add(existing)
            await session.commit()
            print("✅ Admin User credentials and permissions updated!")

if __name__ == "__main__":
    asyncio.run(create_admin())
