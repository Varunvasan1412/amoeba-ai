
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select
from app.models.allowed_relationship import AllowedRelationship
from app.services.relationship_service import bulk_update_relationships
import os

# Database URL from environment or fallback
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/amoeba")

async def test_bulk():
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # 1. Get a client_id that has relationships
        stmt = select(AllowedRelationship.client_id).limit(1)
        client_id = (await session.execute(stmt)).scalar()
        
        if not client_id:
            print("No clients with relationships found.")
            return

        print(f"Testing for client_id: {client_id}")
        
        # 2. Test Enable All
        print("Running enable_all...")
        res = await bulk_update_relationships(session, client_id, "enable_all")
        print(f"Result: {res}")
        
        # Verify
        stmt = select(AllowedRelationship).where(AllowedRelationship.client_id == client_id)
        rels = (await session.execute(stmt)).scalars().all()
        enabled_count = sum(1 for r in rels if r.is_enabled)
        print(f"Total: {len(rels)}, Enabled after enable_all: {enabled_count}")
        
        # 3. Test Disable All
        print("Running disable_all...")
        res = await bulk_update_relationships(session, client_id, "disable_all")
        print(f"Result: {res}")
        
        # Verify
        stmt = select(AllowedRelationship).where(AllowedRelationship.client_id == client_id)
        rels = (await session.execute(stmt)).scalars().all()
        enabled_count = sum(1 for r in rels if r.is_enabled)
        print(f"Total: {len(rels)}, Enabled after disable_all: {enabled_count}")

if __name__ == "__main__":
    asyncio.run(test_bulk())
