import asyncio
from unittest.mock import MagicMock, AsyncMock
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# MOCK Rate Limiter before importing chat
from app.core.rate_limiter import limiter
limiter.check_chat = MagicMock(return_value=True)

from app.routers.chat import websocket_endpoint
from app.models.client_config import ClientConfig
from app.models.chat import ChatMessage
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

class MockWebSocket:
    def __init__(self, query_text):
        self.sent_messages = []
        self.is_closed = False
        self.query_text = query_text
        self.received = False

    async def accept(self):
        print("WS ACCEPTED")

    async def receive_text(self):
        if not self.received:
            self.received = True
            print(f"WS RECEIVED: {self.query_text}")
            return self.query_text
        else:
            # Simulate disconnect
            print("WS DISCONNECT SIMULATED")
            raise Exception("Mock disconnect")

    async def send_json(self, data):
        self.sent_messages.append(data)
        print(f"WS SENT: {data}")

    async def close(self, code=1000):
        self.is_closed = True
        print(f"WS CLOSED: {code}")

async def run_trace():
    print("🚀 STARTING TRACE for 'Add customer'...")
    
    # 1. Mock DB Session
    mock_session = AsyncMock(spec=AsyncSession)
    
    # 2. Mock ClientConfig lookup
    mock_client = ClientConfig(
        id=1,
        client_name="Test Client",
        api_key="test_key",
        db_connection_url="sqlite:///test_erp.db"
    )
    
    # Mock session.execute for ClientConfig
    mock_result_client = MagicMock()
    mock_result_client.scalars.return_value.first.return_value = mock_client
    mock_session.execute.return_value = mock_result_client
    
    # Mock session.execute for History (empty for now)
    mock_result_history = MagicMock()
    mock_result_history.scalars.return_value.all.return_value = []
    
    # Handle multiple calls to session.execute
    def side_effect_execute(statement, *args, **kwargs):
        stmt_str = str(statement).lower()
        if "clientconfig" in stmt_str or "client_config" in stmt_str:
            return mock_result_client
        elif "chatmessage" in stmt_str:
            return mock_result_history
        elif "conversationstate" in stmt_str:
             # Return no active conversation
             mock_state = MagicMock()
             mock_state.scalars.return_value.first.return_value = None
             return mock_state
        return MagicMock()
        
    mock_session.execute.side_effect = side_effect_execute
    mock_session.get.return_value = mock_client

    # 3. Mock get_session generator
    async def mock_get_session():
        yield mock_session
    
    # Patch get_session in chat.py
    import app.routers.chat
    app.routers.chat.get_session = mock_get_session
    
    # 4. Mock execute_fastpath to return (None, [])
    import app.services.fastpath_service
    app.services.fastpath_service.execute_fastpath = AsyncMock(return_value=(None, []))
    
    # 5. Mock discover_tables (used in resolve_crud_intent)
    import app.services.onboarding
    app.services.onboarding.discover_tables = MagicMock(return_value=[{"name": "customers", "columns": ["id", "name"]}])
    
    # 6. Mock get_response (LLM) to detect if it's called
    import app.services.llm_service
    app.services.llm_service.get_response = AsyncMock(return_value=("LLM Response", []))

    # 7. Mock get_table_columns (to avoid real DB connection)
    import app.services.conversation_service
    app.services.conversation_service.get_table_columns = AsyncMock(return_value=["id", "name", "email"])

    # 8. Run websocket_endpoint
    ws = MockWebSocket("Add potato")
    try:
        await websocket_endpoint(ws, api_key="test_key")
    except Exception as e:
        print(f"Websocket loop ended: {e}")
        
    # VERDICT
    print("\n--- TRACE VERDICT ---")
    if app.services.llm_service.get_response.called:
        print("❌ FAILURE: LLM was called! (Leak confirmed in mock)")
    else:
        print("✅ SUCCESS: LLM was bypassed. (No leak in mock)")
        
    found_clarification = False
    for msg in ws.sent_messages:
        if "I understand you want to create something, but I couldn't find that entity" in msg.get("text", ""):
            found_clarification = True
            break
            
    if found_clarification:
        print("✅ SUCCESS: Clarification response found.")
    else:
        print("❌ FAILURE: Clarification response NOT found.")

if __name__ == "__main__":
    asyncio.run(run_trace())
