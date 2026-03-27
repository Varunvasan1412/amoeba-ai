from sqlmodel import select
from app.models.client_config import ClientConfig
from app.core.database import engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

async def seed_data():
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        result = await session.execute(select(ClientConfig).where(ClientConfig.api_key == "test_client_key_123"))
        existing = result.scalars().first()
        if not existing:
            print("🌱 Seeding Test Client...")
            new_client = ClientConfig(
                client_name="Test ERP Client",
                api_key="test_client_key_123",
                db_connection_url="postgresql+asyncpg://user:password@localhost/dbname" # Placeholder
            )
            session.add(new_client)
            await session.commit()
            print(f"✅ Created Test Client with ID: {new_client.id}")
        else:
            print(f"✅ Test Client already exists (ID: {existing.id})")
