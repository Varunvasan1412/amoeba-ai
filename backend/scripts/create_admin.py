
import asyncio
from sqlmodel import select
from app.core.database import engine
from app.models.user import User
from app.core.security import get_password_hash
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

async def create_admin():
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        result = await session.execute(select(User).where(User.username == "admin"))
        existing = result.scalars().first()
        
        if not existing:
            print("👤 Creating Admin User...")
            admin_user = User(
                username="Admin@ahattrickz#2026",
                hashed_password=get_password_hash("1Q2w3e4r@#123"),
                is_admin=True,
                is_active=True
            )
            session.add(admin_user)
            await session.commit()
            print("✅ Admin User 'admin' created with password 'admin'")
        else:
            print("👤 Admin user already exists. Updating password to 'admin'...")
            existing.hashed_password = get_password_hash("admin")
            existing.is_admin = True
            existing.is_active = True
            session.add(existing)
            await session.commit()
            print("✅ Admin User 'admin' password updated to 'admin'")

if __name__ == "__main__":
    asyncio.run(create_admin())
