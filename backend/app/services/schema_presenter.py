import re
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import create_engine, inspect
from sqlmodel import select
from app.models.semantic_metadata import SemanticMetadata
from app.models.client_config import ClientConfig

SYSTEM_FIELDS = [
    "id", "created_at", "updated_at", "deleted_at", 
    "deleted_flag", "tenant_id", "uuid", "is_deleted"
]

class SchemaPresenter:
    @staticmethod
    async def get_friendly_schema(client_id: int, table_name: str, session: AsyncSession) -> List[Dict[str, Any]]:
        """
        Converts raw database schema into user-friendly form schema.
        """
        client_config = await session.get(ClientConfig, client_id)
        if not client_config:
            return []

        # 1. Fetch RAW columns from DB
        engine = create_engine(client_config.db_connection_url)
        inspector = inspect(engine)
        try:
            raw_columns = inspector.get_columns(table_name)
        except Exception as e:
            print(f"⚠️ SchemaPresenter Error for table '{table_name}': {e}")
            return []
        
        # 2. Fetch Semantic Metadata
        statement = select(SemanticMetadata).where(
            SemanticMetadata.client_id == client_id,
            SemanticMetadata.table_name == table_name
        )
        result = await session.execute(statement)
        semantics = {sem.column_name: sem for sem in result.scalars().all()}

        friendly_schema = []

        for col in raw_columns:
            name = col["name"]
            
            # 1. Hide system fields
            if name.lower() in SYSTEM_FIELDS:
                continue
            
            # 2. Apply semantic labels
            sem = semantics.get(name)
            label = sem.label if sem else SchemaPresenter.format_column_label(name)
            data_format = sem.data_format if sem else SchemaPresenter.detect_field_type(name, col["type"])

            friendly_schema.append({
                "field": name,
                "label": label,
                "type": data_format,
                "required": not col.get("nullable", True)
            })

        return friendly_schema

    @staticmethod
    def format_column_label(column_name: str) -> str:
        """Converts snake_case to Title Case."""
        return column_name.replace("_", " ").title()

    @staticmethod
    def detect_field_type(name: str, sa_type: Any) -> str:
        """Heuristic field type detection."""
        name_lower = name.lower()
        
        if "_date" in name_lower:
            return "date"
        if "_amount" in name_lower or "_price" in name_lower or "total_" in name_lower:
            return "currency"
        if "_id" in name_lower:
            return "dropdown" # Foreign key hint
        
        # Basic SQL type mapping
        type_str = str(sa_type).upper()
        if "INT" in type_str:
            return "number"
        if "DATE" in type_str or "TIMESTAMP" in type_str:
            return "date"
        if "TEXT" in type_str or "VARCHAR" in type_str:
            if "DESCRIPTION" in name_lower or "REMARKS" in name_lower:
                return "textarea"
            return "text"
        
        return "text"
