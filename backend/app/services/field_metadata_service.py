from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.models.field_metadata import FieldMetadata
from app.models.client_config import ClientConfig
from typing import List, Dict, Any, Optional

def _detect_storage_type(sa_type: str) -> str:
    """Maps SQLAlchemy types to Amoeba internal storage types."""
    t = sa_type.upper()
    if "INT" in t: return "integer"
    if "DECIMAL" in t or "FLOAT" in t or "NUMERIC" in t: return "float"
    if "BOOL" in t: return "boolean"
    if "DATE" in t or "TIME" in t: return "date"
    return "string"

async def generate_field_metadata(client_id: int, session: AsyncSession):
    """
    Analyzes a client's database and populates field_metadata with smart defaults.
    """
    stmt = select(ClientConfig).where(ClientConfig.id == client_id)
    result = await session.execute(stmt)
    client = result.scalars().first()
    if not client:
        return 0
        
    try:
        # We use a sync engine for discovery
        engine = create_engine(client.db_connection_url)
        inspector = inspect(engine)
    except Exception as e:
        print(f"❌ Metadata Discovery Error: {e}")
        return 0
        
    # Get existing metadata to avoid duplicates
    stmt_existing = select(FieldMetadata).where(FieldMetadata.client_id == client_id)
    result_existing = await session.execute(stmt_existing)
    existing_meta = result_existing.scalars().all()
    # Map of (table, column) -> object
    existing_map = {(m.table_name, m.column_name): m for m in existing_meta}
    
    new_metadata = []
    
    for table_name in inspector.get_table_names():
        columns = inspector.get_columns(table_name)
        pk_cols = inspector.get_pk_constraint(table_name).get("constrained_columns", [])
        
        for col in columns:
            col_name = col["name"]
            if (table_name, col_name) in existing_map:
                continue
                
            # Smart Logic for Defaults
            label = col_name.replace("_", " ").title()
            input_type = "text"
            storage_type = _detect_storage_type(str(col["type"]))
            
            # 1. Detect Read-Only (Primary Keys)
            readonly = col_name in pk_cols
            
            # 2. Detect Checkboxes
            if storage_type == "boolean" or col_name.startswith("is_") or col_name.startswith("has_"):
                input_type = "checkbox"
                
            # 3. Detect Textareas
            if storage_type == "string" and (col.get("type").__class__.__name__ == "TEXT" or "desc" in col_name.lower()):
                input_type = "textarea"
                
            # 4. Detect Dates
            if storage_type == "date":
                input_type = "date"
                
            # 5. Detect Dropdowns (Heuristic: ends with _id)
            if col_name.endswith("_id") and not readonly:
                input_type = "dropdown"
                # Note: data_source_table would be filled by relationship sync or manual admin
            
            new_meta = FieldMetadata(
                client_id=client_id,
                table_name=table_name,
                column_name=col_name,
                label=label,
                input_type=input_type,
                storage_type=storage_type,
                required=not col.get("nullable", True),
                readonly=readonly,
                is_visible=True,
                default_value=str(col.get("default")) if col.get("default") is not None else None
            )
            new_metadata.append(new_meta)
            
    if new_metadata:
        session.add_all(new_metadata)
        await session.commit()
        
    return len(new_metadata)

async def get_field_options(client_id: int, meta: FieldMetadata, session: AsyncSession) -> List[Dict[str, Any]]:
    """
    Fetches dropdown options from the client's database.
    """
    if not meta.data_source_table or not meta.value_column or not meta.display_column:
        return []
        
    stmt = select(ClientConfig).where(ClientConfig.id == client_id)
    result = await session.execute(stmt)
    client = result.scalars().first()
    if not client:
        return []
        
    try:
        # We use a sync engine here because it's a quick fetch and we're in a service
        # but ideally we'd have a pool of client engines.
        engine = create_engine(client.db_connection_url)
        with engine.connect() as conn:
            # Safely build the query
            query = text(f"SELECT {meta.value_column} AS value, {meta.display_column} AS label FROM {meta.data_source_table} LIMIT 100")
            rows = conn.execute(query).mappings().all()
            return [dict(row) for row in rows]
    except Exception as e:
        print(f"❌ Failed to fetch options for {meta.table_name}.{meta.column_name}: {e}")
        return []
