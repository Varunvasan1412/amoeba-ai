# Amoeba AI v1 FIXED — Do not extend without version bump

import json
import asyncio
import decimal
from datetime import datetime, date

def sanitize_for_json(obj):
    """Recursively converts Decimals and Date objects to JSON-serializable formats."""
    if isinstance(obj, list):
        return [sanitize_for_json(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (decimal.Decimal)):
        return float(obj)
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return obj
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException, Depends, Query, Request
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
from app.core.config import settings
from app.core.rate_limiter import limiter

router = APIRouter()

# --- PUBLIC AI CONFIG (for chat widget indicator) ---
@router.get("/ai-config")
@limiter.limit(settings.RATE_LIMIT_HEALTH) # Low limit for config discovery
async def get_ai_config(
    request: Request,
    api_key: str = Query(None),
    session: AsyncSession = Depends(get_session)
):
    """Returns the AI provider & model configured for this client. Used by the chat widget."""
    from app.models.ai_settings import AISettings
    
    if api_key:
        result = await session.execute(select(ClientConfig).where(ClientConfig.api_key == api_key))
        client = result.scalars().first()
        if not client:
            raise HTTPException(status_code=403, detail="Invalid API Key")
    else:
        # Dev fallback
        result = await session.execute(select(ClientConfig).order_by(ClientConfig.id.asc()))
        client = result.scalars().first()
        if not client:
            raise HTTPException(status_code=403, detail="No client found")
    
    stmt = select(AISettings).where(AISettings.client_id == client.id)
    ai_settings = (await session.execute(stmt)).scalars().first()
    
    if ai_settings:
        return {"provider": ai_settings.provider, "model": ai_settings.model, "total_tokens_used": getattr(client, 'total_tokens_used', 0)}
    else:
        from app.core.config import settings
        return {"provider": settings.AI_PROVIDER, "model": settings.OLLAMA_MODEL, "total_tokens_used": getattr(client, 'total_tokens_used', 0)}

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
@limiter.limit(settings.RATE_LIMIT_CHAT)
async def chat_endpoint(payload: Dict[str, Any], request: Request):
    pass

# --- HISTORY ENDPOINT ---
@router.get("/history", response_model=List[ChatMessage])
@limiter.limit(settings.RATE_LIMIT_CHAT)
async def get_history(
    request: Request,
    api_key: str = Query(None),
    session_id: str = Query(...),
    session: AsyncSession = Depends(get_session)
):
    try:
        if api_key:
            result = await session.execute(select(ClientConfig).where(ClientConfig.api_key == api_key))
            client = result.scalars().first()
            if not client:
                raise HTTPException(status_code=403, detail="Invalid API Key")
        else:
            # Dev fallback
            result = await session.execute(select(ClientConfig).order_by(ClientConfig.id.asc()))
            client = result.scalars().first()
            if not client:
                raise HTTPException(status_code=403, detail="No client found")

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
    
    # Initialize variables for cleanup/error handling
    active_tasks: Dict[str, asyncio.Task] = {}
    client_id = 0
    client_context_id = "default"

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
                result = await session.execute(select(ClientConfig).order_by(ClientConfig.id.asc()))
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
            from app.core.database import async_session as SessionLocal
            
            while True:
                try:
                    raw_data = await websocket.receive_text()
                except WebSocketDisconnect:
                    print("🔴 WebSocket Disconnected by Client")
                    break
                except Exception as e:
                    print(f"❌ WebSocket Receive Error: {e}")
                    break

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

                # 3. Process Payload
                try:
                    payload = json.loads(raw_data)
                    msg_type = payload.get("type", "chat")
                    session_id = payload.get("session_id")
                    
                    if not session_id:
                        session_id = f"sess_{client_context_id}"

                    # CANCELLATION LOGIC
                    if msg_type == "STOP":
                        if session_id in active_tasks:
                            print(f"🛑 [WS] Received STOP for Session {session_id}. Cancelling Task.")
                            active_tasks[session_id].cancel()
                            await websocket.send_json({"type": "done", "session_id": session_id})
                        continue

                    # Cancel any existing task for this session to prevent race conditions/double replies
                    if session_id in active_tasks:
                        print(f"🔄 [WS] New message for {session_id} while thinking. Cancelling stale task.")
                        active_tasks[session_id].cancel()

                    # Define the processing logic as a coroutine to be run as a task
                    async def process_and_send(data_str: str, s_id: str):
                        # Create a LOCAL session for this specific task
                        async with SessionLocal() as local_session:
                            try:
                                # Inner processing logic...
                                p = json.loads(data_str)
                                user_text = p.get("text", "")
                                mode = p.get("mode", "assistant")
                                view_mode = p.get("view_mode", "table")
                                is_edit = p.get("is_edit", False)
                                # history_context: list of {role, content} to restore on edit
                                history_context = p.get("history_context", [])
                                # Extract settings
                                DEFAULT_SOURCES = {
                                    "erp": True,
                                    "documents": True,
                                    "web": False
                                }
                                sources = p.get("sources", DEFAULT_SOURCES)
                                model_override = p.get("model")
                                print(f"\nACTIVE SOURCES:\nerp={sources.get('erp')}\ndocuments={sources.get('documents')}\nweb={sources.get('web')}\nMODEL_OVERRIDE={model_override}\n")

                                # Ensure Session Exists in DB (Using local_session)
                                session_res = await local_session.execute(select(ChatSession).where(ChatSession.session_id == s_id))
                                chat_session_obj = session_res.scalars().first()
                                if not chat_session_obj:
                                    print(f"🆕 Creating new chat session: {s_id}")
                                    new_sess = ChatSession(
                                        client_id=client_id,
                                        session_id=s_id,
                                        title=user_text[:40] + ("..." if len(user_text) > 40 else "")
                                    )
                                    local_session.add(new_sess)
                                    await local_session.commit()
                                    log_audit(client_id, "CHAT_SESSION_CREATED", {"session_id": s_id})

                                print(f"📨 WEBSOCKET RECEIVED [{mode}][{s_id}]: {user_text}", flush=True)
                                
                                # A. DB Wipe & Restore on edit: 100% reliable context synchronization
                                if is_edit:
                                    try:
                                        print(f"✂️ [WS] Edit mode: Wiping and restoring history for {s_id}")
                                        from sqlalchemy import delete as sa_delete
                                        await local_session.execute(sa_delete(ChatMessage).where(ChatMessage.session_id == s_id))
                                        
                                        # Restore previous messages (context)
                                        for msg_data in history_context:
                                            restored_msg = ChatMessage(
                                                role=msg_data.get("role", "user"),
                                                content=msg_data.get("content", ""),
                                                client_id=client_id,
                                                session_id=s_id,
                                                is_edited=False 
                                            )
                                            local_session.add(restored_msg)
                                        await local_session.commit()
                                    except Exception as te:
                                        print(f"⚠️ Edit DB sync error: {te}")

                                # B. Save user message
                                user_msg = ChatMessage(
                                    role="user", 
                                    content=user_text,
                                    client_id=client_id,
                                    session_id=s_id,
                                    is_edited=is_edit
                                )
                                local_session.add(user_msg)
                                await local_session.commit()
                                # Suppression: log_audit(client_id, "CHAT_MESSAGE_STORED", ...)

                                # C. Fetch Context (History & Memory) EARLY
                                from app.models.chat_memory import ChatMemory
                                from app.services.memory_service import trigger_compression_task
                                
                                # 1. Trigger Compression (Non-blocking)
                                asyncio.create_task(trigger_compression_task(s_id, int(client_id)))
                                
                                # 2. Get Memory Summary
                                mem_result = await local_session.execute(select(ChatMemory).where(ChatMemory.session_id == s_id))
                                memory = mem_result.scalars().first()
                                memory_summary = memory.summary if memory else ""

                                # 3. Fetch Recent History (now guaranteed to be clean)
                                hist_stmt = select(ChatMessage).where(
                                    ChatMessage.client_id == client_id,
                                    ChatMessage.session_id == s_id
                                ).order_by(ChatMessage.timestamp.desc()).limit(20)
                                hist_res = await local_session.execute(hist_stmt)
                                history_msgs = hist_res.scalars().all()
                                history_msgs.reverse()
                                
                                # Exclude the current (just-saved) user message from the context passed to the AI
                                formatted_history = [{"role": m.role, "content": m.content} for m in history_msgs[:-1]]
                                # Suppression: log_audit(client_id, "CHAT_CONTEXT_BUILT", ...)

                                # D. Rate Limit Check
                                if client and not limiter.check_chat(client.id):
                                    await websocket.send_json({"text": "⚠️ Rate limit exceeded. Please wait.", "type": "chat_response"})
                                    return

                                # E. Route to Service
                                # 1. FastPath Navigation (GLOBAL FOR ALL MODES)
                                from app.services.fastpath_service import execute_fastpath
                                fast_text, fast_actions = await execute_fastpath(user_text, {"client_id": client_context_id, "session_id": s_id}, db_session=local_session)
                                
                                if fast_text:
                                    ai_msg = ChatMessage(role="ai", content=fast_text, actions=fast_actions, client_id=client_id, session_id=s_id)
                                    local_session.add(ai_msg)
                                    await local_session.commit()
                                    await websocket.send_json({"text": fast_text, "actions": fast_actions, "type": "chat_response"})
                                    await websocket.send_json({"type": "done", "session_id": s_id})
                                    return

                                if mode == "operations":
                                    # Suppression: log_audit(client_id, "CHAT_MODE_OPERATIONS", ...)
                                    
                                    # 2. CRUD Intent (CONTEXT AWARE)
                                    from app.services.intent_service import resolve_crud_intent
                                    from app.services.conversation_service import process_conversation, get_active_conversation
                                    
                                    crud_intent = await resolve_crud_intent(user_text, int(client_id), local_session, history=formatted_history, mode=mode)
                                    
                                    # Handle Navigation Intent directly for speed
                                    if crud_intent and crud_intent.get("intent") == "navigate" and crud_intent.get("url"):
                                        dest_url = crud_intent["url"]
                                        dest_name = crud_intent.get("label", "the requested page")
                                        res_text = f"Taking you to **{dest_name}** now..."
                                        res_actions = [{"type": "NAVIGATE", "payload": dest_url}]
                                        ai_msg = ChatMessage(role="ai", content=res_text, actions=res_actions, client_id=client_id, session_id=s_id)
                                        local_session.add(ai_msg)
                                        await local_session.commit()
                                        await websocket.send_json({"text": res_text, "actions": res_actions, "type": "chat_response"})
                                        await websocket.send_json({"type": "done", "session_id": s_id})
                                        return

                                    if crud_intent and crud_intent.get("intent") == "inquiry":
                                        from app.services.assistant_service import get_assistant_response
                                        print(f"❓ Inquiry detected in Operations Mode -> Assistant Fallback")
                                        ai_text, ai_actions = await get_assistant_response(user_text, int(client_id), local_session, history=formatted_history, memory_summary=memory_summary, sources=sources, model=model_override)
                                        ai_msg = ChatMessage(role="ai", content=ai_text, actions=ai_actions, client_id=client_id, session_id=s_id)
                                        local_session.add(ai_msg)
                                        await local_session.commit()
                                        await websocket.send_json({"text": ai_text, "actions": ai_actions, "type": "chat_response"})
                                        await websocket.send_json({"type": "done", "session_id": s_id})
                                        return

                                    # Active Conversation Check (Multi-turn CRUD)
                                    active_crud_state = await get_active_conversation(local_session, int(client_id), s_id)
                                    
                                    if crud_intent or active_crud_state:
                                        crud_text, crud_actions = await process_conversation(user_text, crud_intent, int(client_id), s_id, local_session, view_mode=view_mode)
                                        if crud_text == "__SYSTEM_IGNORE__":
                                            await websocket.send_json({"type": "done", "session_id": s_id})
                                            return
                                            
                                        if crud_text and crud_text.startswith("__DELEGATE_READ__"):
                                            # ===== DETERMINISTIC READ: BYPASS LLM ENTIRELY =====
                                            parts = crud_text.split(":")
                                            table_name = parts[1] if len(parts) > 1 else ""
                                            friendly_name = parts[2] if len(parts) > 2 else table_name
                                            
                                            print(f"🔧 [DETERMINISTIC READ] Bypassing LLM for table: {table_name}")
                                            
                                            try:
                                                from app.services.crud_service import CRUDService
                                                from app.tools.dates import normalize_date_range
                                                
                                                # Step 1: Parse aggregation intent from user query
                                                query_lower = user_text.lower()
                                                is_aggregation = any(kw in query_lower for kw in [
                                                    "how many", "count", "total", "number of", "sum of", "average"
                                                ])
                                                
                                                filters = {}
                                                if is_aggregation:
                                                    if any(kw in query_lower for kw in ["sum of", "total amount", "total value"]):
                                                        filters["aggregate"] = "sum"
                                                    elif "average" in query_lower:
                                                        filters["aggregate"] = "avg"
                                                    else:
                                                        filters["aggregate"] = "count"
                                                
                                                # Step 2: Execute the CRUD read (date filtering is handled internally by CRUDService)
                                                result = await CRUDService.read_records(
                                                    table_name=table_name,
                                                    filters=filters if filters else None,
                                                    limit=100,
                                                    client_id=int(client_id),
                                                    user_query=user_text
                                                )
                                                
                                                # Sanitize for JSON (Convert Decimals to floats!)
                                                result = sanitize_for_json(result)
                                                
                                                # Step 3: Parse date range for transparency in the response
                                                date_start, date_end = normalize_date_range(user_text)
                                                date_info = ""
                                                if date_start:
                                                    date_info = f"\n📅 Date range analyzed: **{date_start}** to **{date_end}**"
                                                
                                                # Step 4: Format the response
                                                actions_list = []
                                                if isinstance(result, dict) and "aggregate" in result:
                                                    # Aggregation result
                                                    agg_type = result["aggregate"]
                                                    value = result["value"]
                                                    response_text = f"**{friendly_name}** — {agg_type.upper()}: **{value}**{date_info}"
                                                elif isinstance(result, dict) and "grouped_results" in result:
                                                    # Grouped aggregation
                                                    response_text = f"**{friendly_name}** — Grouped Results:{date_info}"
                                                    actions_list.append({"type": "DISPLAY_TABLE", "payload": {"title": friendly_name, "data": result["grouped_results"]}})
                                                elif isinstance(result, dict) and "records" in result:
                                                    # Records with warnings
                                                    records = result["records"]
                                                    if records:
                                                        response_text = f"Found **{len(records)}** record(s) in **{friendly_name}**.{date_info}"
                                                        headers = list(records[0].keys()) if records else []
                                                        actions_list.append({
                                                            "type": "data_table", 
                                                            "payload": {
                                                                "title": friendly_name, 
                                                                "headers": headers,
                                                                "rows": records,
                                                                "total": len(records),
                                                                "query_payload": {
                                                                    "table_name": table_name,
                                                                    "filters": filters if filters else None,
                                                                    "user_query": user_text,
                                                                    "client_id": int(client_id)
                                                                }
                                                            }
                                                        })
                                                    else:
                                                        response_text = f"No records found in **{friendly_name}** for the specified criteria.{date_info}"
                                                elif isinstance(result, list):
                                                    if result:
                                                        response_text = f"Found **{len(result)}** record(s) in **{friendly_name}**.{date_info}"
                                                        headers = list(result[0].keys()) if result else []
                                                        actions_list.append({
                                                            "type": "data_table", 
                                                            "payload": {
                                                                "title": friendly_name, 
                                                                "headers": headers,
                                                                "rows": result,
                                                                "total": len(result),
                                                                "query_payload": {
                                                                    "table_name": table_name,
                                                                    "filters": filters if filters else None,
                                                                    "user_query": user_text,
                                                                    "client_id": int(client_id)
                                                                }
                                                            }
                                                        })
                                                    else:
                                                        response_text = f"No records found in **{friendly_name}** for the specified criteria.{date_info}"
                                                else:
                                                    response_text = f"Result from **{friendly_name}**: {result}{date_info}"
                                                
                                                print(f"✅ [DETERMINISTIC READ] Result: {response_text[:100]}...")
                                                
                                                ai_msg = ChatMessage(role="ai", content=response_text, actions=actions_list, client_id=client_id, session_id=s_id)
                                                local_session.add(ai_msg)
                                                await local_session.commit()
                                                await websocket.send_json({"text": response_text, "actions": actions_list, "type": "chat_response"})
                                                await websocket.send_json({"type": "done", "session_id": s_id})
                                                return
                                                
                                            except Exception as read_err:
                                                print(f"❌ [DETERMINISTIC READ] Error: {read_err}")
                                                error_text = f"Sorry, I encountered an error reading from {friendly_name}: {str(read_err)}"
                                                ai_msg = ChatMessage(role="ai", content=error_text, actions=[], client_id=client_id, session_id=s_id)
                                                local_session.add(ai_msg)
                                                await local_session.commit()
                                                await websocket.send_json({"text": error_text, "actions": [], "type": "chat_response"})
                                                await websocket.send_json({"type": "done", "session_id": s_id})
                                                return

                                        elif crud_text:
                                            # De-duplicate actions
                                            unique_actions = []
                                            seen_actions = set()
                                            for act in crud_actions:
                                                act_key = f"{act.get('type')}:{json.dumps(act.get('payload'))}"
                                                if act_key not in seen_actions:
                                                    seen_actions.add(act_key)
                                                    unique_actions.append(act)
                                            
                                            ai_msg = ChatMessage(role="ai", content=crud_text, actions=unique_actions, client_id=client_id, session_id=s_id)
                                            local_session.add(ai_msg)
                                            await local_session.commit()
                                            await websocket.send_json({"text": crud_text, "actions": unique_actions, "type": "chat_response"})
                                            await websocket.send_json({"type": "done", "session_id": s_id})
                                            return

                                    # 3. LLM Fallback (Operations)
                                    print(f"🤖 Calling Operations LLM for: {user_text[:50]}...")
                                    ai_text, actions = await get_response(user_text, history=formatted_history, session=local_session, client_id=int(client_id), memory_summary=memory_summary, model_override=model_override)
                                    print(f"✅ Operations LLM Response received.")
                                    ai_msg = ChatMessage(role="ai", content=ai_text, actions=actions, client_id=client_id, session_id=s_id)
                                    local_session.add(ai_msg)
                                    await local_session.commit()
                                    await websocket.send_json({"text": ai_text, "actions": actions, "type": "chat_response"})
                                    await websocket.send_json({"type": "done", "session_id": s_id})

                                else:
                                    # Mode: Assistant
                                    # Suppression: log_audit(client_id, "CHAT_MODE_ASSISTANT", ...)
                                    
                                    # Guard against accidental CRUD in Assistant (CONTEXT AWARE)
                                    from app.services.intent_service import resolve_crud_intent
                                    crud_intent = await resolve_crud_intent(user_text, int(client_id), local_session, history=formatted_history[-4:], mode=mode) 
                                    
                                    if crud_intent and crud_intent.get("intent") not in ["inquiry", "navigate"]:
                                        # If it's a READ intent, handle it deterministically instead of redirecting
                                        if crud_intent.get("intent") == "read" and crud_intent.get("entity"):
                                            print(f"🔧 [ASSISTANT] Intercepting READ intent for: {crud_intent.get('entity')}")
                                            from app.services.conversation_service import process_conversation, get_active_conversation
                                            crud_text, crud_actions = await process_conversation(user_text, crud_intent, int(client_id), s_id, local_session)
                                            
                                            if crud_text and crud_text.startswith("__DELEGATE_READ__"):
                                                parts = crud_text.split(":")
                                                table_name = parts[1] if len(parts) > 1 else ""
                                                friendly_name = parts[2] if len(parts) > 2 else table_name
                                                
                                                try:
                                                    from app.services.crud_service import CRUDService
                                                    from app.tools.dates import normalize_date_range
                                                    
                                                    query_lower = user_text.lower()
                                                    is_aggregation = any(kw in query_lower for kw in ["how many", "count", "total", "number of", "sum of", "average"])
                                                    
                                                    filters = {}
                                                    if is_aggregation:
                                                        if any(kw in query_lower for kw in ["sum of", "total amount", "total value"]):
                                                            filters["aggregate"] = "sum"
                                                        elif "average" in query_lower:
                                                            filters["aggregate"] = "avg"
                                                        else:
                                                            filters["aggregate"] = "count"
                                                    
                                                    result = await CRUDService.read_records(
                                                        table_name=table_name, filters=filters if filters else None,
                                                        limit=100, client_id=int(client_id), user_query=user_text
                                                    )
                                                    
                                                    # Sanitize for JSON
                                                    result = sanitize_for_json(result)
                                                    
                                                    date_start, date_end = normalize_date_range(user_text)
                                                    date_info = f"\n📅 Date range analyzed: **{date_start}** to **{date_end}**" if date_start else ""
                                                    
                                                    actions_list = []
                                                    if isinstance(result, dict) and "aggregate" in result:
                                                        response_text = f"**{friendly_name}** — {result['aggregate'].upper()}: **{result['value']}**{date_info}"
                                                    elif isinstance(result, dict) and "records" in result:
                                                        records = result["records"]
                                                        if records:
                                                            response_text = f"Found **{len(records)}** record(s) in **{friendly_name}**.{date_info}"
                                                            headers = list(records[0].keys()) if records else []
                                                            actions_list.append({
                                                                "type": "data_table", 
                                                                "payload": {
                                                                    "title": friendly_name, 
                                                                    "headers": headers,
                                                                    "rows": records,
                                                                    "total": len(records)
                                                                }
                                                            })
                                                        else:
                                                            response_text = f"No records found in **{friendly_name}** for the specified criteria.{date_info}"
                                                    elif isinstance(result, list):
                                                        if result:
                                                            response_text = f"Found **{len(result)}** record(s) in **{friendly_name}**.{date_info}"
                                                            headers = list(result[0].keys()) if result else []
                                                            actions_list.append({
                                                                "type": "data_table", 
                                                                "payload": {
                                                                    "title": friendly_name, 
                                                                    "headers": headers,
                                                                    "rows": result,
                                                                    "total": len(result)
                                                                }
                                                            })
                                                        else:
                                                            response_text = f"No records found in **{friendly_name}** for the specified criteria.{date_info}"
                                                    else:
                                                        response_text = f"Result from **{friendly_name}**: {result}{date_info}"
                                                    
                                                    ai_msg = ChatMessage(role="ai", content=response_text, actions=actions_list, client_id=client_id, session_id=s_id)
                                                    local_session.add(ai_msg)
                                                    await local_session.commit()
                                                    await websocket.send_json({"text": response_text, "actions": actions_list, "type": "chat_response"})
                                                    await websocket.send_json({"type": "done", "session_id": s_id})
                                                    return
                                                except Exception as read_err:
                                                    print(f"❌ [ASSISTANT READ] Error: {read_err}")
                                        
                                        # For non-read CRUD intents, redirect to Operations
                                        if crud_intent.get("intent") != "read":
                                            msg = f"I detected an intent to **{crud_intent.get('intent')}** a record. Please switch to **Operations Mode** to perform data actions."
                                            await websocket.send_json({
                                                "text": msg, 
                                                "actions": [{"type": "SWITCH_MODE", "payload": "operations"}],
                                                "type": "chat_response"
                                            })
                                            await websocket.send_json({"type": "done", "session_id": s_id})
                                            return


                                    from app.services.assistant_service import get_assistant_response
                                    
                                    print(f"🤖 Calling Assistant LLM for: {user_text[:50]}...")
                                    res = await get_assistant_response(user_text, int(client_id), local_session, history=formatted_history[-4:], memory_summary=memory_summary, sources=sources, model=model_override)
                                    
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
                                        session_id=s_id
                                    )
                                    local_session.add(ai_msg)
                                    await local_session.commit()
                                    # Suppression: log_audit(client_id, "CHAT_MESSAGE_STORED", ...)
                                    await websocket.send_json({"text": ai_text, "actions": ai_actions, "type": "chat_response"})
                                    # Send explicit DONE signal
                                    await websocket.send_json({"type": "done", "session_id": s_id})

                            except asyncio.CancelledError:
                                print(f'ℹ️ [WS] Task for {s_id} was successfully cancelled.')
                            except Exception as e:
                                # CRITICAL: Rollback on ANY processing error to clear failed transaction state
                                try:
                                    await local_session.rollback()
                                    print(f"🔄 [WS] Transaction rolled back for session {s_id}")
                                except:
                                    pass
    
                                raw_err = str(e)
                                err_str = raw_err if raw_err else e.__class__.__name__
                                
                                # User-friendly error for Rate Limits
                                if "RESOURCE_EXHAUSTED" in err_str:
                                    err_str = "AI Rate limit reached (Gemini). Please wait 30-60 seconds before trying again."
                                
                                print(f"❌ [WS] Processing Task Error: {err_str}")
                                await websocket.send_json({"text": f"Sorry, I encountered an error: {err_str}", "type": "error", "session_id": s_id})
                                await websocket.send_json({"type": "done", "session_id": s_id}) # Still send done for UI to unblock
                            finally:
                                if active_tasks.get(s_id) == asyncio.current_task():
                                    del active_tasks[s_id]
    
                    # Start Task
                    task = asyncio.create_task(process_and_send(raw_data, session_id))
                    active_tasks[session_id] = task

                except Exception as e:
                    err_str = str(e) if str(e) else e.__class__.__name__
                    print(f"❌ WebSocket Loop Error: {err_str}\n{traceback.format_exc()}")
                    await websocket.send_json({"text": f"Internal Error: {err_str}", "type": "error"})

        except WebSocketDisconnect:
            print("🔴 WebSocket Disconnected normally")
            # Cancel all active tasks for this client when the websocket disconnects
            for task_id, task in active_tasks.items():
                if not task.done():
                    print(f"🛑 [WS] Client disconnected. Cancelling task for session {task_id}.")
                    task.cancel()
            break
        except Exception as e:
            print(f"❌ Socket Global Error: {e}\n{traceback.format_exc()}")
            # Cancel all active tasks for this client on global error
            for task_id, task in active_tasks.items():
                if not task.done():
                    print(f"🛑 [WS] Global error. Cancelling task for session {task_id}.")
                    task.cancel()
            break

# --- INLINE EXPORT API ---
from pydantic import BaseModel
from fastapi import HTTPException, Query
from app.tools.reporting import export_query_result
import time
from app.models.client_config import ClientConfig

class InlineExportRequest(BaseModel):
    format: str
    query_payload: dict

@router.post("/inline-export")
@limiter.limit(settings.RATE_LIMIT_EXPORT)
async def inline_export(
    payload: InlineExportRequest,
    request: Request,
    api_key: str = Query(...),
    session: AsyncSession = Depends(get_session)
):
    """
    Directly exports data derived from a previous generic chat table representation.
    """
    start_time = time.time()
    
    # 1. Validate API Key and Set Client Context
    result = await session.execute(select(ClientConfig).where(ClientConfig.api_key == api_key))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=403, detail="Invalid API Key")
        
    # Standardize DB URL with fallback
    db_url = client.db_connection_url or settings.DATABASE_URL
    current_db_url.set(db_url)
    client_id = client.id
    client_context_id = str(client.id)
    
    # Validation
    table_name = payload.query_payload.get("table_name", "unknown")
        
    try:
        # Call the synchronous reporting tool export with fallback url
        filepath = export_query_result(payload.query_payload, payload.format, db_url=db_url)
        
        if filepath.startswith("Error") or filepath.startswith("No data"):
             raise HTTPException(status_code=400, detail=filepath)
        
        import os
        if not os.path.exists(filepath):
             raise HTTPException(status_code=500, detail="Export file was not created.")
             
        exec_time = int((time.time() - start_time) * 1000)
        
        log_audit(client_id, "EXPORT_EXECUTED", {
            "table_name": table_name,
            "format": payload.format,
            "execution_time_ms": exec_time
        })
        
        # Return the file directly as a download response
        from fastapi.responses import FileResponse
        basename = os.path.basename(filepath)
        media_types = {"csv": "text/csv", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "pdf": "application/pdf"}
        mt = media_types.get(payload.format.lower(), "application/octet-stream")
        return FileResponse(filepath, filename=basename, media_type=mt)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")