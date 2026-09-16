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

import uuid
from app.services.crud_llm_service import CrudLlmService
from app.services.crud_foundation import validate_operation, execute_crud_operation
from app.models.crud_schema import CrudOperation


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

    # 1.25. Search Semantic Mappings (Codebase UI Labels)
    from app.models.semantic_mapping import SemanticMapping
    map_stmt = select(SemanticMapping.ui_label).where(
        SemanticMapping.client_id == client_id,
        SemanticMapping.database_table == table_name
    )
    map_res = await session.execute(map_stmt)
    mapping_label = map_res.scalars().first()
    if mapping_label:
        base_label = mapping_label

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

    # 2.5 Ensure base_label never contains raw table underscores
    if base_label and "_" in base_label:
        base_label = base_label.replace("_", " ").title()

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
        curr_intent = intent_data.get("intent", "unknown")
        curr_status = intent_data.get("status", "resolved")
        print(f"✨ [CRUD CONV] New Intent: {curr_intent} (Status: {curr_status})")
        
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
            intent = intent_data.get("intent", "read")
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
                    await db_session.refresh(state)
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
                        collected_data={"original_query": user_input}
                    )
                    db_session.add(state)
                    await db_session.commit()
                    return f"I found multiple options for your request. Which one did you mean?", [{"type": "entity_selection", "payload": matches[:10]}]
            
            return f"I understand you want to {intent} something, but I couldn't find that entity. Please try a different name.", []

        elif intent_data.get("status") in ["resolved", None] and intent_data.get("entity"):
            # Start a fresh flow
            init_data = {"ui_label": intent_data.get("label")} if intent_data.get("label") else {}
            state = ConversationState(
                client_id=client_id, session_id=session_id,
                intent=intent_data.get("intent", "read"), entity_name=intent_data.get("entity", ""),
                module=intent_data.get("module"),
                view_mode=view_mode,
                current_step="start", collected_data=init_data
            )
            db_session.add(state)
            await db_session.commit()
            await db_session.refresh(state)
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

        # Check if input is table_name or label from matches
        from app.models.navigation import NavigationItem
        from app.models.semantic_mapping import SemanticMapping
        clean_in = user_input.strip()
        nav_stmt = select(NavigationItem).where(
            NavigationItem.client_id == client_id,
            (NavigationItem.table_name == clean_in) | (NavigationItem.label == clean_in)
        )
        nav_res = await db_session.execute(nav_stmt)
        nav_item = nav_res.scalars().first()
        if nav_item:
            state.module = nav_item.module
            state.entity_name = nav_item.table_name or clean_in
            if not state.collected_data: state.collected_data = {}
            state.collected_data["ui_label"] = nav_item.label
            log_event(client_id, action="CONTEXT_MODULE_SET", entity=nav_item.label, table_name=state.entity_name, details={"module": nav_item.module, "entity": state.entity_name})
        else:
            sm_stmt = select(SemanticMapping).where(
                SemanticMapping.client_id == client_id,
                (SemanticMapping.database_table == clean_in) | (SemanticMapping.ui_label == clean_in)
            )
            sm_res = await db_session.execute(sm_stmt)
            sm_item = sm_res.scalars().first()
            if sm_item:
                state.entity_name = sm_item.database_table
                if not state.collected_data: state.collected_data = {}
                state.collected_data["ui_label"] = sm_item.ui_label
            else:
                state.entity_name = clean_in

        state.current_step = "start"
        state.updated_at = datetime.utcnow()
        if state.collected_data and "original_query" in state.collected_data:
            user_input = state.collected_data["original_query"]
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
    friendly_name = await get_friendly_entity_label(state.client_id, state.entity_name, db_session, module=state.module)
    if state.module:
        log_event(state.client_id, action="CONTEXT_MODULE_USED", entity=friendly_name, table_name=state.entity_name, details={"module": state.module, "intent": "create"})
    
    if state.current_step in ["start", "collect_fields"]:
        full_query = user_input if state.current_step == "start" else state.collected_data.get("original_request", "") + ". " + user_input
        try:
            crud_op = await CrudLlmService.generate_crud_operation(
                client_id=state.client_id,
                session=db_session,
                action="CREATE",
                table_name=state.entity_name,
                concept=friendly_name,
                user_query=full_query
            )
            
            field_metadata = await CrudLlmService._get_field_metadata(db_session, state.client_id, state.entity_name)
            missing_required_fields = []
            
            for f in field_metadata:
                if f.get("is_required"):
                    col_name = f["column_name"]
                    val = crud_op.fields.get(col_name)
                    if val is None or str(val).strip() == "":
                        if f.get("default_value") is not None:
                            crud_op.fields[col_name] = f["default_value"]
                        else:
                            missing_required_fields.append(col_name.replace('_', ' ').title())
                            
            if missing_required_fields:
                missing_str = ", ".join(missing_required_fields)
                state.current_step = "collect_fields"
                if not state.collected_data: state.collected_data = {}
                state.collected_data["original_request"] = full_query
                db_session.add(state)
                await db_session.commit()
                return f"To create this {friendly_name}, I need a bit more information. Please provide: {missing_str}.", []
            
            is_valid, err, context = await validate_operation(crud_op, state.client_id, "SYSTEM", db_session)
            if not is_valid:
                # Flow reset on validation fail
                await db_session.delete(state)
                await db_session.commit()
                return f"Validation failed: {err}", []
                
            op_id = str(uuid.uuid4())
            if not state.collected_data: state.collected_data = {}
            state.collected_data["operation_id"] = op_id
            state.collected_data["operation_data"] = crud_op.model_dump()
            state.collected_data["ui_label"] = friendly_name
            state.current_step = "confirm"
            db_session.add(state)
            await db_session.commit()
            
            display_fields = {}
            for k, v in crud_op.fields.items():
                friendly_k = k.replace('_', ' ').title()
                display_fields[friendly_k] = v

            payload = {
                "action": "CREATE",
                "entity_label": friendly_name,
                "fields": display_fields,
                "operation_id": op_id
            }
            return f"Please confirm the creation of the new {friendly_name}.", [{"type": "crud_confirmation", "payload": payload}]
        except Exception as e:
            traceback.print_exc()
            await db_session.delete(state)
            await db_session.commit()
            return f"Error preparing CREATE operation: {e}", []
            
    elif state.current_step == "confirm":
        if user_input.strip().lower() in ["yes", "confirm", "ok", "proceed", "create"]:
            return "Please use the Confirm button in the UI above to safely execute this operation.", []
        else:
            await db_session.delete(state)
            await db_session.commit()
            return "Creation cancelled.", []
    
    return "Flow in unexpected state.", []

async def handle_read_flow(user_input: str, state: ConversationState, db_session: AsyncSession) -> Tuple[str, List[Any]]:
    ui_label = state.collected_data.get("ui_label") if state.collected_data else None
    if ui_label:
        friendly_name = ui_label
    else:
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
        filters = await CrudLlmService.extract_filters(state.client_id, db_session, "UPDATE", state.entity_name, friendly_name, user_input)
        
        result = await CRUDService.read_records(
            table_name=state.entity_name, 
            filters=filters, 
            limit=10, 
            client_id=state.client_id
        )
        records = result.get("records", result) if isinstance(result, dict) else result
        
        if not records:
            await db_session.delete(state)
            await db_session.commit()
            return f"I couldn't find any {friendly_name} matching that description. Please try again with different keywords.", []
            
        if len(records) > 1:
            formatted_records = []
            selection_map = {}
            for r in records:
                rid = r.get("id") or list(r.values())[0]
                label_parts = [str(v) for k, v in r.items() if v and isinstance(v, str) and k != "id"][:2]
                label = " | ".join(label_parts) if label_parts else f"Entry #{rid}"
                token = str(uuid.uuid4())
                selection_map[token] = str(rid)
                formatted_records.append({"token": token, "label": label})
                
            state.current_step = "select_record"
            if not state.collected_data: state.collected_data = {}
            state.collected_data["original_request"] = user_input
            state.collected_data["selection_map"] = selection_map
            db_session.add(state)
            await db_session.commit()
            return f"I found multiple matching records. Which {friendly_name} would you like to update?", [{"type": "record_selection", "payload": formatted_records}]
            
        return await _stage_update(records[0], user_input, state, db_session, friendly_name)

    elif state.current_step == "select_record":
        token = user_input.strip()
        selection_map = state.collected_data.get("selection_map", {})
        record_id = selection_map.get(token)
        if not record_id:
            return "Invalid selection. Please select a valid record from the options provided.", []
            
        result = await CRUDService.read_records(
            table_name=state.entity_name, 
            filters={"id": record_id}, 
            limit=1, 
            client_id=state.client_id
        )
        records = result.get("records", result) if isinstance(result, dict) else result
        if not records:
            return "That record no longer exists. Please try again.", []
            
        original_req = state.collected_data.get("original_request", "")
        return await _stage_update(records[0], original_req, state, db_session, friendly_name)

    elif state.current_step == "confirm":
        if user_input.strip().lower() in ["yes", "confirm", "ok", "proceed", "update"]:
            return "Please use the Confirm button in the UI above to safely execute this operation.", []
        else:
            await db_session.delete(state)
            await db_session.commit()
            return "Update cancelled.", []
            
    return "Update flow in unexpected state.", []

async def _stage_update(record: dict, user_query: str, state: ConversationState, db_session: AsyncSession, friendly_name: str) -> Tuple[str, List[Any]]:
    try:
        record_id = record.get("id") or list(record.values())[0]
        crud_op = await CrudLlmService.generate_crud_operation(
            client_id=state.client_id,
            session=db_session,
            action="UPDATE",
            table_name=state.entity_name,
            concept=friendly_name,
            user_query=user_query,
            record_id=record_id,
            record_data=record
        )
        
        is_valid, err, context = await validate_operation(crud_op, state.client_id, "SYSTEM", db_session)
        if not is_valid:
            await db_session.delete(state)
            await db_session.commit()
            return f"Validation failed: {err}", []
            
        op_id = str(uuid.uuid4())
        if not state.collected_data: state.collected_data = {}
        state.collected_data["operation_id"] = op_id
        state.collected_data["operation_data"] = crud_op.model_dump()
        state.collected_data["ui_label"] = friendly_name
        
        label_parts = [str(v) for k, v in record.items() if v and isinstance(v, str) and k != "id"][:2]
        record_label = f"{friendly_name} (" + " | ".join(label_parts) + ")" if label_parts else f"{friendly_name} #{record_id}"
        state.collected_data["record_label"] = record_label
        
        state.current_step = "confirm"
        db_session.add(state)
        await db_session.commit()
        
        # Build business-friendly fields output
        display_fields = {}
        for k, v in crud_op.fields.items():
            friendly_k = k.replace('_', ' ').title()
            old_val = record.get(k)
            if old_val is not None and str(old_val) != str(v):
                display_fields[friendly_k] = {"old": old_val, "new": v}
            else:
                display_fields[friendly_k] = v

        payload = {
            "action": "UPDATE",
            "entity_label": friendly_name,
            "record_label": record_label,
            "fields": display_fields,
            "operation_id": op_id
        }
        return f"Please confirm the updates for {record_label}.", [{"type": "crud_confirmation", "payload": payload}]
    except Exception as e:
        traceback.print_exc()
        await db_session.delete(state)
        await db_session.commit()
        return f"Error preparing UPDATE operation: {e}", []

async def handle_delete_flow(user_input: str, state: ConversationState, db_session: AsyncSession) -> Tuple[str, List[Any]]:
    friendly_name = await get_friendly_entity_label(state.client_id, state.entity_name, db_session, module=state.module)
    if state.module:
        log_event(state.client_id, action="CONTEXT_MODULE_USED", entity=friendly_name, table_name=state.entity_name, details={"module": state.module, "intent": "delete"})
    
    if state.current_step == "start":
        filters = await CrudLlmService.extract_filters(state.client_id, db_session, "DELETE", state.entity_name, friendly_name, user_input)
        
        result = await CRUDService.read_records(
            table_name=state.entity_name, 
            filters=filters, 
            limit=10, 
            client_id=state.client_id
        )
        records = result.get("records", result) if isinstance(result, dict) else result
        
        if not records:
            await db_session.delete(state)
            await db_session.commit()
            return f"I couldn't find any {friendly_name} matching that description to delete.", []
            
        if len(records) > 1:
            formatted_records = []
            selection_map = {}
            for r in records:
                rid = r.get("id") or list(r.values())[0]
                label_parts = [str(v) for k, v in r.items() if v and isinstance(v, str) and k != "id"][:2]
                label = " | ".join(label_parts) if label_parts else f"Entry #{rid}"
                token = str(uuid.uuid4())
                selection_map[token] = str(rid)
                formatted_records.append({"token": token, "label": label})
                
            state.current_step = "select_record"
            if not state.collected_data: state.collected_data = {}
            state.collected_data["original_request"] = user_input
            state.collected_data["selection_map"] = selection_map
            db_session.add(state)
            await db_session.commit()
            return f"I found multiple matching records. Which {friendly_name} would you like to delete?", [{"type": "record_selection", "payload": formatted_records}]
            
        return await _stage_delete(records[0], state, db_session, friendly_name)

    elif state.current_step == "select_record":
        token = user_input.strip()
        selection_map = state.collected_data.get("selection_map", {})
        record_id = selection_map.get(token)
        if not record_id:
            return "Invalid selection. Please select a valid record from the options provided.", []
            
        result = await CRUDService.read_records(
            table_name=state.entity_name, 
            filters={"id": record_id}, 
            limit=1, 
            client_id=state.client_id
        )
        records = result.get("records", result) if isinstance(result, dict) else result
        if not records:
            return "That record no longer exists. Please try again.", []
            
        return await _stage_delete(records[0], state, db_session, friendly_name)
            
    elif state.current_step == "confirm":
        if user_input.strip().lower() in ["yes", "confirm", "ok", "proceed", "delete"]:
            return "Please use the Confirm button in the UI above to safely execute this operation.", []
        else:
            await db_session.delete(state)
            await db_session.commit()
            return "Deletion cancelled.", []
            
    return "Delete flow in unexpected state.", []

async def _stage_delete(record: dict, state: ConversationState, db_session: AsyncSession, friendly_name: str) -> Tuple[str, List[Any]]:
    try:
        record_id = record.get("id") or list(record.values())[0]
        
        crud_op = CrudOperation(
            action="DELETE",
            table=state.entity_name,
            record_id=record_id,
            fields={}
        )
        
        is_valid, err, context = await validate_operation(crud_op, state.client_id, "SYSTEM", db_session)
        if not is_valid:
            await db_session.delete(state)
            await db_session.commit()
            return f"Validation failed: {err}", []
            
        op_id = str(uuid.uuid4())
        if not state.collected_data: state.collected_data = {}
        state.collected_data["operation_id"] = op_id
        state.collected_data["operation_data"] = crud_op.model_dump()
        state.collected_data["ui_label"] = friendly_name
        
        label_parts = [str(v) for k, v in record.items() if v and isinstance(v, str) and k != "id"][:2]
        record_label = f"{friendly_name} (" + " | ".join(label_parts) + ")" if label_parts else f"{friendly_name} #{record_id}"
        state.collected_data["record_label"] = record_label
        
        state.current_step = "confirm"
        db_session.add(state)
        await db_session.commit()
        
        payload = {
            "action": "DELETE",
            "entity_label": friendly_name,
            "record_label": record_label,
            "fields": {},
            "operation_id": op_id
        }
        return f"🚨 Are you absolutely sure you want to DELETE {record_label}?", [{"type": "crud_confirmation", "payload": payload}]
    except Exception as e:
        traceback.print_exc()
        await db_session.delete(state)
        await db_session.commit()
        return f"Error preparing DELETE operation: {e}", []
