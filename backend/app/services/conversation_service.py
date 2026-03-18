from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.models.conversation_state import ConversationState
from app.models.client_config import ClientConfig
from app.models.navigation import NavigationItem
from app.models.semantic_metadata import SemanticMetadata
from app.services.crud_service import CRUDBuilder
from app.services.smart_form_service import SmartFormService
from app.services.record_selector_service import RecordSelectorService
from sqlalchemy import inspect, create_engine
from datetime import datetime
import json
import re
import traceback
from app.services.audit_service import log_audit

async def get_active_conversation(session: AsyncSession, client_id: int, session_id: str) -> Optional[ConversationState]:
    statement = select(ConversationState).where(
        ConversationState.client_id == client_id,
        ConversationState.session_id == session_id
    ).order_by(ConversationState.updated_at.desc())
    result = await session.execute(statement)
    return result.scalars().first()

async def get_friendly_entity_label(client_id: int, table_name: str, session: AsyncSession) -> str:
    """Resolves a technical table name to a user-friendly label (Sidebar name or Semantic Label)."""
    # 1. Try Navigation (HIGHEST PRIORITY)
    nav_stmt = select(NavigationItem.label).where(
        NavigationItem.client_id == client_id,
        NavigationItem.table_name == table_name
    )
    res = await session.execute(nav_stmt)
    label = res.scalars().first()
    if label: return label

    # 2. Try Semantic Metadata (Table Level Label)
    sem_stmt = select(SemanticMetadata.label).where(
        SemanticMetadata.client_id == client_id,
        SemanticMetadata.table_name == table_name,
        (SemanticMetadata.column_name == None) | (SemanticMetadata.column_name == "")
    ).limit(1)
    res = await session.execute(sem_stmt)
    label = res.scalars().first()
    if label: return label

    # 3. Fallback to Title Case
    return table_name.replace("_", " ").title()

async def process_conversation(
    user_input: str, 
    intent_data: Optional[Dict[str, Any]], 
    client_id: int, 
    session_id: str, 
    db_session: AsyncSession
) -> Tuple[Optional[str], List[Any]]:
    # 0. System Filter (Hide Pings)
    import re
    if re.search(r'\bping\b', user_input, re.I):
        print(f"🛑 [CRUD CONV] Filtered system ping: {user_input}")
        return "__SYSTEM_IGNORE__", []

    state = await get_active_conversation(db_session, client_id, session_id)
    
    # Robust cleanup for corrupted state
    if state and "ping" in (state.entity_name or "").lower():
        print(f"🗑️ [CRUD CONV] Cleaning up corrupted state with entity: {state.entity_name}")
        await db_session.delete(state)
        await db_session.commit()
        state = None
    
    print(f"🔄 [CRUD CONV] Process: input='{user_input[:50]}', has_state={state is not None}, intent_status={intent_data.get('status') if intent_data else 'None'}")
    
    # CASE 0: GLOBAL CANCEL
    if user_input.strip().lower() in ["cancel", "exit", "quit", "stop", "nevermind", "abort"]:
        print("🛑 [CRUD CONV] Global Cancel triggered.")
        if state:
            await db_session.delete(state)
            await db_session.commit()
        return "Operation cancelled.", []

    # CASE 1: NEW INTENT (Highest Priority)
    # If a new intent is detected, we ALWAYS drop the old state and start fresh.
    if intent_data:
        print(f"✨ [CRUD CONV] New Intent: {intent_data['intent']} (Status: {intent_data['status']})")
        if state:
            print(f"   🗑️ Clearing existing flow: {state.intent} {state.entity_name}")
            await db_session.delete(state)
            await db_session.commit()
            state = None

        if intent_data.get("status") == "unresolved_entity":
            # Hand over to Entity Selector for ambiguity resolution
            intent = intent_data["intent"]
            entity_query = intent_data.get("entity") or user_input
            from app.services.entity_selector import EntitySelector
            from app.services.onboarding import discover_tables
            client_config = await db_session.get(ClientConfig, client_id)
            tables = discover_tables(client_config.db_connection_url)
            table_names = [t["name"] for t in tables]
            matches = await EntitySelector.resolve_ambiguous_entity(entity_query, client_id, db_session, table_names)
            
            if matches:
                state = ConversationState(
                    client_id=client_id, session_id=session_id,
                    intent=intent, entity_name="", current_step="resolve_ambiguity",
                    collected_data={}
                )
                db_session.add(state)
                await db_session.commit()
                return f"I found multiple options for your request. Which one did you mean?", [{"type": "entity_selection", "payload": matches[:10]}]
            
            return f"I understand you want to {intent} something, but I couldn't find that entity. Please try a different name.", []

        elif intent_data.get("status") == "resolved":
            # Start a fresh flow
            state = ConversationState(
                client_id=client_id, session_id=session_id,
                intent=intent_data["intent"], entity_name=intent_data["entity"],
                current_step="start", collected_data={}
            )
            db_session.add(state)
            await db_session.commit()

    # If we still have no state and no new intent, we exit.
    if not state:
        return None, []

    # CASE 2: HANDLE AMBIGUITY RESOLUTION STEP
    if state.current_step == "resolve_ambiguity":
        print(f"🎯 [CRUD CONV] Resolving Ambiguity -> Input corresponds to entity selection: {user_input}")
        
        # FIX: Check if the user selected a NAVIGATION PATH instead of a TABLE
        if user_input.startswith("nav_path:"):
            url = user_input.replace("nav_path:", "")
            # Clear state and navigate
            await db_session.delete(state)
            await db_session.commit()
            return f"I couldn't find a direct database link for that, but I can take you to the page.", [{"type": "NAVIGATE", "payload": url}]

        state.entity_name = user_input.strip()
        state.current_step = "start"
        state.updated_at = datetime.utcnow()
        db_session.add(state)
        await db_session.commit()
    
    # CASE 3: ROUTE TO FLOW HANDLERS
    print(f"Track: Flow={state.intent}, Step={state.current_step}, Entity={state.entity_name}")
    if state.intent == "create": 
        return await handle_create_flow(user_input, state, db_session)
    elif state.intent == "read": 
        return await handle_read_flow(user_input, state, db_session)
    elif state.intent == "update": 
        return await handle_update_flow(user_input, state, db_session)
    elif state.intent == "delete": 
        return await handle_delete_flow(user_input, state, db_session)

    return "I'm not sure how to handle that CRUD operation.", []

async def handle_create_flow(user_input: str, state: ConversationState, db_session: AsyncSession) -> Tuple[str, List[Any]]:
    friendly_name = await get_friendly_entity_label(state.client_id, state.entity_name, db_session)
    
    if state.current_step == "start":
        state.current_step = "collect_data"
        db_session.add(state)
        await db_session.commit()
        form_config = await SmartFormService.generate_form(state.client_id, state.entity_name, db_session)
        return f"Please fill out the form to create a new {friendly_name}.", [{"type": "form", "payload": form_config}]

    elif state.current_step == "collect_data":
        try:
            # Check if input is likely JSON
            if not user_input.strip().startswith("{"):
                print(f"⚠️ [CREATE FLOW] Expected JSON, got text: '{user_input[:20]}'")
                form_config = await SmartFormService.generate_form(state.client_id, state.entity_name, db_session)
                return f"I'm waiting for the {friendly_name} details. Please use the form shown above.", [{"type": "form", "payload": form_config}]
                
            data = json.loads(user_input)
            client_config = await db_session.get(ClientConfig, state.client_id)
            builder = CRUDBuilder(client_config.db_connection_url)
            result = builder.execute_create(state.entity_name, data)
            await db_session.delete(state)
            await db_session.commit()
            return f"Successfully created new {friendly_name}!", [{"type": "success", "payload": "Created"}]
        except Exception as e:
            print(f"❌ [CREATE FLOW] Error: {e}")
            form_config = await SmartFormService.generate_form(state.client_id, state.entity_name, db_session)
            return f"Error creating record: {str(e)}", [{"type": "form", "payload": form_config}]
    
    return "Flow in unexpected state.", []

async def handle_read_flow(user_input: str, state: ConversationState, db_session: AsyncSession) -> Tuple[str, List[Any]]:
    friendly_name = await get_friendly_entity_label(state.client_id, state.entity_name, db_session)
    client_config = await db_session.get(ClientConfig, state.client_id)
    builder = CRUDBuilder(client_config.db_connection_url)
    try:
        data = builder.execute_read(state.entity_name)
        await db_session.delete(state)
        await db_session.commit()
        if not data: return f"No records found in {friendly_name}.", []
        return f"Found {len(data)} records in {friendly_name}.", [{"type": "success", "payload": f"Read {len(data)} records"}]
    except Exception as e: return f"Error reading: {str(e)}", []

async def handle_update_flow(user_input: str, state: ConversationState, db_session: AsyncSession) -> Tuple[str, List[Any]]:
    friendly_name = await get_friendly_entity_label(state.client_id, state.entity_name, db_session)
    
    if state.current_step == "start":
        id_match = re.search(r"\b(\d+)\b", user_input)
        if id_match: return await _init_update_form(id_match.group(1), state, db_session)
        records = await RecordSelectorService.get_records_for_selection(state.client_id, state.entity_name, db_session)
        if not records: return f"No records found to update in {friendly_name}.", []
        state.current_step = "select_record"
        db_session.add(state)
        await db_session.commit()
        return f"Which {friendly_name} would you like to update?", [{"type": "record_selection", "payload": records}]

    elif state.current_step == "select_record":
        return await _init_update_form(user_input.strip(), state, db_session)

    elif state.current_step == "collect_data":
        try:
            if not user_input.strip().startswith("{"):
                return f"Please use the form to submit your updates for {friendly_name}.", [{"type": "form", "payload": await SmartFormService.generate_form(state.client_id, state.entity_name, db_session)}]
                
            data = json.loads(user_input)
            state.collected_data = {**state.collected_data, "update_data": data}
            state.current_step = "confirm"
            db_session.add(state)
            await db_session.commit()
            return f"Confirm update for {friendly_name}?", [{"type": "confirmation", "payload": { "action": "update", "entity": friendly_name }}]
        except Exception as e: return f"Error: {str(e)}", []

    elif state.current_step == "confirm":
        if user_input.lower() in ["yes", "confirm", "ok"]:
            client_config = await db_session.get(ClientConfig, state.client_id)
            builder = CRUDBuilder(client_config.db_connection_url)
            inspector = inspect(create_engine(client_config.db_connection_url))
            pk_name = inspector.get_pk_constraint(state.entity_name)["constrained_columns"][0]
            builder.execute_update(state.entity_name, {pk_name: state.collected_data["id"]}, state.collected_data["update_data"])
            await db_session.delete(state)
            await db_session.commit()
            return f"Updated {friendly_name} successfully.", [{"type": "success", "payload": "Updated"}]
        else:
            await db_session.delete(state); await db_session.commit()
            return "Update cancelled.", []
            
    return "Update flow in unexpected state.", []

async def _init_update_form(record_id: str, state: ConversationState, db_session: AsyncSession) -> Tuple[str, List[Any]]:
    friendly_name = await get_friendly_entity_label(state.client_id, state.entity_name, db_session)
    state.collected_data = {"id": record_id}
    state.current_step = "collect_data"
    db_session.add(state); await db_session.commit()
    form_config = await SmartFormService.generate_form(state.client_id, state.entity_name, db_session)
    return f"Updating {friendly_name}. Please check the fields below:", [{"type": "form", "payload": form_config}]

async def handle_delete_flow(user_input: str, state: ConversationState, db_session: AsyncSession) -> Tuple[str, List[Any]]:
    friendly_name = await get_friendly_entity_label(state.client_id, state.entity_name, db_session)
    if state.current_step == "start":
        id_match = re.search(r"\b(\d+)\b", user_input)
        if id_match: return await _init_delete_confirm(id_match.group(1), state, db_session)
        records = await RecordSelectorService.get_records_for_selection(state.client_id, state.entity_name, db_session)
        if not records: return f"No records found to delete in {friendly_name}.", []
        state.current_step = "select_record"
        db_session.add(state); await db_session.commit()
        return f"Which {friendly_name} would you like to delete?", [{"type": "record_selection", "payload": records}]

    elif state.current_step == "select_record":
        return await _init_delete_confirm(user_input.strip(), state, db_session)
            
    elif state.current_step == "confirm":
        if user_input.lower() in ["yes", "confirm", "ok"]:
            client_config = await db_session.get(ClientConfig, state.client_id)
            builder = CRUDBuilder(client_config.db_connection_url)
            inspector = inspect(create_engine(client_config.db_connection_url))
            pk_name = inspector.get_pk_constraint(state.entity_name)["constrained_columns"][0]
            builder.execute_delete(state.entity_name, {pk_name: state.collected_data["id"]})
            await db_session.delete(state); await db_session.commit()
            return f"Deleted record from {friendly_name}.", [{"type": "success", "payload": "Deleted"}]
        else:
            await db_session.delete(state); await db_session.commit()
            return "Operation cancelled.", []
            
    return "Delete flow in unexpected state.", []

async def _init_delete_confirm(record_id: str, state: ConversationState, db_session: AsyncSession) -> Tuple[str, List[Any]]:
    friendly_name = await get_friendly_entity_label(state.client_id, state.entity_name, db_session)
    state.collected_data = {"id": record_id}
    state.current_step = "confirm"
    db_session.add(state); await db_session.commit()
    return f"Are you sure you want to delete this {friendly_name} entry?", [{"type": "confirmation", "payload": { "action": "delete", "entity": friendly_name }}]
