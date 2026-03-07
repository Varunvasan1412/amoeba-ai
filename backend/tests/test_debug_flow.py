import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from app.routers.chat import websocket_endpoint
from app.models.client_config import ClientConfig
from app.models.chat import ChatMessage
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

class MockWebSocket:
    def __init__(self):
        self.sent_messages = []
        self.is_closed = False

    async def accept(self):
        pass

    async def receive_text(self):
        if not hasattr(self, "received"):
            self.received = True
            return "Add customer"
        else:
            # Sleep to simulate long-running or just raise exception to break loop
            await asyncio.sleep(1)
            raise Exception("Mock disconnect")

    async def send_json(self, data):
        self.sent_messages.append(data)
        print(f"DEBUG: Sent to WebSocket: {data}")

    async def close(self, code=1000):
        self.is_closed = True

@pytest.mark.asyncio
async def test_trace_add_customer():
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
        stmt_str = str(statement)
        if "client_config" in stmt_str:
            return mock_result_client
        elif "chatmessage" in stmt_str:
            return mock_result_history
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
    
    # 7. Mock limiter
    from app.core.rate_limiter import limiter
    limiter.check_chat = MagicMock(return_value=True)

    # 8. Run websocket_endpoint
    ws = MockWebSocket()
    try:
        await websocket_endpoint(ws, api_key="test_key")
    except Exception as e:
        print(f"Websocket loop ended: {e}")
        
    # Check if LLM was called
    if app.services.llm_service.get_response.called:
        print("❌ FAILURE: LLM was called for 'Add customer'")
    else:
        print("✅ SUCCESS: LLM was bypassed for 'Add customer'")
        
    # Check if CRUD Assistant was triggered
    # (Checking sent messages)
    found_crud_response = False
    for msg in ws.sent_messages:
        if "To create a new customers, I need some information." in msg.get("text", ""):
            found_crud_response = True
            break
            
    if found_crud_response:
        print("✅ SUCCESS: CRUD Assistant response found")
    else:
        print("❌ FAILURE: CRUD Assistant response NOT found")
