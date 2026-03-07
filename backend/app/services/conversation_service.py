from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.models.conversation_state import ConversationState
from app.models.client_config import ClientConfig
from app.services.crud_service import CRUDBuilder
from sqlalchemy import inspect, create_engine
from datetime import datetime
import json
from app.services.audit_service import log_audit

async def get_active_conversation(session: AsyncSession, client_id: int, session_id: str) -> Optional[ConversationState]:
    statement = select(ConversationState).where(
        ConversationState.client_id == client_id,
        ConversationState.session_id == session_id
    ).order_by(ConversationState.updated_at.desc())
    result = await session.execute(statement)
    return result.scalars().first()

async def process_conversation(
    user_input: str, 
    intent_data: Optional[Dict[str, Any]], 
    client_id: int, 
    session_id: str, 
    db_session: AsyncSession
) -> Tuple[Optional[str], List[Any]]:
    """
    Manages the state machine for CRUD conversations.
    """
    # 1. Check for existing state
    state = await get_active_conversation(db_session, client_id, session_id)
    
    if not state and not intent_data:
        return None, []

    # 2. Handle New Intent with Unresolved Entity (CLARIFICATION)
    if intent_data and intent_data.get("status") == "unresolved_entity":
        intent = intent_data["intent"]
        available = ", ".join(intent_data.get("available_entities", []))
        return f"I understand you want to {intent} something, but I couldn't find that entity. Did you mean one of these: {available}?", []

    # 3. Handle Errors
    if intent_data and intent_data.get("status") == "error":
        return "I encountered a system error while trying to process your request. Please try again later.", []

    # 4. Start new workflow if intent detected (RESOLVED)
    if intent_data and intent_data.get("status") == "resolved":
        # If we have an existing state, override it
        if state:
            await db_session.delete(state)
            await db_session.commit()
            
        state = ConversationState(
            client_id=client_id,
            session_id=session_id,
            intent=intent_data["intent"],
            entity_name=intent_data["entity"],
            current_step="start",
            collected_data={}
        )
        db_session.add(state)
        await db_session.commit()

    # 5. Handle specific intents
    if state:
        if state.intent == "create":
            return await handle_create_flow(user_input, state, db_session)
        elif state.intent == "read":
            return await handle_read_flow(user_input, state, db_session)
        elif state.intent == "update":
            return await handle_update_flow(user_input, state, db_session)
        elif state.intent == "delete":
            return await handle_delete_flow(user_input, state, db_session)

    return "I'm not sure how to handle that CRUD operation yet.", []

async def get_table_columns(client_id: int, table_name: str, db_session: AsyncSession) -> List[str]:
    client_config = await db_session.get(ClientConfig, client_id)
    engine = create_engine(client_config.db_connection_url)
    inspector = inspect(engine)
    columns = [col["name"] for col in inspector.get_columns(table_name) if not col.get("primary_key") and not col.get("autoincrement")]
    return columns

async def handle_create_flow(user_input: str, state: ConversationState, db_session: AsyncSession) -> Tuple[str, List[Any]]:
    print(f"DEBUG: CONVERSATION_SERVICE - handle_create_flow, step: {state.current_step}")
    columns = await get_table_columns(state.client_id, state.entity_name, db_session)
    print(f"DEBUG: CONVERSATION_SERVICE - Columns for {state.entity_name}: {columns}")
    
    if state.current_step == "start":
        state.current_step = "collect_data"
        state.updated_at = datetime.utcnow()
        db_session.add(state)
        await db_session.commit()
        
        print("DEBUG: CONVERSATION_SERVICE - Returning form_request")
        return f"To create a new {state.entity_name}, I need some information.", [{
            "type": "form_request",
            "payload": {
                "entity": state.entity_name,
                "fields": columns
            }
        }]

    if state.current_step == "collect_data":
        try:
            data = json.loads(user_input)
            client_config = await db_session.get(ClientConfig, state.client_id)
            builder = CRUDBuilder(client_config.db_connection_url)
            
            result = builder.execute_create(state.entity_name, data)
            log_audit(state.client_id, "crud_create", {"entity": state.entity_name, "result": str(result)})
            
            await db_session.delete(state)
            await db_session.commit()
            
            return f"Successfully created new {state.entity_name}!", [{"type": "success", "payload": "Created"}]
        except Exception as e:
            print(f"❌ Create Error: {e}")
            return f"Error creating record: {str(e)}. Please check your data and try again.", [{
                "type": "form_request",
                "payload": {
                    "entity": state.entity_name,
                    "fields": columns
                }
            }]

    return "Implementation in progress...", []

async def handle_read_flow(user_input: str, state: ConversationState, db_session: AsyncSession) -> Tuple[str, List[Any]]:
    client_config = await db_session.get(ClientConfig, state.client_id)
    builder = CRUDBuilder(client_config.db_connection_url)
    try:
        data = builder.execute_read(state.entity_name)
        log_audit(state.client_id, "crud_read", {"entity": state.entity_name, "count": len(data)})
        
        await db_session.delete(state)
        await db_session.commit()
        
        if not data:
            return f"No records found in {state.entity_name}.", []
            
        summary = f"Found {len(data)} records in {state.entity_name}:\n"
        for row in data:
            summary += f"- {row}\n"
            
        return summary, [{"type": "success", "payload": f"Read {len(data)} records"}]
    except Exception as e:
        return f"Error reading from {state.entity_name}: {str(e)}", []

async def handle_update_flow(user_input: str, state: ConversationState, db_session: AsyncSession) -> Tuple[str, List[Any]]:
    if state.current_step == "start":
        import re
        id_match = re.search(r"\b(\d+)\b", user_input)
        if id_match:
            record_id = id_match.group(1)
            state.collected_data = {"id": record_id}
            state.current_step = "collect_data"
            state.updated_at = datetime.utcnow()
            db_session.add(state)
            await db_session.commit()
            
            columns = await get_table_columns(state.client_id, state.entity_name, db_session)
            return f"Update {state.entity_name} ID {record_id}. Enter new values:", [{
                "type": "form_request",
                "payload": {
                    "entity": state.entity_name,
                    "fields": columns
                }
            }]
        else:
            return f"Please provide the ID of the {state.entity_name} you want to update.", []

    if state.current_step == "collect_data":
        try:
            data = json.loads(user_input)
            # Create a new dict to trigger SQLAlchemy change detection for JSON column
            new_collected_data = dict(state.collected_data)
            new_collected_data["update_data"] = data
            state.collected_data = new_collected_data
            
            state.current_step = "confirm"
            state.updated_at = datetime.utcnow()
            db_session.add(state)
            await db_session.commit()
            
            return f"Confirm update for {state.entity_name} ID {state.collected_data['id']}?", [{
                "type": "confirmation",
                "payload": {
                    "action": "update",
                    "entity": state.entity_name,
                    "id": state.collected_data["id"]
                }
            }]
        except Exception as e:
            print(f"❌ Update Data Error: {e}")
            return f"Error processing update data: {str(e)}. Please try again.", []

    if state.current_step == "confirm":
        if user_input.lower() in ["yes", "confirm", "ok"]:
            try:
                client_config = await db_session.get(ClientConfig, state.client_id)
                builder = CRUDBuilder(client_config.db_connection_url)
                
                # Get PK
                engine = create_engine(client_config.db_connection_url)
                inspector = inspect(engine)
                pk_cols = inspector.get_pk_constraint(state.entity_name)["constrained_columns"]
                pk_name = pk_cols[0] if pk_cols else "id"
                
                rows = builder.execute_update(state.entity_name, {pk_name: state.collected_data["id"]}, state.collected_data["update_data"])
                log_audit(state.client_id, "crud_update", {"entity": state.entity_name, "id": state.collected_data["id"], "rows": rows})
                
                await db_session.delete(state)
                await db_session.commit()
                
                return f"Successfully updated {rows} record(s) in {state.entity_name}.", [{"type": "success", "payload": "Updated"}]
            except Exception as e:
                return f"Error updating record: {str(e)}.", []
        else:
            await db_session.delete(state)
            await db_session.commit()
            return "Update cancelled.", []

    return "Update flow implementation continue...", []

async def handle_delete_flow(user_input: str, state: ConversationState, db_session: AsyncSession) -> Tuple[str, List[Any]]:
    if state.current_step == "start":
        import re
        id_match = re.search(r"\b(\d+)\b", user_input)
        if id_match:
            record_id = id_match.group(1)
            state.collected_data = {"id": record_id}
            state.current_step = "confirm"
            state.updated_at = datetime.utcnow()
            db_session.add(state)
            await db_session.commit()
            return f"Are you sure you want to delete {state.entity_name} with ID {record_id}?", [{
                "type": "confirmation",
                "payload": {
                    "action": "delete",
                    "entity": state.entity_name,
                    "id": record_id
                }
            }]
        else:
            return f"Please provide the ID of the {state.entity_name} you want to delete.", []
            
    if state.current_step == "confirm":
        if user_input.lower() in ["yes", "confirm", "ok"]:
            client_config = await db_session.get(ClientConfig, state.client_id)
            builder = CRUDBuilder(client_config.db_connection_url)
            try:
                engine = create_engine(client_config.db_connection_url)
                inspector = inspect(engine)
                pk_cols = inspector.get_pk_constraint(state.entity_name)["constrained_columns"]
                pk_name = pk_cols[0] if pk_cols else "id"
                
                rows = builder.execute_delete(state.entity_name, {pk_name: state.collected_data["id"]})
                log_audit(state.client_id, "crud_delete", {"entity": state.entity_name, "id": state.collected_data["id"], "rows": rows})
                
                await db_session.delete(state)
                await db_session.commit()
                return f"Successfully deleted {rows} record(s).", [{"type": "success", "payload": "Deleted"}]
            except Exception as e:
                return f"Error deleting: {str(e)}", []
        else:
            await db_session.delete(state)
            await db_session.commit()
            return "Operation cancelled.", []

    return "Delete flow implementation continue...", []
