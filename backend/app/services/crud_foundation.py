import json
from typing import Dict, Any, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.models.crud_schema import CrudOperation
from app.models.field_metadata import FieldMetadata
from app.models.semantic_mapping import SemanticMapping
from app.models.audit_log import AuditLog
from app.core.context import current_db_url
from app.tools.database import _get_async_url

async def _check_authorization(user_id: str, action: str, table: str) -> bool:
    """Mock authorization check for Phase 2 CRUD Foundation."""
    # In a real app, query RBAC tables
    return True

async def get_app_concept_filter(session: AsyncSession, client_id: int, table_name: str) -> Optional[str]:
    """Fetches the structural filter for the table from SemanticMapping, FieldMetadata, or SemanticMetadata."""
    stmt = select(SemanticMapping).where(
        SemanticMapping.client_id == client_id,
        SemanticMapping.database_table == table_name
    )
    res = await session.execute(stmt)
    mapping = res.scalars().first()
    if mapping:
        return mapping.default_filter if mapping.default_filter else "1=1"

    # Fallback check for semantic metadata or field metadata approval
    from app.models.semantic_metadata import SemanticMetadata
    sem_stmt = select(SemanticMetadata).where(
        SemanticMetadata.client_id == client_id,
        SemanticMetadata.table_name == table_name
    )
    sem_res = await session.execute(sem_stmt)
    if sem_res.scalars().first():
        return "1=1"

    fm_stmt = select(FieldMetadata).where(
        FieldMetadata.client_id == client_id,
        FieldMetadata.table_name == table_name
    )
    fm_res = await session.execute(fm_stmt)
    if fm_res.scalars().first():
        return "1=1"

    return "1=1" # Allow configured database tables by default

from app.models.client_config import ClientConfig

async def validate_operation(operation: CrudOperation, client_id: int, user_id: str, session: AsyncSession) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Validates a requested CRUD operation against safety boundaries.
    Returns: (is_valid, error_message, validated_context)
    """
    # 0. System-Level Operations Mode Enforcement
    client_config = await session.get(ClientConfig, client_id)
    if not client_config:
        return False, "Client configuration not found.", {}
        
    # 1. Action Check
    if operation.action.upper() not in ["CREATE", "UPDATE", "DELETE"]:
        return False, f"Unknown action: {operation.action}", {}

    # 2. Authorization
    is_authorized = await _check_authorization(user_id, operation.action, operation.table)
    if not is_authorized:
        return False, "Unauthorized operation.", {}

    # 3. Bulk Modification Check (Phase 2 constraint)
    if operation.action.upper() in ["UPDATE", "DELETE"] and not operation.record_id:
        return False, "Bulk UPDATE/DELETE is disabled. A specific record_id must be provided.", {}

    # 4. App Concept Boundary Check
    app_filter = await get_app_concept_filter(session, client_id, operation.table)
    if not app_filter:
        return False, f"Table '{operation.table}' is not an approved App Concept or has no structural filter configured.", {}

    # 5. Field Validation
    if operation.fields and operation.action.upper() in ["CREATE", "UPDATE"]:
        # Fetch allowed physical columns from FieldMetadata (case-insensitive)
        from sqlalchemy import func, inspect, create_engine
        stmt = select(FieldMetadata).where(
            FieldMetadata.client_id == client_id,
            func.lower(FieldMetadata.table_name) == operation.table.lower()
        )
        res = await session.execute(stmt)
        allowed_fields = {f.column_name.lower() for f in res.scalars().all()}
        
        if not allowed_fields:
            if client_config:
                sync_url = client_config.db_connection_url
                if sync_url.startswith("postgresql+asyncpg://"): sync_url = sync_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
                elif sync_url.startswith("postgresql://"): sync_url = sync_url.replace("postgresql://", "postgresql+psycopg2://")
                elif sync_url.startswith("mysql+aiomysql://"): sync_url = sync_url.replace("mysql+aiomysql://", "mysql+pymysql://")
                elif sync_url.startswith("mysql://"): sync_url = sync_url.replace("mysql://", "mysql+pymysql://")
                elif sync_url.startswith("sqlite+aiosqlite://"): sync_url = sync_url.replace("sqlite+aiosqlite://", "sqlite://")
                try:
                    engine = create_engine(sync_url)
                    inspector = inspect(engine)
                    cols = inspector.get_columns(operation.table)
                    allowed_fields = {c["name"].lower() for c in cols}
                except Exception:
                    pass

        for field in operation.fields.keys():
            if field.lower() not in allowed_fields:
                return False, f"Unknown or restricted field: '{field}'. Modification rejected.", {}

    context = {
        "app_filter": app_filter,
        "is_safe": True
    }
    return True, "", context

async def generate_human_preview(operation: CrudOperation) -> str:
    """Generates a human-readable preview of the action for confirmation."""
    action = operation.action.upper()
    if action == "DELETE":
        return f"🚨 You are about to **DELETE** record #{operation.record_id} from **{operation.table}**.\n\nAre you sure?"
    elif action == "UPDATE":
        changes = ", ".join([f"**{k}** to `{v}`" for k, v in operation.fields.items()])
        return f"You are about to **UPDATE** record #{operation.record_id} in **{operation.table}**.\nChanges: {changes}\n\nConfirm?"
    elif action == "CREATE":
        fields = ", ".join([f"**{k}**: `{v}`" for k, v in operation.fields.items()])
        return f"You are about to **CREATE** a new record in **{operation.table}**.\nData: {fields}\n\nConfirm?"
    return "Unknown operation preview."

async def execute_crud_operation(operation: CrudOperation, client_id: int, user_id: str, session: AsyncSession, client_db_url: str) -> Tuple[bool, str]:
    """
    Executes the CRUD operation securely using parameterized queries and transactions.
    """
    # 1. REVALIDATE
    is_valid, err, context = await validate_operation(operation, client_id, user_id, session)
    if not is_valid:
        return False, f"Revalidation Failed: {err}"
        
    app_filter = context["app_filter"]
    action = operation.action.upper()

    # 2. Connect to Client DB
    async_url = _get_async_url(client_db_url)
    engine = create_async_engine(async_url)
    
    try:
        async with engine.begin() as conn: # BEGIN TRANSACTION
            
            # 3. Parameterized Query Construction
            if action == "UPDATE":
                set_clauses = []
                params = {"record_id": operation.record_id}
                
                for i, (k, v) in enumerate(operation.fields.items()):
                    param_key = f"val_{i}"
                    set_clauses.append(f"{k} = :{param_key}")
                    params[param_key] = v
                    
                set_sql = ", ".join(set_clauses)
                
                # Structural boundary injected directly into WHERE
                sql = f"UPDATE {operation.table} SET {set_sql} WHERE id = :record_id AND {app_filter}"
                
                result = await conn.execute(text(sql), params)
                if result.rowcount == 0:
                    raise ValueError("Update failed: Record not found, or it does not belong to this App Concept.")
                    
            elif action == "DELETE":
                params = {"record_id": operation.record_id}
                
                # Structural boundary injected directly into WHERE
                # Note: Soft delete logic would be injected here based on App Concept config if present
                sql = f"DELETE FROM {operation.table} WHERE id = :record_id AND {app_filter}"
                
                result = await conn.execute(text(sql), params)
                if result.rowcount == 0:
                    raise ValueError("Delete failed: Record not found, or it does not belong to this App Concept.")
                    
            elif action == "CREATE":
                cols = list(operation.fields.keys())
                param_keys = [f"val_{i}" for i in range(len(cols))]
                
                params = {}
                for i, k in enumerate(cols):
                    params[param_keys[i]] = operation.fields[k]
                    
                cols_sql = ", ".join(cols)
                vals_sql = ", ".join([f":{pk}" for pk in param_keys])
                
                sql = f"INSERT INTO {operation.table} ({cols_sql}) VALUES ({vals_sql})"
                await conn.execute(text(sql), params)

        # 4. Audit Log (After successful commit)
        audit = AuditLog(
            client_id=client_id,
            user_id=user_id,
            action=action,
            table_name=operation.table,
            record_id=str(operation.record_id) if operation.record_id else None,
            details={"new_values": operation.fields},
            source="AI",
            status="SUCCESS"
        )
        session.add(audit)
        await session.commit()
        
        return True, "Operation successful."

    except Exception as e:
        # Audit Failure
        audit = AuditLog(
            client_id=client_id,
            user_id=user_id,
            action=action,
            table_name=operation.table,
            record_id=str(operation.record_id) if operation.record_id else None,
            details={"new_values": operation.fields},
            source="AI",
            status="FAILED"
        )
        # Note: the failure audit must be in a different transaction block or use the active session which wasn't rolled back (the engine.begin() rolled back the client db, not the app db)
        session.add(audit)
        await session.commit()
        
        return False, f"Transaction Failed (Rolled Back): {e}"
