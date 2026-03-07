
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.services.intent_service import resolve_crud_intent
from app.models.client_config import ClientConfig
from app.core.config import settings
from sqlmodel import SQLModel

async def repro():
    # Setup in-memory DB for ClientConfig
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        # Create a client with a placeholder DB URL
        client = ClientConfig(
            id=1,
            client_name="Test Client",
            api_key="test_key",
            db_connection_url="postgresql+asyncpg://user:password@localhost/dbname" # Placeholder
        )
        session.add(client)
        await session.commit()
        
        print("Testing 'Add customer' with placeholder DB URL...")
        intent = await resolve_crud_intent("Add customer", 1, session)
        print(f"Result: {intent}")
        
        if intent is None:
            print("✅ Reproduced: Intent resolution failed (returned None).")
        else:
            print("❌ Not Reproduced: Intent resolution succeeded.")

if __name__ == "__main__":
    asyncio.run(repro())
