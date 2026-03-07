# Amoeba AI v1 FIXED — Do not extend without version bump

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException, Depends, Query
from app.services.llm_service import get_response
from app.core.context import current_db_url
from app.tools.navigation import batch_learn_routes
from typing import List, Dict, Any
from pydantic import BaseModel
from app.core.database import get_session
from app.models.chat import ChatMessage
from app.models.client_config import ClientConfig
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.audit_service import log_audit
from app.core.rate_limiter import limiter


router = APIRouter()

class RouteItem(BaseModel):
    label: str
    path: str

@router.post("/routes/learn")
async def learn_routes_endpoint(routes: List[RouteItem]):
    """Authentication-free endpoint for the widget to dump discovered links."""
    # Convert Pydantic models to dicts
    routes_data = [{"label": r.label, "path": r.path} for r in routes]
    result = batch_learn_routes(routes_data)
    print(f"🧠 {result}")
    return {"status": "success", "message": result}

@router.post("/chat")
async def chat_endpoint(payload: Dict[str, Any]):
    # This endpoint is incomplete in the provided instruction.
    # To make it syntactically correct, I'm adding a pass statement.
    # Please provide the full implementation if you want it to do something.
    pass

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
async def websocket_endpoint(
    websocket: WebSocket,
    api_key: str = Query(None) # Optional for now to not break existing dev
):
    await websocket.accept()
    
    # MANUAL SESSION MANAGEMENT FOR WEBSOCKETS
    async for session in get_session():
        try:
            # 1. CLIENT AUTH (Simple Mock-able Logic)
            if api_key:
                print(f"🔑 Client Connecting with Key: {api_key}")
                # Lookup Client
                result = await session.execute(select(ClientConfig).where(ClientConfig.api_key == api_key))
                client = result.scalars().first()
                if not client:
                    print(f"❌ Client Not Found for API Key: {api_key}")
                    await websocket.close(code=4003)
                    return
                
                # RATE LIMIT CHECK
                if not limiter.check_chat(client.id):
                    await websocket.send_json({"text": "⚠️ You are sending messages too fast. Please wait a moment."})
                    continue

                if client:
                    print(f"✅ Client Verified: {client.client_name}")
                    # Set Context for Tools
                    current_db_url.set(client.db_connection_url)
                    # New: Set Logic Context
                    client_context_id = str(client.id)
                else:
                    print(f"⚠️ Invalid API Key: {api_key}. Tools will fail.")
            else:
                print("⚠️ No API Key provided. Running in Default/Dev Mode.")
                # FIX: Try to find a valid client to mimic
                result = await session.execute(select(ClientConfig))
                client = result.scalars().first()
                
                if client:
                    print(f"✅ Dev Mode: Using Client '{client.client_name}' (ID: {client.id})")
                    current_db_url.set(client.db_connection_url)
                    client_context_id = str(client.id)
                else:
                    print("⚠️ No clients found in DB. Tools may fail.")
                    from app.core.config import settings
                    current_db_url.set(settings.DATABASE_URL)
                    client_context_id = "default"
            
            while True:
                # 2. Receive User Message
                user_text = await websocket.receive_text()
                print(f"📨 WEBSOCKET RECEIVED: {user_text}", flush=True)
                print("DEBUG: STEP 1 - Starting Message Processing")
                
                # Save User Message
                user_msg = ChatMessage(sender="user", content=user_text)
                session.add(user_msg)
                await session.commit()

                # -----------------------------------------------------------------
                # 🚀 ARCHITECTURAL FIX: INTENT ROUTER (BEFORE LLM)
                # -----------------------------------------------------------------
                from app.services.fastpath_service import execute_fastpath
                
                # Check for Fast-Path FIRST (with Context)
                if 'fastpath_context' not in locals():
                    fastpath_context = {"client_id": client_context_id}
                else:
                    fastpath_context["client_id"] = client_context_id
                
                fast_text, fast_actions = await execute_fastpath(user_text, fastpath_context, db_session=session)
                
                if fast_text:
                     # Check for State Updates in Actions
                     new_actions_for_client = []
                     for action in fast_actions:
                         if action["type"] == "SET_AMBIGUITY":
                             fastpath_context["ambiguity_candidates"] = action["payload"]
                         elif action["type"] == "CLEAR_AMBIGUITY":
                             fastpath_context = {}
                         elif action["type"] == "SET_PENDING_REPORT":
                             fastpath_context["pending_report"] = action["payload"]
                         else:
                             new_actions_for_client.append(action)
                             
                             # If we navigated successfully OR generated a report, clear context!
                             if action["type"] == "NAVIGATE" or action["type"] == "TOOL_RESULT":
                                 fastpath_context = {}

                     # Save AI Message
                     ai_msg = ChatMessage(sender="ai", content=fast_text, actions=fast_actions)
                     session.add(ai_msg)
                     await session.commit()
                     
                     # Send Response Directly
                     response_payload = {
                        "text": fast_text,
                        "actions": new_actions_for_client
                     }
                     await websocket.send_json(response_payload)
                     continue # 🛑 TERMINAL: Skip get_response()

                # -----------------------------------------------------------------
                # 🆕 CRUD ASSISTANT (v3 - NO LLM)
                # -----------------------------------------------------------------
                from app.services.intent_service import resolve_crud_intent
                from app.services.conversation_service import process_conversation, get_active_conversation
                
                session_id = f"sess_{client_context_id}" 
                
                # A. Resolve Intent (Keywords + Entity)
                crud_intent = await resolve_crud_intent(user_text, int(client_context_id), session)
                
                # B. Check for existing active CRUD session
                active_crud_state = await get_active_conversation(session, int(client_context_id), session_id)
                
                # C. CRUD HARD GUARD: If keyword found OR active session exists -> BLOCK LLM
                if crud_intent or active_crud_state:
                    crud_text, crud_actions = await process_conversation(user_text, crud_intent, int(client_context_id), session_id, session)
                    
                    if crud_text:
                        ai_msg = ChatMessage(sender="ai", content=crud_text, actions=crud_actions)
                        session.add(ai_msg)
                        await session.commit()
                        
                        await websocket.send_json({
                            "text": crud_text,
                            "actions": crud_actions
                        })
                        continue # 🛑 TERMINAL: Request handled by CRUD engine
                    else:
                        # Safety fallback
                        await websocket.send_json({
                            "text": "I understood your CRUD request but encountered a logic error. Please try a different phrasing.",
                            "actions": []
                        })
                        continue
                # -----------------------------------------------------------------

                # 3. Generate AI Response (SLOW PATH - General Chat Only)
                history_result = await session.execute(
                    select(ChatMessage)
                    .order_by(ChatMessage.timestamp.desc())
                    .limit(10)
                )
                print("🔍 Debug: History select done. Processing scalars...", flush=True)
                # Reverse to chronological order (oldest first)
                recent_history = history_result.scalars().all()[::-1]
                print(f"🔍 Debug: Scalars processed. Found {len(recent_history)} items.", flush=True)
                
                # Exclude the very last user message we just added (to avoid dupes if logic overlaps)
                # Actually, get_response appends user_input manually, so we should exclude the CURRENT message.
                recent_history = [msg for msg in recent_history if msg.content != user_text]
                
                print(f"🤖 Calling get_response with {len(recent_history)} history items...", flush=True)
                ai_text, actions = await get_response(user_text, history=recent_history)
                
                # 3.5 Process Actions & Safety Results
                # If we have "TOOL_RESULT" actions (Safety Net), append them to the text so the user sees them.
                for action in actions:
                    if action["type"] == "TOOL_RESULT":
                         tool_output = action["payload"]
                         # Only append if not already present to avoid duplication
                         if tool_output not in ai_text:
                             print(f"🔗 Appending Safety Net Link to Response: {tool_output}")
                             
                             # BEAUTIFICATION: If it's an image, render it!
                             if "http" in tool_output and ("png" in tool_output or "jpg" in tool_output or "jpeg" in tool_output or "picsum" in tool_output or "unsplash" in tool_output):
                                 # Extract URL from the message (simple heuristic)
                                 import re
                                 url_match = re.search(r'(https?://[^\s]+)', tool_output)
                                 if url_match:
                                     img_url = url_match.group(1)
                                     ai_text += f"\n\n![Generated Image]({img_url})"
                                 else:
                                     ai_text += f"\n\n[System Output]: {tool_output}"
                             else:
                                 ai_text += f"\n\n[System Output]: {tool_output}"

                # Save AI Message
                ai_msg = ChatMessage(sender="ai", content=ai_text, actions=actions)
                session.add(ai_msg)
                await session.commit()

                # 4. Send Back (JSON structured message)
                # We send strict JSON now so frontend can distinguish text vs actions
                response_payload = {
                    "text": ai_text,
                    "actions": actions
                }
                await websocket.send_json(response_payload)
                
        except WebSocketDisconnect:
            print("Client disconnected")
            break # Exit the loop to close session
        except Exception as e:
            print(f"Socket Error: {e}")
            break