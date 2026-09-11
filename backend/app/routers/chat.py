# Amoeba AI v1 FIXED — Do not extend without version bump

import json
import asyncio
import decimal
from datetime import datetime, date

def sanitize_for_json(obj):
    """Recursively converts Decimals and Date objects to JSON-serializable formats."""
    if isinstance(obj, (list, tuple)):
        return [sanitize_for_json(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (decimal.Decimal)):
        return float(obj)
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return obj
from langchain_core.messages import HumanMessage, SystemMessage
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException, Depends, Query, Request
import traceback
from app.services.llm_service import get_response
from app.core.context import current_db_url
from app.tools.navigation import batch_learn_routes
from typing import List, Dict, Any, Optional
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

class SemanticItem(BaseModel):
    ui_label: str
    database_table: str
    source_file: str
    ui_columns: Optional[str] = None
    default_filter: Optional[str] = None
    base_query: Optional[str] = None
    required_joins: Optional[str] = None
    tab_group: Optional[str] = None

@router.post("/semantic/sync")
async def sync_semantic_endpoint(
    semantics: List[SemanticItem], 
    api_key: str = Query(...),
    session: AsyncSession = Depends(get_session)
):
    """Saves discovered semantic mappings from the codebase profiler.
    Uses smart upsert: validates table names against real DB, fuzzy-matches
    non-existent tables, and never overwrites source-code mappings with web-crawl guesses.
    """
    from app.models.semantic_mapping import SemanticMapping
    from app.services.onboarding import discover_tables
    
    # 1. Verify Client
    result = await session.execute(select(ClientConfig).where(ClientConfig.api_key == api_key))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=403, detail="Invalid API Key")

    # 2. Discover real DB tables for validation
    real_tables = []
    try:
        if client.db_connection_url:
            tables_raw = discover_tables(client.db_connection_url)
            real_tables = [t["name"].lower() for t in tables_raw]
    except Exception as e:
        print(f"⚠️ [SEMANTIC SYNC] Could not discover tables for validation: {e}")
    
    def fuzzy_match_table(guessed_table, real_tables_list):
        """Try to match a guessed table name to a real one."""
        if not real_tables_list:
            return guessed_table
        gt = guessed_table.lower().strip()
        # 1. Exact match
        if gt in real_tables_list:
            return gt
        # 2. Suffix matches
        for suffix in ['_head', '_header', '_master', '_mst', '_detail', '_details', '_items', '_det', '_tran', '_ms', '_log', '_history']:
            if f"{gt}{suffix}" in real_tables_list:
                return f"{gt}{suffix}"
        # 3. Contains match (prefer shortest containing match)
        containing = [t for t in real_tables_list if gt in t]
        if containing:
            containing.sort(key=len)
            return containing[0]
        # 4. Reverse contains (table name contained in guessed name)
        for t in real_tables_list:
            t_base = t.replace('_head', '').replace('_header', '').replace('_master', '').replace('_mst', '').replace('_detail', '')
            if t_base and len(t_base) >= 3 and t_base in gt:
                return t
        return guessed_table  # Return as-is if no match found

    # 3. Smart Upsert: Update existing, add new, validate tables
    added = 0
    updated = 0
    skipped = 0
    try:
        for s in semantics:
            # Validate and fix table name
            validated_table = s.database_table
            if real_tables and s.database_table.lower() not in real_tables:
                corrected = fuzzy_match_table(s.database_table, real_tables)
                if corrected != s.database_table.lower():
                    print(f"🔧 [SEMANTIC SYNC] Table correction: '{s.database_table}' -> '{corrected}'")
                    validated_table = corrected
                else:
                    print(f"⚠️ [SEMANTIC SYNC] Table '{s.database_table}' not found in DB, keeping as-is for label '{s.ui_label}'")
            
            is_web_crawl = s.source_file and s.source_file.startswith("HTTP")
            
            # Check if mapping already exists
            existing_stmt = select(SemanticMapping).where(
                SemanticMapping.client_id == client.id,
                SemanticMapping.ui_label == s.ui_label
            )
            existing_res = await session.execute(existing_stmt)
            existing = existing_res.scalars().first()
            
            if existing:
                # Never overwrite source-code-based mapping with a web-crawl guess
                existing_is_source_code = existing.source_file and not existing.source_file.startswith("HTTP")
                if is_web_crawl and existing_is_source_code:
                    skipped += 1
                    continue
                
                # Update existing mapping
                existing.database_table = validated_table
                existing.source_file = s.source_file
                existing.ui_columns = s.ui_columns
                existing.default_filter = s.default_filter
                existing.base_query = s.base_query
                existing.required_joins = s.required_joins
                existing.tab_group = s.tab_group
                session.add(existing)
                updated += 1
            else:
                new_map = SemanticMapping(
                    client_id=client.id,
                    ui_label=s.ui_label,
                    database_table=validated_table,
                    source_file=s.source_file,
                    ui_columns=s.ui_columns,
                    default_filter=s.default_filter,
                    base_query=s.base_query,
                    required_joins=s.required_joins,
                    tab_group=s.tab_group
                )
                session.add(new_map)
                added += 1
            
        await session.commit()
        msg = f"Synced semantic mappings: {added} added, {updated} updated, {skipped} skipped (protected)"
        print(f"✅ [SEMANTIC SYNC] {msg}")
        return {"status": "success", "message": msg, "added": added, "updated": updated, "skipped": skipped}
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Database error during sync: {str(e)}")

@router.get("/semantic/debug")
async def debug_semantic_endpoint(
    api_key: str = Query(...),
    search: str = Query("invoice"),
    session: AsyncSession = Depends(get_session)
):
    """Temporary diagnostic endpoint to inspect semantic mappings."""
    from app.models.semantic_mapping import SemanticMapping
    result = await session.execute(select(ClientConfig).where(ClientConfig.api_key == api_key))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    
    sm_stmt = select(SemanticMapping).where(SemanticMapping.client_id == client.id)
    sm_res = await session.execute(sm_stmt)
    sm_all = sm_res.scalars().all()
    
    search_lower = search.lower()
    matches = []
    for sm in sm_all:
        if search_lower in (sm.ui_label or "").lower() or search_lower in (sm.tab_group or "").lower():
            matches.append({
                "id": sm.id,
                "ui_label": sm.ui_label,
                "tab_group": sm.tab_group,
                "database_table": sm.database_table,
                "default_filter": sm.default_filter,
                "source_file": sm.source_file[:80] if sm.source_file else None,
            })
    
    # Group by tab_group
    groups = {}
    for m in matches:
        g = m["tab_group"] or "NULL"
        groups.setdefault(g, []).append(m["ui_label"])
    
    return {
        "client_id": client.id,
        "search": search,
        "total_mappings": len(sm_all),
        "matching_count": len(matches),
        "by_tab_group": groups,
        "matches": matches[:30]
    }

@router.post("/enums/learn")
async def learn_enums_endpoint(
    enums: Dict[str, Dict[str, Dict[str, str]]], # table_name -> column_name -> mapping (e.g. {"unit": {"status": {"1": "Active"}}})
    api_key: str = Query(...),
    session: AsyncSession = Depends(get_session)
):
    """Saves enum mappings to SemanticMetadata for a specific client."""
    from app.models.semantic_metadata import SemanticMetadata
    
    # 1. Verify Client
    result = await session.execute(select(ClientConfig).where(ClientConfig.api_key == api_key))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=403, detail="Invalid API Key")

    updated = 0
    try:
        # Fetch existing semantic metadata for this client
        stmt = select(SemanticMetadata).where(SemanticMetadata.client_id == client.id)
        res = await session.execute(stmt)
        existing_meta = res.scalars().all()
        
        # Create a lookup for quick access
        meta_lookup = {(m.table_name, m.column_name): m for m in existing_meta}
        
        for table_name, columns in enums.items():
            for column_name, mapping in columns.items():
                key = (table_name, column_name)
                if key in meta_lookup:
                    # Update existing
                    meta = meta_lookup[key]
                    meta.enum_mappings = mapping
                    session.add(meta)
                    updated += 1
                else:
                    # Create new semantic metadata entry just for this enum
                    new_meta = SemanticMetadata(
                        client_id=client.id,
                        table_name=table_name,
                        column_name=column_name,
                        label=column_name.replace("_", " ").title(),
                        enum_mappings=mapping
                    )
                    session.add(new_meta)
                    updated += 1
                    
        await session.commit()
        return {"status": "success", "message": f"Synced {updated} enum mappings"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Database error during enum sync: {str(e)}")

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
                                # 0.9 Multi-Turn Disambiguation Choice Resolution (Tab & Report choices)
                                from app.services.conversation_service import get_active_conversation
                                from app.models.conversation_state import ConversationState
                                active_choice_state = await get_active_conversation(local_session, int(client_id), s_id)
                                
                                if active_choice_state and active_choice_state.current_step == "resolve_tab_choice":
                                    saved_tabs = active_choice_state.collected_data.get("tabs", []) if active_choice_state.collected_data else []
                                    user_trimmed = user_text.strip()
                                    chosen_tab = None
                                    if user_trimmed.isdigit():
                                        idx = int(user_trimmed) - 1
                                        if 0 <= idx < len(saved_tabs):
                                            chosen_tab = saved_tabs[idx]
                                    else:
                                        for t in saved_tabs:
                                            if t.lower() in user_trimmed.lower() or user_trimmed.lower() in t.lower():
                                                chosen_tab = t
                                                break
                                    
                                    if chosen_tab:
                                        await local_session.delete(active_choice_state)
                                        await local_session.commit()
                                        c_data = active_choice_state.collected_data or {}
                                        orig_q = c_data.get("original_query", "").lower()
                                        has_nav_verb = any(w in orig_q for w in ["navigate", "go to", "open", "take me"])
                                        if has_nav_verb:
                                            user_text = f"navigate to {chosen_tab.lower()}"
                                        else:
                                            user_text = f"view {chosen_tab.lower()} table"
                                    elif user_trimmed.lower() in ["cancel", "stop", "exit", "quit", "nevermind"]:
                                        await local_session.delete(active_choice_state)
                                        await local_session.commit()
                                        cancel_msg = "Tab selection cancelled."
                                        ai_msg = ChatMessage(role="ai", content=cancel_msg, actions=[], client_id=client_id, session_id=s_id)
                                        local_session.add(ai_msg)
                                        await local_session.commit()
                                        await websocket.send_json({"text": cancel_msg, "actions": [], "type": "chat_response"})
                                        await websocket.send_json({"type": "done", "session_id": s_id})
                                        return

                                if active_choice_state and active_choice_state.intent == "report_disambiguation" and active_choice_state.current_step == "resolve_report_choice":
                                    c_data = active_choice_state.collected_data or {}
                                    saved_opts = c_data.get("options", [])
                                    rep_entity = c_data.get("entity", "Total Sales Report")
                                    rep_url = c_data.get("url")
                                    rep_table = c_data.get("table")
                                    user_trimmed = user_text.strip()
                                    chosen_opt = None

                                    if user_trimmed.isdigit():
                                        idx = int(user_trimmed) - 1
                                        if 0 <= idx < len(saved_opts):
                                            chosen_opt = saved_opts[idx]
                                    else:
                                        for opt_lbl in saved_opts:
                                            if opt_lbl.lower() in user_trimmed.lower() or user_trimmed.lower() in opt_lbl.lower():
                                                chosen_opt = opt_lbl
                                                break

                                    if chosen_opt or any(k in user_trimmed.lower() for k in ["view", "table", "open", "page", "navigate", "download", "export"]):
                                        await local_session.delete(active_choice_state)
                                        await local_session.commit()

                                        chosen_str = (chosen_opt or user_trimmed).lower()
                                        if any(k in chosen_str for k in ["open", "page", "navigate"]):
                                            nav_dest = rep_url
                                            if not nav_dest:
                                                from app.tools.navigation import load_client_sitemap
                                                all_client_routes = await load_client_sitemap(local_session, int(client_id))
                                                for r in all_client_routes:
                                                    r_lbl = r.get("label", "").lower()
                                                    if rep_entity.lower() in r_lbl or r_lbl in rep_entity.lower():
                                                        nav_dest = r["path"]
                                                        break
                                            if not nav_dest:
                                                nav_dest = f"/{rep_entity.lower().replace(' ', '/')}"
                                            nav_text = f"Taking you to **{rep_entity}** now..."
                                            nav_actions = [{"type": "NAVIGATE", "payload": nav_dest}]
                                            ai_msg = ChatMessage(role="ai", content=nav_text, actions=nav_actions, client_id=client_id, session_id=s_id)
                                            local_session.add(ai_msg)
                                            await local_session.commit()
                                            await websocket.send_json({"text": nav_text, "actions": nav_actions, "type": "chat_response"})
                                            await websocket.send_json({"type": "done", "session_id": s_id})
                                            return
                                        elif any(k in chosen_str for k in ["download", "export", "document"]):
                                            from app.models.report_registry import ReportRegistry
                                            reg_stmt = select(ReportRegistry).where(
                                                ReportRegistry.client_id == int(client_id),
                                                ReportRegistry.display_name.ilike(f"%{rep_entity}%")
                                            )
                                            matched_rep = (await local_session.execute(reg_stmt)).scalars().first()
                                            if matched_rep:
                                                from app.services.fastpath_service import export_sql_to_excel
                                                from app.core.config import settings
                                                file_path = export_sql_to_excel(matched_rep.sql_template)
                                                file_url = f"{settings.PUBLIC_BASE_URL}/{file_path}" if "static" not in file_path else file_path
                                                res_t = f"Here is your {matched_rep.display_name}: {file_url}"
                                                res_a = [{"type": "TOOL_RESULT", "payload": file_url}]
                                            else:
                                                res_t = f"This export template hasn’t been configured in the Control Panel yet. You can view the data in chat and export directly from the data table."
                                                res_a = []
                                            ai_msg = ChatMessage(role="ai", content=res_t, actions=res_a, client_id=client_id, session_id=s_id)
                                            local_session.add(ai_msg)
                                            await local_session.commit()
                                            await websocket.send_json({"text": res_t, "actions": res_a, "type": "chat_response"})
                                            await websocket.send_json({"type": "done", "session_id": s_id})
                                            return
                                        else:
                                            # User chose to view the data table
                                            user_text = f"view {rep_entity.lower()} table"
                                    elif user_trimmed.lower() in ["cancel", "stop", "exit", "quit", "nevermind"]:
                                        await local_session.delete(active_choice_state)
                                        await local_session.commit()
                                        cancel_msg = "Report selection cancelled."
                                        ai_msg = ChatMessage(role="ai", content=cancel_msg, actions=[], client_id=client_id, session_id=s_id)
                                        local_session.add(ai_msg)
                                        await local_session.commit()
                                        await websocket.send_json({"text": cancel_msg, "actions": [], "type": "chat_response"})
                                        await websocket.send_json({"type": "done", "session_id": s_id})
                                        return

                                if active_choice_state and active_choice_state.intent == "screen_disambiguation" and active_choice_state.current_step == "resolve_screen_choice":
                                    c_data = active_choice_state.collected_data or {}
                                    saved_opts = c_data.get("options", [])
                                    user_trimmed = user_text.strip()
                                    chosen_opt = None

                                    if user_trimmed.isdigit():
                                        idx = int(user_trimmed) - 1
                                        if 0 <= idx < len(saved_opts):
                                            chosen_opt = saved_opts[idx]
                                    else:
                                        for opt in saved_opts:
                                            opt_lbl = opt.get("label", "") if isinstance(opt, dict) else str(opt)
                                            if opt_lbl.lower() in user_trimmed.lower() or user_trimmed.lower() in opt_lbl.lower():
                                                chosen_opt = opt
                                                break

                                    if chosen_opt:
                                        await local_session.delete(active_choice_state)
                                        await local_session.commit()
                                        opt_label = chosen_opt.get("label") if isinstance(chosen_opt, dict) else str(chosen_opt)
                                        opt_path = chosen_opt.get("path") if isinstance(chosen_opt, dict) else None
                                        
                                        if opt_path:
                                            nav_text = f"Taking you to **{opt_label}** now..."
                                            nav_actions = [{"type": "NAVIGATE", "payload": opt_path}]
                                            ai_msg = ChatMessage(role="ai", content=nav_text, actions=nav_actions, client_id=client_id, session_id=s_id)
                                            local_session.add(ai_msg)
                                            await local_session.commit()
                                            await websocket.send_json({"text": nav_text, "actions": nav_actions, "type": "chat_response"})
                                            await websocket.send_json({"type": "done", "session_id": s_id})
                                            return
                                        else:
                                            user_text = f"Show me the {opt_label.lower()}"
                                    elif user_trimmed.lower() in ["cancel", "stop", "exit", "quit", "nevermind"]:
                                        await local_session.delete(active_choice_state)
                                        await local_session.commit()
                                        cancel_msg = "Selection cancelled."
                                        ai_msg = ChatMessage(role="ai", content=cancel_msg, actions=[], client_id=client_id, session_id=s_id)
                                        local_session.add(ai_msg)
                                        await local_session.commit()
                                        await websocket.send_json({"text": cancel_msg, "actions": [], "type": "chat_response"})
                                        await websocket.send_json({"type": "done", "session_id": s_id})
                                        return

                                if active_choice_state and active_choice_state.intent == "dual_action_disambiguation" and active_choice_state.current_step == "resolve_dual_action":
                                    c_data = active_choice_state.collected_data or {}
                                    dest_label = c_data.get("label", active_choice_state.entity_name or "this page")
                                    dest_path = c_data.get("path")
                                    orig_q = c_data.get("original_query", user_text)
                                    user_trimmed = user_text.strip()
                                    
                                    is_table_choice = False
                                    is_nav_choice = False
                                    
                                    if user_trimmed == "1":
                                        is_table_choice = True
                                    elif user_trimmed == "2":
                                        is_nav_choice = True
                                    elif any(k in user_trimmed.lower() for k in ["table", "view", "show table", "list table", "data", "records", "rows"]):
                                        is_table_choice = True
                                    elif any(k in user_trimmed.lower() for k in ["navigate", "open", "go to", "page", "screen"]):
                                        is_nav_choice = True
                                    elif user_trimmed.lower() in ["cancel", "stop", "exit", "quit", "nevermind"]:
                                        await local_session.delete(active_choice_state)
                                        await local_session.commit()
                                        cancel_msg = "Selection cancelled."
                                        ai_msg = ChatMessage(role="ai", content=cancel_msg, actions=[], client_id=client_id, session_id=s_id)
                                        local_session.add(ai_msg)
                                        await local_session.commit()
                                        await websocket.send_json({"text": cancel_msg, "actions": [], "type": "chat_response"})
                                        await websocket.send_json({"type": "done", "session_id": s_id})
                                        return

                                    if is_nav_choice and dest_path:
                                        await local_session.delete(active_choice_state)
                                        await local_session.commit()
                                        nav_text = f"Taking you to **{dest_label}** now..."
                                        nav_actions = [{"type": "NAVIGATE", "payload": dest_path}]
                                        ai_msg = ChatMessage(role="ai", content=nav_text, actions=nav_actions, client_id=client_id, session_id=s_id)
                                        local_session.add(ai_msg)
                                        await local_session.commit()
                                        await websocket.send_json({"text": nav_text, "actions": nav_actions, "type": "chat_response"})
                                        await websocket.send_json({"type": "done", "session_id": s_id})
                                        return
                                    elif is_table_choice:
                                        await local_session.delete(active_choice_state)
                                        await local_session.commit()
                                        from app.models.semantic_mapping import SemanticMapping
                                        from sqlalchemy import or_, func
                                        clean_dest = re.sub(r'(?i)\b(list|page|screen|view|table)\b', '', dest_label).strip()
                                        sm_stmt = select(SemanticMapping).where(
                                            SemanticMapping.client_id == int(client_id),
                                            or_(
                                                SemanticMapping.route_path == dest_path,
                                                func.lower(SemanticMapping.ui_label) == dest_label.lower(),
                                                func.lower(SemanticMapping.ui_label) == clean_dest.lower(),
                                                SemanticMapping.ui_label.ilike(f"%{clean_dest}%")
                                            )
                                        )
                                        found_sm = (await local_session.execute(sm_stmt)).scalars().first()
                                        if found_sm:
                                            user_text = f"view {found_sm.ui_label.lower()} table"
                                        else:
                                            user_text = f"view {dest_label.lower()} table"

                                # 1. FastPath Navigation (GLOBAL FOR ALL MODES)
                                from app.services.fastpath_service import execute_fastpath
                                fast_text, fast_actions = await execute_fastpath(user_text, {"client_id": client_context_id, "session_id": s_id, "mode": mode}, db_session=local_session)
                                
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
                                    from app.services.conversation_service import process_conversation
                                    
                                    crud_intent = await resolve_crud_intent(user_text, int(client_id), local_session, history=formatted_history, mode=mode)
                                    
                                    # Handle Tab Disambiguation Intent directly
                                    if crud_intent and crud_intent.get("intent") == "tab_disambiguation":
                                        screen_name = crud_intent.get("screen", "this screen")
                                        tabs = crud_intent.get("tabs", [])
                                        res_text = f"I found multiple views for **{screen_name}**. Which tab would you like to see?"
                                        res_actions = [{
                                            "type": "CHOICE",
                                            "payload": tabs
                                        }]

                                        # Save state to allow numeric choice resolution ("1", "2") or text clicks
                                        existing_states = await local_session.execute(
                                            select(ConversationState).where(
                                                ConversationState.client_id == int(client_id),
                                                ConversationState.session_id == s_id
                                            )
                                        )
                                        for old_s in existing_states.scalars().all():
                                            await local_session.delete(old_s)

                                        ambig_state = ConversationState(
                                            client_id=int(client_id),
                                            session_id=s_id,
                                            intent="tab_disambiguation",
                                            entity_name=screen_name,
                                            current_step="resolve_tab_choice",
                                            collected_data={
                                                "tabs": [t["label"] for t in tabs],
                                                "original_query": user_text
                                            }
                                        )
                                        local_session.add(ambig_state)

                                        ai_msg = ChatMessage(role="ai", content=res_text, actions=res_actions, client_id=client_id, session_id=s_id)
                                        local_session.add(ai_msg)
                                        await local_session.commit()
                                        await websocket.send_json({"text": res_text, "actions": res_actions, "type": "chat_response"})
                                        await websocket.send_json({"type": "done", "session_id": s_id})
                                        return

                                    # Handle Report vs Menu Disambiguation Intent directly
                                    if crud_intent and crud_intent.get("intent") == "report_disambiguation":
                                        rep_name = crud_intent.get("entity", "this report")
                                        opts = crud_intent.get("options", [])
                                        res_text = f"I found the **{rep_name}**. Which one are you referring to?"
                                        res_actions = [{
                                            "type": "CHOICE",
                                            "payload": opts
                                        }]

                                        existing_states = await local_session.execute(
                                            select(ConversationState).where(
                                                ConversationState.client_id == int(client_id),
                                                ConversationState.session_id == s_id
                                            )
                                        )
                                        for old_s in existing_states.scalars().all():
                                            await local_session.delete(old_s)

                                        ambig_state = ConversationState(
                                            client_id=int(client_id),
                                            session_id=s_id,
                                            intent="report_disambiguation",
                                            entity_name=rep_name,
                                            current_step="resolve_report_choice",
                                            collected_data={
                                                "options": [o["label"] for o in opts],
                                                "entity": rep_name,
                                                "url": crud_intent.get("url"),
                                                "table": crud_intent.get("table")
                                            }
                                        )
                                        local_session.add(ambig_state)

                                        ai_msg = ChatMessage(role="ai", content=res_text, actions=res_actions, client_id=client_id, session_id=s_id)
                                        local_session.add(ai_msg)
                                        await local_session.commit()
                                        await websocket.send_json({"text": res_text, "actions": res_actions, "type": "chat_response"})
                                        await websocket.send_json({"type": "done", "session_id": s_id})
                                        return

                                    # Handle Screen Disambiguation Intent directly
                                    if crud_intent and crud_intent.get("intent") == "screen_disambiguation":
                                        root_name = crud_intent.get("entity", "this screen")
                                        mod_name = crud_intent.get("module")
                                        opts = crud_intent.get("options", [])
                                        
                                        mod_suffix = f" in **{mod_name}**" if mod_name and mod_name != "the menu" else ""
                                        res_text = f"I found multiple pages for **{root_name}**{mod_suffix}. Which one would you like to see?"
                                        res_actions = [{
                                            "type": "CHOICE",
                                            "payload": opts
                                        }]

                                        existing_states = await local_session.execute(
                                            select(ConversationState).where(
                                                ConversationState.client_id == int(client_id),
                                                ConversationState.session_id == s_id
                                            )
                                        )
                                        for old_s in existing_states.scalars().all():
                                            await local_session.delete(old_s)

                                        ambig_state = ConversationState(
                                            client_id=int(client_id),
                                            session_id=s_id,
                                            intent="screen_disambiguation",
                                            entity_name=root_name,
                                            current_step="resolve_screen_choice",
                                            collected_data={"options": opts}
                                        )
                                        local_session.add(ambig_state)

                                        ai_msg = ChatMessage(role="ai", content=res_text, actions=res_actions, client_id=client_id, session_id=s_id)
                                        local_session.add(ai_msg)
                                        await local_session.commit()
                                        await websocket.send_json({"text": res_text, "actions": res_actions, "type": "chat_response"})
                                        await websocket.send_json({"type": "done", "session_id": s_id})
                                        return

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
                                            
                                            print(f"🔧 [DETERMINISTIC READ] Processing table: {table_name}")
                                            
                                            # --- FAST CONTROLLER BASE QUERY CHECK ---
                                            # If this read request matches a verified semantic mapping with an exact base_query,
                                            # execute it directly for maximum speed and 100% ERP screen parity.
                                            try:
                                                from app.models.semantic_mapping import SemanticMapping
                                                from app.models.client_config import ClientConfig
                                                from app.tools.database import execute_sql_query
                                                from app.core.context import current_db_url
                                                from app.services.intent_service import NON_ENTITY_WORDS
                                                
                                                client_config = await local_session.get(ClientConfig, int(client_id))
                                                if client_config and client_config.db_connection_url:
                                                    current_db_url.set(client_config.db_connection_url)

                                                sm_stmt = select(SemanticMapping).where(SemanticMapping.client_id == int(client_id))
                                                all_sms = (await local_session.execute(sm_stmt)).scalars().all()
                                                
                                                user_q_low = user_text.lower().strip()
                                                fn_low = friendly_name.lower().strip()
                                                query_tokens = set(re.findall(r'[a-zA-Z0-9]+', user_q_low)) - NON_ENTITY_WORDS
                                                
                                                best_sm = None
                                                best_score = -999
                                                
                                                for sm in all_sms:
                                                    sm_lbl = sm.ui_label.lower().strip()
                                                    sm_toks = set(re.findall(r'[a-zA-Z0-9]+', sm_lbl)) - NON_ENTITY_WORDS
                                                    
                                                    score = 0
                                                    if sm_lbl == fn_low or sm_lbl == user_q_low:
                                                        score += 100
                                                    elif sm_lbl in user_q_low or user_q_low in sm_lbl:
                                                        score += 50
                                                    
                                                    # Core token overlap
                                                    overlap = query_tokens.intersection(sm_toks)
                                                    score += len(overlap) * 20
                                                    
                                                    # Penalize extra non-matching tokens
                                                    diff = sm_toks - query_tokens
                                                    score -= len(diff) * 5
                                                    
                                                    # Tab discriminator bonus/penalty
                                                    for td in ["pending", "completed", "active", "inactive"]:
                                                        if td in user_q_low and td in sm_lbl:
                                                            score += 30
                                                        elif td in user_q_low and td not in sm_lbl and any(other_td in sm_lbl for other_td in ["pending", "completed", "active", "inactive"]):
                                                            score -= 40
                                                            
                                                    # Report vs History/Attendance/Log discriminator bonus/penalty
                                                    if "report" in user_q_low and "report" in sm_lbl:
                                                        score += 35
                                                    elif "report" in user_q_low and any(k in sm_lbl for k in ["history", "log", "attendance", "logs"]):
                                                        score -= 45
                                                    elif any(k in user_q_low for k in ["history", "log", "attendance", "logs"]) and any(k in sm_lbl for k in ["history", "log", "attendance", "logs"]):
                                                        score += 35
                                                    elif any(k in user_q_low for k in ["history", "log", "attendance", "logs"]) and "report" in sm_lbl:
                                                        score -= 45
                                                            
                                                    if score > best_score and score >= 20:
                                                        best_score = score
                                                        best_sm = sm

                                                if best_sm and best_sm.base_query:
                                                    print(f"⚡ [FAST CONTROLLER QUERY] Executing verified base_query for '{best_sm.ui_label}' (Score: {best_score})", flush=True)
                                                    raw_records = await execute_sql_query(best_sm.base_query)
                                                    result = sanitize_for_json(raw_records)
                                                    display_title = best_sm.ui_label
                                                    actions_list = []
                                                    if isinstance(result, (list, tuple)) and result:
                                                        headers = list(result[0].keys())
                                                        actions_list.append({
                                                            "type": "data_table",
                                                            "payload": {
                                                                "title": display_title,
                                                                "headers": headers,
                                                                "rows": list(result),
                                                                "total": len(result)
                                                            }
                                                        })
                                                        response_text = f"Found **{len(result)}** record(s) in **{display_title}**."
                                                    elif isinstance(result, (list, tuple)):
                                                        response_text = f"No records found for **{display_title}**."
                                                    else:
                                                        # Result is an error string (e.g. "Database Error: table doesn't exist")
                                                        # Do NOT return - fall through to Schema RAG for intelligent table resolution
                                                        print(f"⚠️ [FAST CONTROLLER] base_query returned error for '{display_title}': {result}", flush=True)
                                                        raise ValueError(f"base_query failed: {result}")
                                                    
                                                    ai_msg = ChatMessage(role="ai", content=response_text, actions=actions_list, client_id=client_id, session_id=s_id)
                                                    local_session.add(ai_msg)
                                                    await local_session.commit()
                                                    await websocket.send_json({"text": response_text, "actions": actions_list, "type": "chat_response"})
                                                    await websocket.send_json({"type": "done", "session_id": s_id})
                                                    return
                                            except Exception as fast_err:
                                                print(f"⚠️ Fast base_query execution skipped/failed ({fast_err}), falling back", flush=True)

                                            try:
                                                from app.models.client_config import ClientConfig
                                                client_config = await local_session.get(ClientConfig, int(client_id))
                                                if client_config and client_config.schema_rag_enabled:
                                                    print(f"🧠 [SCHEMA RAG] Intercepting read request for {table_name}")
                                                    from app.services.schema_rag_service import query_legacy_db_with_schema
                                                    rag_result = await query_legacy_db_with_schema(user_text, table_name, int(client_id), local_session)
                                                    
                                                    result = sanitize_for_json(rag_result["records"])
                                                    sql_used = rag_result["generated_sql"]
                                                    
                                                    thought_process = rag_result.get("thought_process", "")
                                                    thought_msg = f"\n\n**AI Thought Process:**\n_{thought_process}_" if thought_process else ""
                                                    
                                                    actions_list = []
                                                    display_title = rag_result.get("display_title") or friendly_name
                                                    if display_title and "_" in display_title and display_title.islower():
                                                        display_title = display_title.replace("_", " ").title()

                                                    if isinstance(result, (list, tuple)) and result:
                                                        headers = list(result[0].keys())
                                                        actions_list.append({
                                                            "type": "data_table", 
                                                            "payload": {
                                                                "title": display_title, 
                                                                "headers": headers,
                                                                "rows": list(result),
                                                                "total": len(result)
                                                            }
                                                        })
                                                        
                                                        msg_text = rag_result.get("user_message", "")
                                                        if msg_text and not msg_text.lower().startswith("i cannot show"):
                                                            response_text = f"{msg_text}\n\nFound **{len(result)}** record(s) in **{display_title}**."
                                                        else:
                                                            response_text = f"Found **{len(result)}** record(s) in **{display_title}**."
                                                    elif isinstance(result, (list, tuple)):
                                                        msg_text = rag_result.get("user_message", "")
                                                        debug_block = f"\n\n<details><summary>Debug AI Query</summary>\n\n```sql\n{sql_used}\n```\n</details>" if sql_used else ""
                                                        if msg_text and not msg_text.lower().startswith("i cannot show"):
                                                            response_text = f"{msg_text}{debug_block}"
                                                        else:
                                                            response_text = f"No records found for your query.{debug_block}"
                                                    elif isinstance(result, str):
                                                        response_text = f"Database returned a response:\n{result}"
                                                    else:
                                                        response_text = f"Query executed. Result type: {type(result)}.\n\n```sql\n{sql_used}\n```"
                                                        
                                                    ai_msg = ChatMessage(role="ai", content=response_text, actions=actions_list, client_id=client_id, session_id=s_id)
                                                    local_session.add(ai_msg)
                                                    await local_session.commit()
                                                    await websocket.send_json({"text": response_text, "actions": actions_list, "type": "chat_response"})
                                                    await websocket.send_json({"type": "done", "session_id": s_id})
                                                    return
                                                    
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
                                                clean_friendly_name = friendly_name.replace("_", " ").title() if (friendly_name and "_" in friendly_name) else friendly_name
                                                actions_list = []
                                                if isinstance(result, dict) and "aggregate" in result:
                                                    # Aggregation result
                                                    agg_type = result["aggregate"]
                                                    value = result["value"]
                                                    response_text = f"**{clean_friendly_name}** — {agg_type.upper()}: **{value}**{date_info}"
                                                elif isinstance(result, dict) and "grouped_results" in result:
                                                    # Grouped aggregation
                                                    response_text = f"**{clean_friendly_name}** — Grouped Results:{date_info}"
                                                    grouped = result["grouped_results"]
                                                    g_headers = list(grouped[0].keys()) if (isinstance(grouped, list) and grouped and isinstance(grouped[0], dict)) else []
                                                    actions_list.append({
                                                        "type": "data_table",
                                                        "payload": {
                                                            "title": clean_friendly_name,
                                                            "headers": g_headers,
                                                            "rows": grouped if isinstance(grouped, list) else [],
                                                            "total": len(grouped) if isinstance(grouped, list) else 0
                                                        }
                                                    })
                                                elif isinstance(result, dict) and "records" in result:
                                                    # Records with warnings
                                                    records = result["records"]
                                                    if records:
                                                        response_text = f"Found **{len(records)}** record(s) in **{clean_friendly_name}**.{date_info}"
                                                        headers = list(records[0].keys()) if records else []
                                                        actions_list.append({
                                                            "type": "data_table", 
                                                            "payload": {
                                                                "title": clean_friendly_name, 
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
                                                        response_text = f"No records found in **{clean_friendly_name}** for the specified criteria.{date_info}"
                                                elif isinstance(result, list):
                                                    if result:
                                                        response_text = f"Found **{len(result)}** record(s) in **{clean_friendly_name}**.{date_info}"
                                                        headers = list(result[0].keys()) if result else []
                                                        actions_list.append({
                                                            "type": "data_table", 
                                                            "payload": {
                                                                "title": clean_friendly_name, 
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
                                                    
                                                    clean_friendly_name = friendly_name.replace("_", " ").title() if (friendly_name and "_" in friendly_name) else friendly_name
                                                    actions_list = []
                                                    if isinstance(result, dict) and "aggregate" in result:
                                                        response_text = f"**{clean_friendly_name}** — {result['aggregate'].upper()}: **{result['value']}**{date_info}"
                                                    elif isinstance(result, dict) and "records" in result:
                                                        records = result["records"]
                                                        if records:
                                                            response_text = f"Found **{len(records)}** record(s) in **{clean_friendly_name}**.{date_info}"
                                                            headers = list(records[0].keys()) if records else []
                                                            actions_list.append({
                                                                "type": "data_table", 
                                                                "payload": {
                                                                    "title": clean_friendly_name, 
                                                                    "headers": headers,
                                                                    "rows": records,
                                                                    "total": len(records)
                                                                }
                                                            })
                                                        else:
                                                            response_text = f"No records found in **{clean_friendly_name}** for the specified criteria.{date_info}"
                                                    elif isinstance(result, list):
                                                        if result:
                                                            response_text = f"Found **{len(result)}** record(s) in **{clean_friendly_name}**.{date_info}"
                                                            headers = list(result[0].keys()) if result else []
                                                            actions_list.append({
                                                                "type": "data_table", 
                                                                "payload": {
                                                                    "title": clean_friendly_name, 
                                                                    "headers": headers,
                                                                    "rows": result,
                                                                    "total": len(result)
                                                                }
                                                            })
                                                        else:
                                                            response_text = f"No records found in **{clean_friendly_name}** for the specified criteria.{date_info}"
                                                    else:
                                                        response_text = f"Result from **{clean_friendly_name}**: {result}{date_info}"
                                                    
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

