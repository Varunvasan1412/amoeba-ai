# Amoeba AI v1 FIXED — Do not extend without version bump

import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException, Depends, Query
import traceback
from app.services.llm_service import get_response
from app.core.context import current_db_url
from app.tools.navigation import batch_learn_routes
from typing import List, Dict, Any
from pydantic import BaseModel
from app.core.database import get_session
from app.models.chat import ChatMessage
from app.models.chat_session import ChatSession
from app.models.client_config import ClientConfig
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.audit_service import log_audit
from app.core.rate_limiter import limiter


router = APIRouter()

# --- PUBLIC AI CONFIG (for chat widget indicator) ---
@router.get("/ai-config")
async def get_ai_config(
    api_key: str = Query(...),
    session: AsyncSession = Depends(get_session)
):
    """Returns the AI provider & model configured for this client. Used by the chat widget."""
    from app.models.ai_settings import AISettings
    result = await session.execute(select(ClientConfig).where(ClientConfig.api_key == api_key))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    
    stmt = select(AISettings).where(AISettings.client_id == client.id)
    ai_settings = (await session.execute(stmt)).scalars().first()
    
    if ai_settings:
        return {"provider": ai_settings.provider, "model": ai_settings.model}
    else:
        from app.core.config import settings
        return {"provider": settings.AI_PROVIDER, "model": settings.OLLAMA_MODEL}

class RouteItem(BaseModel):
    label: str
    path: str

@router.post("/routes/learn")
async def learn_routes_endpoint(
    routes: List[RouteItem], 
    api_key: str = Query(...),
    session: AsyncSession = Depends(get_session)
):
    """Saves discovered links for a specific client."""
    # 1. Verify Client
    result = await session.execute(select(ClientConfig).where(ClientConfig.api_key == api_key))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=403, detail="Invalid API Key")

    # 2. Convert and Learn
    routes_data = [{"label": r.label, "path": r.path} for r in routes]
    result_msg = await batch_learn_routes(routes_data, session, client.id)
    print(f"🧠 {result_msg}")
    return {"status": "success", "message": result_msg}

@router.post("/chat")
async def chat_endpoint(payload: Dict[str, Any]):
    # This endpoint is incomplete in the provided instruction.
    # To make it syntactically correct, I'm adding a pass statement.
    # Please provide the full implementation if you want it to do something.
    pass

# --- HISTORY ENDPOINT ---
@router.get("/history", response_model=List[ChatMessage])
async def get_history(
    api_key: str = Query(...),
    session_id: str = Query(...),
    session: AsyncSession = Depends(get_session)
):
    try:
        # 1. Verify Client
        result = await session.execute(select(ClientConfig).where(ClientConfig.api_key == api_key))
        client = result.scalars().first()
        if not client:
            raise HTTPException(status_code=403, detail="Invalid API Key")

        # 2. Fetch messages for this client and session
        result = await session.execute(
            select(ChatMessage)
            .where(ChatMessage.client_id == client.id)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.timestamp)
        )
        messages = result.scalars().all()
        print(f"📜 HISTORY REQUEST: Returning {len(messages)} messages for session {session_id}")
        
        # Log History Load
        log_audit(client.id, "CHAT_HISTORY_LOADED", {"session_id": session_id, "count": len(messages)})
        
        return messages
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error fetching history: {e}")
        return []

# --- WEBSOCKET CHAT ---
@router.websocket("/ws/chat")
async def websocket_endpoint(
    websocket: WebSocket,
    api_key: str = Query(None)
):
    await websocket.accept()
    
    async for session in get_session():
        try:
            # 1. AUTH & CONTEXT
            client = None
            if api_key:
                result = await session.execute(select(ClientConfig).where(ClientConfig.api_key == api_key))
                client = result.scalars().first()
                if not client:
                    await websocket.close(code=4003)
                    return
                current_db_url.set(client.db_connection_url)
                client_id = client.id
                client_context_id = str(client.id)
            else:
                # Fallback / Dev Mode
                result = await session.execute(select(ClientConfig))
                client = result.scalars().first()
                if client:
                    current_db_url.set(client.db_connection_url)
                    client_id = client.id
                    client_context_id = str(client.id)
                else:
                    from app.core.config import settings
                    current_db_url.set(settings.DATABASE_URL)
                    client_id = 0
                    client_context_id = "default"

            # 2. MESSAGE LOOP
            while True:
                try:
                    raw_data = await websocket.receive_text()
                except WebSocketDisconnect:
                    print("🔴 WebSocket Disconnected by Client")
                    break
                except Exception as e:
                    print(f"❌ WebSocket Receive Error: {e}")
                    break

                # --- 1. HEARTBEAT FILTER (Hardened) ---
                # Catches 'ping', '{"type":"ping"}', etc. but ignores 'shipping', 'shopping'
                is_ping = False
                if not raw_data:
                    is_ping = True
                else:
                    import re
                    # Standalone "ping" word OR JSON type:ping
                    if re.search(r'\bping\b', raw_data, re.I) or re.search(r'"type"\s*:\s*"ping"', raw_data, re.I):
                        is_ping = True
                
                if is_ping:
                    await websocket.send_json({"type": "pong"})
                    continue

                # Robust Processing Wrapper
                try:
                    # A. Parse Payload
                    try:
                        payload = json.loads(raw_data)
                        
                        user_text = payload.get("text", "")
                        mode = payload.get("mode", "assistant")
                        session_id = payload.get("session_id")
                    except:
                        user_text = raw_data
                        mode = "operations"
                        session_id = f"sess_{client_context_id}"
                    
                    if not session_id:
                        session_id = f"sess_{client_context_id}"

                    # NEW: Ensure Session Exists in DB
                    session_res = await session.execute(select(ChatSession).where(ChatSession.session_id == session_id))
                    chat_session_obj = session_res.scalars().first()
                    if not chat_session_obj:
                        print(f"🆕 Creating new chat session: {session_id}")
                        new_sess = ChatSession(
                            client_id=client_id,
                            session_id=session_id,
                            title=user_text[:40] + ("..." if len(user_text) > 40 else "")
                        )
                        session.add(new_sess)
                        await session.commit()
                        log_audit(client_id, "CHAT_SESSION_CREATED", {"session_id": session_id})

                    print(f"📨 WEBSOCKET RECEIVED [{mode}][{session_id}]: {user_text}", flush=True)
                    
                    # B. Save user message
                    user_msg = ChatMessage(
                        role="user", 
                        content=user_text,
                        client_id=client_id,
                        session_id=session_id
                    )
                    session.add(user_msg)
                    await session.commit()
                    log_audit(client_id, "CHAT_MESSAGE_STORED", {"sender": "user", "session_id": session_id})

                    # C. Fetch Context (History & Memory) EARLY
                    from app.models.chat_memory import ChatMemory
                    from app.services.memory_service import trigger_compression_task
                    import asyncio
                    
                    # 1. Trigger Compression (Non-blocking)
                    asyncio.create_task(trigger_compression_task(session_id, int(client_id)))
                    
                    # 2. Get Memory Summary
                    mem_result = await session.execute(select(ChatMemory).where(ChatMemory.session_id == session_id))
                    memory = mem_result.scalars().first()
                    memory_summary = memory.summary if memory else ""

                    # 3. Fetch Recent History
                    hist_stmt = select(ChatMessage).where(
                        ChatMessage.client_id == client_id,
                        ChatMessage.session_id == session_id
                    ).order_by(ChatMessage.timestamp.desc()).limit(10)
                    hist_res = await session.execute(hist_stmt)
                    history_msgs = hist_res.scalars().all()
                    history_msgs.reverse()
                    formatted_history = [{"role": m.role, "content": m.content} for m in history_msgs]
                    log_audit(client_id, "CHAT_CONTEXT_BUILT", {"session_id": session_id, "history_size": len(formatted_history)})

                    # D. Rate Limit Check
                    if client and not limiter.check_chat(client.id):
                        await websocket.send_json({"text": "⚠️ Rate limit exceeded. Please wait."})
                        continue

                    # E. Route to Service
                    if mode == "operations":
                        log_audit(client_id, "CHAT_MODE_OPERATIONS", {"text": user_text, "session_id": session_id})
                        
                        # 1. FastPath
                        from app.services.fastpath_service import execute_fastpath
                        fast_text, fast_actions = await execute_fastpath(user_text, {"client_id": client_context_id, "session_id": session_id}, db_session=session)
                        
                        if fast_text:
                            ai_msg = ChatMessage(role="ai", content=fast_text, actions=fast_actions, client_id=client_id, session_id=session_id)
                            session.add(ai_msg)
                            await session.commit()
                            await websocket.send_json({"text": fast_text, "actions": fast_actions})
                            continue

                        # 2. CRUD Intent (CONTEXT AWARE)
                        from app.services.intent_service import resolve_crud_intent
                        from app.services.conversation_service import process_conversation, get_active_conversation
                        import json
                        
                        crud_intent = await resolve_crud_intent(user_text, int(client_id), session, history=formatted_history, mode=mode)
                        
                        # Handle Navigation Intent directly for speed
                        if crud_intent and crud_intent.get("intent") == "navigate" and crud_intent.get("url"):
                            dest_url = crud_intent["url"]
                            dest_name = crud_intent.get("label", "the requested page")
                            res_text = f"Taking you to **{dest_name}** now..."
                            res_actions = [{"type": "NAVIGATE", "payload": dest_url}]
                            ai_msg = ChatMessage(role="ai", content=res_text, actions=res_actions, client_id=client_id, session_id=session_id)
                            session.add(ai_msg)
                            await session.commit()
                            await websocket.send_json({"text": res_text, "actions": res_actions})
                            continue

                        # NEW: Handle Inquiry Intent (Questions like "where is sales?")
                        # We route these to Assistant mode fallback to avoid tool errors 
                        if crud_intent and crud_intent.get("intent") == "inquiry":
                            from app.services.assistant_service import get_assistant_response
                            print(f"❓ Inquiry detected in Operations Mode -> Assistant Fallback")
                            ai_text, ai_actions = await get_assistant_response(user_text, int(client_id), session, history=formatted_history, memory_summary=memory_summary)
                            ai_msg = ChatMessage(role="ai", content=ai_text, actions=ai_actions, client_id=client_id, session_id=session_id)
                            session.add(ai_msg)
                            await session.commit()
                            await websocket.send_json({"text": ai_text, "actions": ai_actions})
                            continue

                        # Active Conversation Check (Multi-turn CRUD)
                        active_crud_state = await get_active_conversation(session, int(client_id), session_id)
                        
                        if crud_intent or active_crud_state:
                            crud_text, crud_actions = await process_conversation(user_text, crud_intent, int(client_id), session_id, session)
                            if crud_text == "__SYSTEM_IGNORE__":
                                continue
                            if crud_text:
                                # De-duplicate actions
                                unique_actions = []
                                seen_actions = set()
                                for act in crud_actions:
                                    import json
                                    act_key = f"{act.get('type')}:{json.dumps(act.get('payload'))}"
                                    if act_key not in seen_actions:
                                        seen_actions.add(act_key)
                                        unique_actions.append(act)
                                
                                ai_msg = ChatMessage(role="ai", content=crud_text, actions=unique_actions, client_id=client_id, session_id=session_id)
                                session.add(ai_msg)
                                await session.commit()
                                await websocket.send_json({"text": crud_text, "actions": unique_actions})
                                continue

                        # 3. LLM Fallback (Operations)
                        print(f"🤖 Calling Operations LLM for: {user_text[:50]}...")
                        ai_text, actions = await get_response(user_text, history=formatted_history, session=session, client_id=int(client_id), memory_summary=memory_summary)
                        print(f"✅ Operations LLM Response received.")
                        ai_msg = ChatMessage(role="ai", content=ai_text, actions=actions, client_id=client_id, session_id=session_id)
                        session.add(ai_msg)
                        await session.commit()
                        await websocket.send_json({"text": ai_text, "actions": actions})

                    else:
                        # Mode: Assistant
                        log_audit(client_id, "CHAT_MODE_ASSISTANT", {"text": user_text, "session_id": session_id})
                        
                        # Guard against accidental CRUD in Assistant (CONTEXT AWARE)
                        from app.services.intent_service import resolve_crud_intent
                        crud_intent = await resolve_crud_intent(user_text, int(client_id), session, history=formatted_history[-4:], mode=mode) # Pass relevant history
                        
                        # Only block if it's an actual CRUD operation (create, update, delete, read)
                        # allow 'inquiry' and 'navigate' to pass through
                        if crud_intent and crud_intent.get("intent") not in ["inquiry", "navigate"]:
                            msg = f"I detected an intent to **{crud_intent.get('intent')}** a record. Please switch to **Operations Mode** to perform data actions."
                            await websocket.send_json({
                                "text": msg, 
                                "actions": [{"type": "SWITCH_MODE", "payload": "operations"}]
                            })
                            continue


                        from app.services.assistant_service import get_assistant_response
                        
                        print(f"🤖 Calling Assistant LLM for: {user_text[:50]}...")
                        # Pass only the relevant history for assistant mode (e.g., last 4)
                        res = await get_assistant_response(user_text, int(client_id), session, history=formatted_history[-4:], memory_summary=memory_summary)
                        
                        # Type Safety Unpacking
                        if isinstance(res, tuple) and len(res) == 2:
                            ai_text, ai_actions = res
                        else:
                            ai_text = str(res)
                            ai_actions = []

                        print(f"✅ Assistant LLM Response Type: {type(ai_text)}, Actions Type: {type(ai_actions)}")
                        
                        ai_msg = ChatMessage(
                            role="ai", 
                            content=str(ai_text),
                            actions=ai_actions,
                            client_id=client_id,
                            session_id=session_id
                        )
                        session.add(ai_msg)
                        await session.commit()
                        log_audit(client_id, "CHAT_MESSAGE_STORED", {"sender": "ai", "session_id": session_id})
                        await websocket.send_json({"text": ai_text, "actions": ai_actions})

                except Exception as e:
                    err_str = str(e) if str(e) else e.__class__.__name__
                    print(f"❌ CHAT PROCESSING ERROR: {err_str}\n{traceback.format_exc()}")
                    await websocket.send_json({"text": f"Sorry, I encountered an error: {err_str}", "actions": []})

        except WebSocketDisconnect:
            print("🔴 WebSocket Disconnected normally")
            break
        except Exception as e:
            print(f"❌ Socket Global Error: {e}\n{traceback.format_exc()}")
            break