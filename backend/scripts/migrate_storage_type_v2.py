import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
import os

# Manual override for local run
DB_URL = "postgresql+asyncpg://user:password@localhost:5432/amoeba"

async def migrate():
    print(f"🚀 Starting Migration: Adding 'storage_type' to 'field_metadata' on {DB_URL}...")
    engine = create_async_engine(DB_URL)
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE field_metadata ADD COLUMN IF NOT EXISTS storage_type VARCHAR DEFAULT 'string'"))
            print("✅ Migration Successful!")
        except Exception as e:
            print(f"❌ Migration Failed: {e}")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate())
