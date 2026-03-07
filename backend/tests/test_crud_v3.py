import asyncio
import os
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_session, init_db, engine as db_engine
from app.services.intent_service import resolve_crud_intent
from app.services.conversation_service import process_conversation
from app.models.client_config import ClientConfig
from sqlmodel import select, text
import json

async def setup_test_data(session: AsyncSession):
    # Create a test client pointing to THIS database for testing
    # Note: Using psycopg2-binary for discovery (synchronous)
    # The asyncpg url should be replaced with its sync counterpart for ClientConfig.db_connection_url
    current_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5435/amoeba")
    sync_url = current_url.replace("asyncpg", "psycopg2")
    
    result = await session.execute(select(ClientConfig).where(ClientConfig.api_key == "crud_test_key"))
    client = result.scalars().first()
    
    if not client:
        print("🌱 Creating CRUD Test Client...")
        client = ClientConfig(
            client_name="CRUD Test Client",
            api_key="crud_test_key",
            db_connection_url=sync_url
        )
        session.add(client)
        await session.commit()
    
    # Create a test 'customers' table for CRUD testing
    print("🏗️ Creating 'customers' table for tests...")
    async with db_engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS customers (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL,
                phone VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
    
    return client

async def test_crud_flow():
    print("🚀 Starting CRUD v3 Integration Test")
    
    # Initialize DB (create tables)
    await init_db()
    
    async for session in get_session():
        client = await setup_test_data(session)
        client_id = client.id
        session_id = f"test_sess_{client_id}"
        
        print(f"✅ Testing with Client: {client.client_name} (ID: {client_id})")
        
        # --- TEST 1: READ INTENT ---
        print("\n--- TEST 1: READ INTENT ---")
        query = "show customers"
        intent = await resolve_crud_intent(query, client_id, session)
        print(f"Intent Resolved: {intent}")
        
        if intent:
            text_res, actions = await process_conversation(query, intent, client_id, session_id, session)
            print(f"Response: {text_res}")
            print(f"Actions: {actions}")
        else:
            print("❌ Intent not resolved for 'show customers'")

        # --- TEST 2: CREATE INTENT ---
        print("\n--- TEST 2: CREATE INTENT ---")
        query = "Add a new customer"
        intent = await resolve_crud_intent(query, client_id, session)
        print(f"Intent Resolved: {intent}")
        
        if intent:
            # 2.1 Start
            print("--- Step 1: Start ---")
            text_res, actions = await process_conversation(query, intent, client_id, session_id, session)
            print(f"Response: {text_res}")
            print(f"Actions: {actions}")
            
            # 2.2 Submit Form
            print("\n--- Step 2: Submit Form ---")
            form_data = '{"name": "Alice Wonderland", "email": "alice@wonder.com", "phone": "555-0123"}'
            text_res2, actions2 = await process_conversation(form_data, None, client_id, session_id, session)
            print(f"Response: {text_res2}")
            print(f"Actions: {actions2}")
        else:
            print("❌ Intent not resolved for 'Add a new customer'")

        # --- TEST 3: UPDATE INTENT ---
        print("\n--- TEST 3: UPDATE INTENT ---")
        # Let's assume the ID is 1 (as it's the first one we created)
        query = "Update customer 1"
        intent = await resolve_crud_intent(query, client_id, session)
        print(f"Intent Resolved: {intent}")
        
        if intent:
            # 3.1 Start
            print("--- Step 1: Start ---")
            text_res, actions = await process_conversation(query, intent, client_id, session_id, session)
            print(f"Response: {text_res}")
            print(f"Actions: {actions}")
            
            # 3.2 Submit Form
            print("\n--- Step 2: Submit Form ---")
            update_data = '{"phone": "999-9999"}'
            text_res2, actions2 = await process_conversation(update_data, None, client_id, session_id, session)
            print(f"Response: {text_res2}")
            print(f"Actions: {actions2}")
            
            # 3.3 Confirm (REQUIRED in v3)
            print("\n--- Step 3: Confirm ---")
            text_res3, actions3 = await process_conversation("Yes", None, client_id, session_id, session)
            print(f"Response: {text_res3}")
            print(f"Actions: {actions3}")
        else:
            print("❌ Intent not resolved for 'Update customer 1'")

        # --- TEST 4: DELETE INTENT ---
        print("\n--- TEST 4: DELETE INTENT ---")
        query = "Delete customer 1"
        intent = await resolve_crud_intent(query, client_id, session)
        print(f"Intent Resolved: {intent}")
        
        if intent:
            # 4.1 Start
            print("--- Step 1: Start ---")
            text_res, actions = await process_conversation(query, intent, client_id, session_id, session)
            print(f"Response: {text_res}")
            print(f"Actions: {actions}")
            
            # 4.2 Confirm (REQUIRED)
            print("\n--- Step 2: Confirm ---")
            text_res2, actions2 = await process_conversation("Yes", None, client_id, session_id, session)
            print(f"Response: {text_res2}")
            print(f"Actions: {actions2}")
        else:
            print("❌ Intent not resolved for 'Delete customer 1'")

        break # Only test one session

if __name__ == "__main__":
    asyncio.run(test_crud_flow())
