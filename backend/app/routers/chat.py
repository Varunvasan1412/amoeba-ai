from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from app.services.llm_service import get_response
from app.core.database import get_session
from app.models.chat import ChatMessage
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

router = APIRouter()

# --- HISTORY ENDPOINT ---
@router.get("/history", response_model=List[ChatMessage])
async def get_history(session: AsyncSession = Depends(get_session)):
    try:
        # Fetch all messages sorted by time
        result = await session.execute(select(ChatMessage).order_by(ChatMessage.timestamp))
        messages = result.scalars().all()
        print(f"📜 HISTORY REQUEST: Returning {len(messages)} messages")
        return messages
    except Exception as e:
        print(f"❌ Error fetching history: {e}")
        return []

# --- WEBSOCKET CHAT ---
@router.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # MANUAL SESSION MANAGEMENT FOR WEBSOCKETS
    # We must manually enter the async context manager
    async for session in get_session():
        try:
            while True:
                # 1. Receive User Message
                user_text = await websocket.receive_text()
                
                # Save User Message
                user_msg = ChatMessage(sender="user", content=user_text)
                session.add(user_msg)
                await session.commit()

                # 2. Generate AI Response
                ai_text = get_response(user_text)
                
                # Save AI Message
                ai_msg = ChatMessage(sender="ai", content=ai_text)
                session.add(ai_msg)
                await session.commit()

                # 3. Send Back
                await websocket.send_text(ai_text)
                
        except WebSocketDisconnect:
            print("Client disconnected")
            break # Exit the loop to close session
        except Exception as e:
            print(f"Socket Error: {e}")
            break