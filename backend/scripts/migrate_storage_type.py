import asyncio
from sqlalchemy import text
from app.core.database import engine

async def migrate():
    print("🚀 Starting Migration: Adding 'storage_type' to 'field_metadata'...")
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE field_metadata ADD COLUMN IF NOT EXISTS storage_type VARCHAR DEFAULT 'string'"))
            print("✅ Migration Successful!")
        except Exception as e:
            print(f"❌ Migration Failed: {e}")

if __name__ == "__main__":
    asyncio.run(migrate())
