import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from app.core.config import settings

async def migrate():
    url = settings.DATABASE_URL
    # Fallback for local execution outside docker
    if "@db:5432" in url:
        url = url.replace("@db:5432", "@localhost:5435")
        
    print(f"🚀 Connecting to {url}...")
    engine = create_async_engine(url)
    
    async with engine.begin() as conn:
        try:
            print("🔍 Checking if 'actions' column exists in 'chatmessage'...")
            # Check if column exists
            result = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='chatmessage' AND column_name='actions'"))
            column_exists = result.fetchone()
            
            if not column_exists:
                print("➕ Adding 'actions' column to 'chatmessage' table...")
                await conn.execute(text("ALTER TABLE chatmessage ADD COLUMN actions JSONB DEFAULT '[]'::jsonb"))
                print("✅ Migration successful!")
            else:
                print("✅ Column 'actions' already exists. Skipping.")
                
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate())
