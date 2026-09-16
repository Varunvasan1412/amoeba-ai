import asyncio
from app.core.database import engine
from sqlalchemy import text

async def migrate():
    print("🚀 Starting Manual Migration...")
    async with engine.begin() as conn:
        # Table 'users' (The model says __tablename__ = "users")
        try:
            print("Checking 'users' table columns...")
            # SQLite specific check
            res = await conn.execute(text("PRAGMA table_info(users)"))
            cols = [r[1] for r in res.fetchall()]
            
            if "email" not in cols:
                print("Adding 'email' to users...")
                await conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR"))
            
            if "is_platform_user" not in cols:
                print("Adding 'is_platform_user' to users...")
                await conn.execute(text("ALTER TABLE users ADD COLUMN is_platform_user BOOLEAN DEFAULT 0"))
                
            if "client_id" not in cols:
                print("Adding 'client_id' to users...")
                await conn.execute(text("ALTER TABLE users ADD COLUMN client_id INTEGER"))
        except Exception as e:
            print(f"Error migrating users: {e}")

        # Table 'clientconfig'
        try:
            print("Checking 'clientconfig' table columns...")
            res = await conn.execute(text("PRAGMA table_info(clientconfig)"))
            cols = [r[1] for r in res.fetchall()]
            
            if "company_code" not in cols:
                print("Adding 'company_code' to clientconfig...")
                await conn.execute(text("ALTER TABLE clientconfig ADD COLUMN company_code VARCHAR"))
                
            if "onboarding_completed" not in cols:
                print("Adding 'onboarding_completed' to clientconfig...")
                await conn.execute(text("ALTER TABLE clientconfig ADD COLUMN onboarding_completed BOOLEAN DEFAULT 0"))
                
            if "assistant_enabled" not in cols:
                print("Adding 'assistant_enabled' to clientconfig...")
                await conn.execute(text("ALTER TABLE clientconfig ADD COLUMN assistant_enabled BOOLEAN DEFAULT 0"))
                
            if "operations_enabled" not in cols:
                print("Adding 'operations_enabled' to clientconfig...")
                await conn.execute(text("ALTER TABLE clientconfig ADD COLUMN operations_enabled BOOLEAN DEFAULT 0"))
                
            if "schema_rag_enabled" not in cols:
                print("Adding 'schema_rag_enabled' to clientconfig...")
                await conn.execute(text("ALTER TABLE clientconfig ADD COLUMN schema_rag_enabled BOOLEAN DEFAULT 1"))
                
            if "schema_synced" not in cols:
                print("Adding 'schema_synced' to clientconfig...")
                await conn.execute(text("ALTER TABLE clientconfig ADD COLUMN schema_synced BOOLEAN DEFAULT 0"))
                
        except Exception as e:
            print(f"Error migrating clientconfig: {e}")

    print("✅ Migration Complete.")

if __name__ == "__main__":
    asyncio.run(migrate())
