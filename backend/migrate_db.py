import asyncio
from app.core.database import engine
from sqlalchemy import text, inspect

async def migrate():
    print("🚀 Starting Manual Migration...")
    async with engine.begin() as conn:
        def get_cols(sync_conn, table_name):
            inspector = inspect(sync_conn)
            if not inspector.has_table(table_name):
                return []
            return [col['name'] for col in inspector.get_columns(table_name)]

        # Table 'users'
        try:
            print("Checking 'users' table columns...")
            cols = await conn.run_sync(get_cols, 'users')
            
            if cols and "email" not in cols:
                print("Adding 'email' to users...")
                await conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR"))
            
            if cols and "is_platform_user" not in cols:
                print("Adding 'is_platform_user' to users...")
                await conn.execute(text("ALTER TABLE users ADD COLUMN is_platform_user BOOLEAN DEFAULT FALSE"))
                
            if cols and "client_id" not in cols:
                print("Adding 'client_id' to users...")
                await conn.execute(text("ALTER TABLE users ADD COLUMN client_id INTEGER"))
        except Exception as e:
            print(f"Error migrating users: {e}")

        # Table 'clientconfig'
        try:
            print("Checking 'clientconfig' table columns...")
            cols = await conn.run_sync(get_cols, 'clientconfig')
            
            if cols and "company_code" not in cols:
                print("Adding 'company_code' to clientconfig...")
                await conn.execute(text("ALTER TABLE clientconfig ADD COLUMN company_code VARCHAR"))
                
            if cols and "onboarding_completed" not in cols:
                print("Adding 'onboarding_completed' to clientconfig...")
                await conn.execute(text("ALTER TABLE clientconfig ADD COLUMN onboarding_completed BOOLEAN DEFAULT FALSE"))
                
            if cols and "assistant_enabled" not in cols:
                print("Adding 'assistant_enabled' to clientconfig...")
                await conn.execute(text("ALTER TABLE clientconfig ADD COLUMN assistant_enabled BOOLEAN DEFAULT FALSE"))
                
            if cols and "operations_enabled" not in cols:
                print("Adding 'operations_enabled' to clientconfig...")
                await conn.execute(text("ALTER TABLE clientconfig ADD COLUMN operations_enabled BOOLEAN DEFAULT FALSE"))
                
            if cols and "schema_rag_enabled" not in cols:
                print("Adding 'schema_rag_enabled' to clientconfig...")
                await conn.execute(text("ALTER TABLE clientconfig ADD COLUMN schema_rag_enabled BOOLEAN DEFAULT TRUE"))
                
            if cols and "schema_synced" not in cols:
                print("Adding 'schema_synced' to clientconfig...")
                await conn.execute(text("ALTER TABLE clientconfig ADD COLUMN schema_synced BOOLEAN DEFAULT FALSE"))
                
        except Exception as e:
            print(f"Error migrating clientconfig: {e}")

    print("✅ Migration Complete.")

if __name__ == "__main__":
    asyncio.run(migrate())
