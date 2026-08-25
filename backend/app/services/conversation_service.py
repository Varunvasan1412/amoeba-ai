from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.models.conversation_state import ConversationState
from app.models.client_config import ClientConfig
from app.models.navigation import NavigationItem
from app.models.semantic_metadata import SemanticMetadata
from app.services.crud_service import CRUDService
from app.services.smart_form_service import SmartFormService
from app.services.record_selector_service import RecordSelectorService
from sqlalchemy import inspect, create_engine
from datetime import datetime
import json
import re
import traceback
from app.services.audit_service import log_event


async def get_active_conversation(session: AsyncSession, client_id: int, session_id: str) -> Optional[ConversationState]:
    statement = select(ConversationState).where(
        ConversationState.client_id == client_id,
        ConversationState.session_id == session_id
    ).order_by(ConversationState.updated_at.desc())
    result = await session.execute(statement)
    return result.scalars().first()

async def get_friendly_entity_label(client_id: int, table_name: str, session: AsyncSession, module: Optional[str] = None) -> str:
    """
    Resolves table_name → user-friendly label with special Module context awareness.
    Priority: Navigation label (context match) > Navigation label (any) > Raw table label.
    """
    from app.models.navigation import NavigationItem
    from sqlmodel import select

    # 1. Search Navigation Index
    stmt = select(NavigationItem.label, NavigationItem.module).where(
        NavigationItem.client_id == client_id,
        NavigationItem.table_name == table_name
    )

    res = await session.execute(stmt)
    nav_items = res.all()

    base_label = None

    if nav_items:
        # A. Prioritize context-aware module match
        if module:
            for label, mod in nav_items:
                if mod and mod.lower() == module.lower():
                    base_label = label
                    break
        
        # B. Fallback to first available navigation label
        if not base_label:
            base_label = nav_items[0][0]

    # 1.5. Search Semantic Metadata (Admin Label) - Priority over Navigation if explicitly set
    sem_stmt = select(SemanticMetadata.label).where(
        SemanticMetadata.client_id == client_id,
        SemanticMetadata.table_name == table_name,
        (SemanticMetadata.column_name == None) | (SemanticMetadata.column_name == "")
    )
    sem_res = await session.execute(sem_stmt)
    sem_label = sem_res.scalars().first()
    if sem_label:
        base_label = sem_label

    # 2. Fallback to formatted table label
    if not base_label:
        from app.services.entity_selector import EntitySelector
        base_label = EntitySelector.format_table_label(table_name)

    # 3. Intelligence: Apply Module Prefix only if missing
    # This prevents "Sales Sales Enquiry" but ensures "Sales Enquiry"
    if module and module.lower() not in base_label.lower():
        final_label = f"{module} {base_label}"
    else:
        final_label = base_label

    print(f"🧠 [CRUD RESPONSE] module={module}, table_label={base_label} → final={final_label}")
    return final_label

async def process_conversation(
    user_input: str, 
    intent_data: Optional[Dict[str, Any]], 
    client_id: int, 
    session_id: str, 
    db_session: AsyncSession,
    view_mode: str = "table"
) -> Tuple[Optional[str], List[Any]]:
    # 0. System Filter (Hide Pings)
    import re
    if re.search(r'\bping\b', user_input, re.I):
        print(f"🛑 [CRUD CONV] Filtered system ping: {user_input}")
        return "__SYSTEM_IGNORE__", []

    state = await get_active_conversation(db_session, client_id, session_id)
    
    # Update existing state with latest view_mode preference
    if state:
        state.view_mode = view_mode
        state.updated_at = datetime.utcnow()
        db_session.add(state)
        await db_session.commit()
    
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
    if intent_data:
        print(f"✨ [CRUD CONV] New Intent: {intent_data['intent']} (Status: {intent_data['status']})")
        
        pronouns = ["it", "this", "that", "item", "items", "record", "records", "them", "these", "one", "ones"]
        is_pronoun = intent_data.get("use_context") or (intent_data.get("entity") in pronouns)

        # If a new intent is detected, we drop the old state UNLESS it's a pronoun
        if state and not is_pronoun:
            print(f"   🗑️ Clearing existing flow: {state.intent} {state.entity_name}")
            await db_session.delete(state)
            await db_session.commit()
            state = None

        # Resolve pronoun using context
        if is_pronoun:
             if state and state.entity_name:
                 print(f"🔄 [CRUD CONV] Resolving pronoun context: {state.entity_name} ({state.module})")
                 intent_data["entity"] = state.entity_name
                 intent_data["module"] = state.module
                 intent_data["status"] = "resolved"
             else:
                 print("⚠️ [CRUD CONV] Pronoun detected but NO active state found. Reverting to unresolved.")
                 intent_data["status"] = "unresolved_entity"
                 intent_data["entity"] = user_input # Fallback to original text for ambiguity flow

        if intent_data.get("status") == "unresolved_entity":
            # Hand over to Entity Selector for ambiguity resolution
            intent = intent_data["intent"]
            entity_query = intent_data.get("entity") or user_input
            from app.services.entity_selector import EntitySelector
            from app.services.onboarding import discover_tables
            client_config = await db_session.get(ClientConfig, client_id)
            if not client_config:
                return "Client configuration not found.", []
            tables = discover_tables(client_config.db_connection_url)
            table_names = [t["name"] for t in tables]
            matches = await EntitySelector.resolve_ambiguous_entity(entity_query, client_id, db_session, table_names, intent=intent)
            
            if matches:
                if len(matches) == 1:
                    # Single match: auto-select and proceed to flow
                    print(f"✅ [CRUD CONV] Auto-selected single entity: {matches[0]['table_name']} (Module: {matches[0].get('module')})")
                    state = ConversationState(
                        client_id=client_id, session_id=session_id,
                        intent=intent, entity_name=matches[0]["table_name"],
                        module=matches[0].get("module"),
                        view_mode=view_mode,
                        current_step="start", collected_data={}
                    )
                    db_session.add(state)
                    await db_session.commit()
                    if matches[0].get("module"):
                        log_event(client_id, action="CONTEXT_MODULE_SET", entity=matches[0].get("label") or matches[0]["table_name"], table_name=matches[0]["table_name"], details={"module": matches[0].get("module"), "entity": matches[0]["table_name"]})
                    # Fall through to flow handlers below
                else:
                    # Multiple matches: ask for disambiguation
                    state = ConversationState(
                        client_id=client_id, session_id=session_id,
                        intent=intent, entity_name="", module=None, 
                        view_mode=view_mode,
                        current_step="resolve_ambiguity",
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
                module=intent_data.get("module"),
                view_mode=view_mode,
                current_step="start", collected_data={}
            )
            db_session.add(state)
            await db_session.commit()
            if intent_data.get("module"):
                log_event(client_id, action="CONTEXT_MODULE_SET", entity=intent_data.get("entity"), table_name=intent_data.get("entity"), details={"module": intent_data["module"], "entity": intent_data["entity"]})

    # If we still have no state and no new intent, we exit.
    if not state:
        return None, []

    # NEW: Validate table existence before proceeding to any flow handler
    if state.entity_name and state.current_step != "resolve_ambiguity":
        try:
             client_config = await db_session.get(ClientConfig, client_id)
             engine = create_engine(client_config.db_connection_url)
             inspector = inspect(engine)
             if not inspector.has_table(state.entity_name):
                 print(f"❌ [CRUD CONV] Table Validation Failed: {state.entity_name}")
                 error_msg = f"I'm sorry, the table '{state.entity_name}' does not exist in your database. Please try a different request."
                 await db_session.delete(state)
                 await db_session.commit()
                 return error_msg, []
        except Exception as e:
             print(f"⚠️ Validation Check Error: {e}")

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

        # NEW: Check if input is table_name or label from matches (UI sends table_name usually)
        # We try to recover the module if possible
        from app.models.navigation import NavigationItem
        nav_stmt = select(NavigationItem).where(NavigationItem.client_id == client_id, NavigationItem.table_name == user_input.strip())
        nav_res = await db_session.execute(nav_stmt)
        nav_item = nav_res.scalars().first()
        if nav_item:
            state.module = nav_item.module
            log_event(client_id, action="CONTEXT_MODULE_SET", entity=user_input.strip(), table_name=user_input.strip(), details={"module": nav_item.module, "entity": user_input.strip()})

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
    print(f"DEBUG LABEL → module={state.module}, entity={state.entity_name}")
    friendly_name = await get_friendly_entity_label(state.client_id, state.entity_name, db_session, module=state.module)
    if state.module:
        log_event(state.client_id, action="CONTEXT_MODULE_USED", entity=friendly_name, table_name=state.entity_name, details={"module": state.module, "intent": "create"})
    
    if state.current_step == "start":
        state.current_step = "collect_data"
        db_session.add(state)
        await db_session.commit()
        form_config = await SmartFormService.generate_form(state.client_id, state.entity_name, db_session, module=state.module)
        
        final_label = friendly_name
        payload = {
            "table_name": state.entity_name,
            "fields": form_config["fields"],
            "label": final_label,
            "display_title": final_label,
            "module": state.module
        }
        print("🚀 FORM PAYLOAD:", payload)
        return f"Please fill out the form to create a new {final_label}.", [{"type": "form", "payload": payload}]

    elif state.current_step == "collect_data":
        try:
            # Check if input is likely JSON
            if not user_input.strip().startswith("{"):
                print(f"⚠️ [CREATE FLOW] Expected JSON, got text: '{user_input[:20]}'")
                form_config = await SmartFormService.generate_form(state.client_id, state.entity_name, db_session, module=state.module)
                final_label = friendly_name
                payload = {
                    "table_name": state.entity_name,
                    "fields": form_config["fields"],
                    "label": final_label,
                    "display_title": final_label,
                    "module": state.module
                }
                print("🚀 FORM PAYLOAD (RETRY):", payload)
                return f"I'm waiting for the {final_label} details. Please use the form shown above.", [{"type": "form", "payload": payload}]
                
            form_data = json.loads(user_input)
            record_id = await CRUDService.create_record(state.entity_name, form_data, user_id=None, client_id=state.client_id)
            await db_session.delete(state)
            await db_session.commit()
            return f"Successfully created new {friendly_name}!", [{"type": "success", "payload": "Created"}]
        except Exception as e:
            print(f"❌ [CREATE FLOW] Error: {e}")
            form_config = await SmartFormService.generate_form(state.client_id, state.entity_name, db_session, module=state.module)
            final_label = friendly_name
            payload = {
                "table_name": state.entity_name,
                "fields": form_config["fields"],
                "label": final_label,
                "display_title": final_label,
                "module": state.module
            }
            print("🚀 FORM PAYLOAD (ERROR):", payload)
            return f"{str(e)}", [{"type": "form", "payload": payload}]

    
    return "Flow in unexpected state.", []

async def handle_read_flow(user_input: str, state: ConversationState, db_session: AsyncSession) -> Tuple[str, List[Any]]:
    friendly_name = await get_friendly_entity_label(state.client_id, state.entity_name, db_session, module=state.module)
    if state.module:
        log_event(state.client_id, action="CONTEXT_MODULE_USED", entity=friendly_name, table_name=state.entity_name, details={"module": state.module, "intent": "read"})
    
    # Delegate the read operation to the LLM so it can parse complex filters
    # The state object remains active so the entity Context is preserved for future turns.
    return f"__DELEGATE_READ__:{state.entity_name}:{friendly_name}", []

async def handle_update_flow(user_input: str, state: ConversationState, db_session: AsyncSession) -> Tuple[str, List[Any]]:
    friendly_name = await get_friendly_entity_label(state.client_id, state.entity_name, db_session, module=state.module)
    if state.module:
        log_event(state.client_id, action="CONTEXT_MODULE_USED", entity=friendly_name, table_name=state.entity_name, details={"module": state.module, "intent": "update"})
    
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
                form_config = await SmartFormService.generate_form(state.client_id, state.entity_name, db_session, module=state.module)
                form_config.update({
                    "label": friendly_name,
                    "display_title": friendly_name,
                    "module": state.module
                })
                return f"Please use the form to submit your updates for {friendly_name}.", [{"type": "form", "payload": form_config}]
                
            form_data = json.loads(user_input)
            state.collected_data = {**state.collected_data, "update_data": form_data}
            state.current_step = "confirm"
            db_session.add(state)
            await db_session.commit()
            return f"Confirm update for {friendly_name}?", [{"type": "confirmation", "payload": { "action": "update", "entity": friendly_name }}]
        except Exception as e: return f"Error: {str(e)}", []

    elif state.current_step == "confirm":
        if user_input.lower() in ["yes", "confirm", "ok"]:
            client_config = await db_session.get(ClientConfig, state.client_id)
            inspector = inspect(create_engine(client_config.db_connection_url))
            pk_name = inspector.get_pk_constraint(state.entity_name)["constrained_columns"][0]
            count = await CRUDService.update_records(state.entity_name, {pk_name: state.collected_data["id"]}, state.collected_data["update_data"], client_id=state.client_id)
            await db_session.delete(state)
            await db_session.commit()
            return f"Updated {friendly_name} successfully.", [{"type": "success", "payload": "Updated"}]
        else:
            await db_session.delete(state); await db_session.commit()
            return "Update cancelled.", []
            
    return "Update flow in unexpected state.", []

async def _init_update_form(record_id: str, state: ConversationState, db_session: AsyncSession) -> Tuple[str, List[Any]]:
    final_label = await get_friendly_entity_label(state.client_id, state.entity_name, db_session, module=state.module)
    state.collected_data = {"id": record_id}
    state.current_step = "collect_data"
    db_session.add(state); await db_session.commit()
    form_config = await SmartFormService.generate_form(state.client_id, state.entity_name, db_session, module=state.module)
    
    payload = {
        "table_name": state.entity_name,
        "fields": form_config["fields"],
        "label": final_label,
        "display_title": final_label,
        "module": state.module,
        "record_id": record_id
    }
    print("🚀 FORM PAYLOAD (UPDATE):", payload)
    return f"Updating {final_label}. Please check the fields below:", [{"type": "form", "payload": payload}]

async def handle_delete_flow(user_input: str, state: ConversationState, db_session: AsyncSession) -> Tuple[str, List[Any]]:
    friendly_name = await get_friendly_entity_label(state.client_id, state.entity_name, db_session, module=state.module)
    if state.module:
        log_event(state.client_id, action="CONTEXT_MODULE_USED", entity=friendly_name, table_name=state.entity_name, details={"module": state.module, "intent": "delete"})
    
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
            inspector = inspect(create_engine(client_config.db_connection_url))
            pk_name = inspector.get_pk_constraint(state.entity_name)["constrained_columns"][0]
            count = await CRUDService.delete_records(state.entity_name, {pk_name: state.collected_data["id"]}, client_id=state.client_id)
            await db_session.delete(state); await db_session.commit()
            return f"Deleted record from {friendly_name}.", [{"type": "success", "payload": "Deleted"}]
        else:
            await db_session.delete(state); await db_session.commit()
            return "Operation cancelled.", []
            
    return "Delete flow in unexpected state.", []

async def _init_delete_confirm(record_id: str, state: ConversationState, db_session: AsyncSession) -> Tuple[str, List[Any]]:
    friendly_name = await get_friendly_entity_label(state.client_id, state.entity_name, db_session, module=state.module)
    state.collected_data = {"id": record_id}
    state.current_step = "confirm"
    db_session.add(state); await db_session.commit()
    return f"Are you sure you want to delete this {friendly_name} entry?", [{"type": "confirmation", "payload": { "action": "delete", "entity": friendly_name }}]
