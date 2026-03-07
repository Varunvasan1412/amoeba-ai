from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from fastapi import HTTPException

from app.models.semantic_metadata import SemanticMetadata
from app.models.client_config import ClientConfig
from app.services.onboarding import discover_tables
from app.services.audit_service import log_audit

async def get_semantic_schema(session: AsyncSession, client_id: int) -> List[SemanticMetadata]:
    """
    Fetch all semantic mappings for a client.
    """
    statement = select(SemanticMetadata).where(SemanticMetadata.client_id == client_id)
    result = await session.execute(statement)
    return result.scalars().all()

async def get_table_semantics(session: AsyncSession, client_id: int, table_name: str) -> List[SemanticMetadata]:
    """
    Fetch semantic mappings for a specific table.
    """
    statement = select(SemanticMetadata).where(
        SemanticMetadata.client_id == client_id,
        SemanticMetadata.table_name == table_name
    )
    result = await session.execute(statement)
    return result.scalars().all()

async def bulk_upsert_semantics(session: AsyncSession, client_id: int, mappings: List[Dict[str, Any]]):
    """
    Validates and upserts semantic metadata.
    
    Validation:
    1. Table must exist in Client DB.
    2. Column must exist in Client DB Table.
    
    Security:
    - Admin-only (enforced by router).
    - No mapping of ghost columns.
    """
    
    # 1. Fetch Client Config to access DB
    client_config = await session.get(ClientConfig, client_id)
    if not client_config:
        raise HTTPException(status_code=404, detail="Client not found")
        
    # 2. Discover Real Schema (Validation Source of Truth)
    try:
        # Note: discover_tables is synchronous, might block slightly. 
        # In high-load, offload to threadpool. For admin action, it's fine.
        real_schema = discover_tables(client_config.db_connection_url)
        # Convert to fast lookup dict: {"table_name": {"col1", "col2"}}
        schema_map = {
            t["name"]: set(t["columns"]) for t in real_schema
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not validate schema against client database: {str(e)}")

    # 3. Process Mappings
    updated_count = 0
    created_count = 0
    
    for mapping in mappings:
        table_name = mapping.get("table_name")
        column_name = mapping.get("column_name")
        
        # Validation checks
        if table_name not in schema_map:
            raise HTTPException(status_code=400, detail=f"Table '{table_name}' does not exist in the database.")
        
        if column_name not in schema_map[table_name]:
            raise HTTPException(status_code=400, detail=f"Column '{column_name}' does not exist in table '{table_name}'.")

        # Check existing
        statement = select(SemanticMetadata).where(
            SemanticMetadata.client_id == client_id,
            SemanticMetadata.table_name == table_name,
            SemanticMetadata.column_name == column_name
        )
        result = await session.execute(statement)
        existing = result.scalars().first()
        
        if existing is not None:
            # Update
            existing.label = mapping.get("label", existing.label)
            existing.description = mapping.get("description", existing.description)
            existing.synonyms = mapping.get("synonyms", existing.synonyms)
            existing.data_format = mapping.get("data_format", existing.data_format)
            existing.is_pii = mapping.get("is_pii", existing.is_pii)
            existing.is_default_date = mapping.get("is_default_date", existing.is_default_date)
            session.add(existing)
            updated_count += 1
        else:
            # Create
            new_meta = SemanticMetadata(
                client_id=client_id,
                table_name=table_name,
                column_name=column_name,
                label=mapping.get("label"),
                description=mapping.get("description"),
                synonyms=mapping.get("synonyms", []),
                data_format=mapping.get("data_format", "text"),
                is_pii=mapping.get("is_pii", False),
                is_default_date=mapping.get("is_default_date", False)
            )
            session.add(new_meta)
            created_count += 1

    await session.commit()
    
    log_audit(client_id, "semantic_update", {
        "created": created_count,
        "updated": updated_count,
        "tables_touched": list(set(m["table_name"] for m in mappings))
    })
    
    return {"status": "success", "created": created_count, "updated": updated_count}
