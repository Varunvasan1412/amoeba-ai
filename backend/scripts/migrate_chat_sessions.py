import asyncio
import sys
import os
import uuid
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

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
            # 1. Create chat_session table if not exists
            print("🔍 Creating 'chat_session' table if it doesn't exist...")
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS chat_session (
                    id SERIAL PRIMARY KEY,
                    client_id INTEGER NOT NULL,
                    session_id VARCHAR NOT NULL UNIQUE,
                    title VARCHAR DEFAULT 'New Chat',
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (now() at time zone 'utc'),
                    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (now() at time zone 'utc')
                )
            """))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_chat_session_client_id ON chat_session (client_id)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_chat_session_session_id ON chat_session (session_id)"))

            # 2. Add client_id and session_id to chatmessage
            print("🔍 Checking columns in 'chatmessage'...")
            
            # Add client_id
            result = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='chatmessage' AND column_name='client_id'"))
            if not result.fetchone():
                print("➕ Adding 'client_id' column to 'chatmessage'...")
                await conn.execute(text("ALTER TABLE chatmessage ADD COLUMN client_id INTEGER"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_chatmessage_client_id ON chatmessage (client_id)"))

            # Add session_id
            result = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='chatmessage' AND column_name='session_id'"))
            if not result.fetchone():
                print("➕ Adding 'session_id' column to 'chatmessage'...")
                await conn.execute(text("ALTER TABLE chatmessage ADD COLUMN session_id VARCHAR"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_chatmessage_session_id ON chatmessage (session_id)"))

            # 3. Data Migration for existing messages
            print("🔄 Migrating existing messages...")
            
            # Find distinct client_id from other tables if possible, otherwise use a default
            # Let's see if we can find a default client
            result = await conn.execute(text("SELECT id FROM clientconfig LIMIT 1"))
            default_client = result.fetchone()
            default_client_id = default_client[0] if default_client else 1
            
            # Update messages with no client_id
            await conn.execute(text(f"UPDATE chatmessage SET client_id = {default_client_id} WHERE client_id IS NULL"))
            
            # For each client, create one default session if they have messages
            result = await conn.execute(text("SELECT DISTINCT client_id FROM chatmessage WHERE session_id IS NULL"))
            clients_to_migrate = result.fetchall()
            
            for row in clients_to_migrate:
                cid = row[0]
                new_session_id = str(uuid.uuid4())
                print(f"📦 Creating default session {new_session_id} for client {cid}...")
                
                await conn.execute(text("INSERT INTO chat_session (client_id, session_id, title) VALUES (:cid, :sid, :title)"), 
                                   {"cid": cid, "sid": new_session_id, "title": "Migrated History"})
                
                await conn.execute(text("UPDATE chatmessage SET session_id = :sid WHERE client_id = :cid AND session_id IS NULL"),
                                   {"sid": new_session_id, "cid": cid})

            print("✅ Migration successful!")
                
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            import traceback
            traceback.print_exc()
            
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate())
