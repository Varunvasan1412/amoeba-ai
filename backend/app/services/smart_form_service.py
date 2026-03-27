from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import create_engine, inspect, text
from sqlmodel import select
from app.models.client_config import ClientConfig
from app.models.field_metadata import FieldMetadata
from app.services.schema_presenter import SchemaPresenter
from sqlalchemy import create_engine, inspect, text, func
from app.models.allowed_relationship import AllowedRelationship
from app.services.field_metadata_service import get_field_options
from app.models.ui_schema import UISchemaCache
from app.models.semantic_metadata import SemanticMetadata

class SmartFormService:
    @staticmethod
    async def generate_form(client_id: int, table_name: str, session: AsyncSession, module: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate a full UI-ready form structure using FieldMetadata.
        """
        client_config = await session.get(ClientConfig, client_id)
        if not client_config:
            return {"error": "Client not found"}

        # Format a friendly table name if module is present
        from app.services.entity_selector import EntitySelector
        raw_label = EntitySelector.format_table_label(table_name)
        if module:
            display_title = f"{module} {raw_label}"
        else:
            display_title = raw_label

        # 1. Load Field Metadata for this table (Case-Insensitive match)
        stmt = select(FieldMetadata).where(
            FieldMetadata.client_id == client_id,
            func.lower(FieldMetadata.table_name) == table_name.lower()
        )
        result = await session.execute(stmt)
        meta_list = result.scalars().all()
        meta_map = {m.column_name.lower(): m for m in meta_list}

        # 2. Get Governance Links (Allowed Relationships) - Robust Check
        rel_stmt = select(AllowedRelationship).where(
            AllowedRelationship.client_id == client_id,
            (
                (func.lower(AllowedRelationship.parent_table) == table_name.lower()) |
                (func.lower(AllowedRelationship.child_table) == table_name.lower())
            ),
            AllowedRelationship.is_enabled == True
        )
        rel_result = await session.execute(rel_stmt)
        rel_list = rel_result.scalars().all()
        
        # Build map: column -> relationship
        rel_map = {}
        for r in rel_list:
            if r.parent_table.lower() == table_name.lower():
                rel_map[r.parent_column.lower()] = ("parent", r)
            else:
                rel_map[r.child_column.lower()] = ("child", r)

        # 3. Get Friendly Schema (Base fields)
        friendly_fields = await SchemaPresenter.get_friendly_schema(client_id, table_name, session)

        # 4. Load UI Schema Cache (Learned from DOM)
        ui_stmt = select(UISchemaCache).where(
            UISchemaCache.client_id == client_id
        )
        ui_res = await session.execute(ui_stmt)
        ui_map = {u.field_name.lower(): u for u in ui_res.scalars().all()}

        # 5. Load Semantic Metadata (Business Labels)
        sem_stmt = select(SemanticMetadata).where(
            SemanticMetadata.client_id == client_id,
            func.lower(SemanticMetadata.table_name) == table_name.lower()
        )
        sem_result = await session.execute(sem_stmt)
        sem_map = {s.column_name.lower(): s for s in sem_result.scalars().all() if s.column_name}

        form_fields = []
        seen_cols = set()

        for field in friendly_fields:
            col_name = field["field"]
            col_lower = col_name.lower()
            seen_cols.add(col_lower)

            # --- APPLY PRIORITY (Bottom-Up: Discovery -> Semantic -> Explicit UX) ---

            # Priority 3: UI Cache (Learned from DOM) - The "Discovered Default"
            if col_lower in ui_map:
                ui = ui_map[col_lower]
                field["label"] = ui.label
                field["type"] = ui.field_type

            # Priority 2: Semantic Metadata - The "Business Definition"
            if col_lower in sem_map:
                sem = sem_map[col_lower]
                field["label"] = sem.label  # Overwrite discovered label with business label
                # Synonyms and data format are usually for AI but can be used here if needed

            # Priority 1: Field Metadata - The "Admin Override / UX Integrity"
            if col_lower in meta_map:
                meta = meta_map[col_lower]
                
                # Check Visibility - Skip field if hidden by admin
                if not meta.is_visible:
                    continue

                # Field Metadata is explicit. It wins over everything.
                if meta.label:
                    field["label"] = meta.label
                    
                field["type"] = meta.input_type
                field["storage_type"] = meta.storage_type
                field["required"] = meta.required
                field["readonly"] = meta.readonly

                if meta.input_type == "dropdown":
                    field["options"] = await get_field_options(client_id, meta, session)

            # Strategy C: If it's a dropdown but no options yet, try to auto-find via Governance
            if field.get("type") == "dropdown" and not field.get("options"):
                if col_lower in rel_map:
                    direction, rel = rel_map[col_lower]
                    
                    # Extract source info based on direction
                    source_table = rel.child_table if direction == "parent" else rel.parent_table
                    source_column = rel.child_column if direction == "parent" else rel.parent_column

                    # Create a "virtual" metadata object for get_field_options
                    virtual_meta = FieldMetadata(
                        client_id=client_id,
                        table_name=table_name,
                        column_name=col_name,
                        label=field["label"],
                        input_type="dropdown",
                        storage_type="integer", 
                        data_source_table=source_table,
                        value_column=source_column,
                        display_column=rel.selected_columns[0] if rel.selected_columns else source_column
                    )
                    field["storage_type"] = "integer"
                    field["options"] = await get_field_options(client_id, virtual_meta, session)
            
            # Ensure storage_type exists even if no metadata found (default from SchemaPresenter or string)
            if "storage_type" not in field:
                field["storage_type"] = "string" # Default fallback

            form_fields.append(field)

        # 5. Backup Strategy: Add "UI-Only" fields if DB inspection returned nothing or is partial
        if not form_fields:
            for f_name, ui in ui_map.items():
                form_fields.append({
                    "field": ui.field_name,
                    "label": ui.label,
                    "type": ui.field_type,
                    "required": False,
                    "storage_type": "string"
                })

        print(f"🧠 [SMART FORM] Generated {len(form_fields)} fields for {table_name} (Merged Sources)")

        return {
            "table_name": table_name,
            "label": display_title,
            "display_title": display_title, # Keep for legacy compat
            "module": module,
            "fields": form_fields
        }
