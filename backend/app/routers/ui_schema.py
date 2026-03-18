import re
from fastapi import APIRouter, Depends, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from app.core.database import get_session
from app.models.semantic_metadata import SemanticMetadata
from app.models.ui_schema import UISchemaCache
from app.models.navigation import NavigationItem
from app.services.audit_service import log_audit

router = APIRouter()

class UIField(BaseModel):
    label: str
    name: str # The technical name/id from DOM
    type: str
    required: bool = False

class UISchemaPayload(BaseModel):
    client_id: int
    page_path: str
    fields: List[UIField]

def normalize_name(name: str) -> str:
    """Normalizes names to snake_case and strips common UI prefixes."""
    # 1. Remove ASP.NET style prefixes or long paths
    if "$" in name: name = name.split("$")[-1]
    
    # 2. Handle camelCase
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
    clean = s2.replace("-", "_").strip("_")
    
    # 3. Strip common UI prefixes
    prefixes = ["txt_", "ddl_", "btn_", "lbl_", "id_", "select_", "input_"]
    for p in prefixes:
        if clean.startswith(p):
            clean = clean[len(p):]
            break
    
    # Handle specific common cases
    if clean == "contactnumber": return "contact_number"
    if clean == "contactperson": return "contact_person"
    
    return clean

@router.post("")
@router.post("/")
async def save_ui_schema(
    payload: UISchemaPayload,
    session: AsyncSession = Depends(get_session)
):
    """
    Saves UI labels discovered from the DOM.
    Matches them to database columns based on normalized names.
    """
    try:
        # 1. Resolve Table Name from Page Path
        nav_stmt = select(NavigationItem).where(NavigationItem.client_id == payload.client_id)
        nav_res = await session.execute(nav_stmt)
        nav_items = nav_res.scalars().all()
        
        table_name = None
        for item in nav_items:
            if payload.page_path.endswith(item.path):
                table_name = item.table_name
                break
        
        if not table_name:
            # Fallback: if we can't find a direct path match, try to infer from last part of URL
            parts = [p for p in payload.page_path.split("/") if p]
            if parts:
                possible_table = parts[-1]
                # Check if this table name exists in any nav item
                match = next((item.table_name for item in nav_items if item.table_name and normalize_name(item.table_name) == normalize_name(possible_table)), None)
                if match: table_name = match

        print(f"🧠 [UI LEARNING] Scanned {len(payload.fields)} fields for table: {table_name or 'Unknown'}")

        for field in payload.fields:
            # 2. Cache UI Schema (idempotent)
            cache_stmt = select(UISchemaCache).where(
                UISchemaCache.client_id == payload.client_id,
                UISchemaCache.page_path == payload.page_path,
                UISchemaCache.field_name == field.name
            )
            cache_res = await session.execute(cache_stmt)
            existing_cache = cache_res.scalars().first()
            
            if not existing_cache:
                new_cache = UISchemaCache(
                    client_id=payload.client_id,
                    page_path=payload.page_path,
                    field_name=field.name,
                    label=field.label,
                    field_type=field.type
                )
                session.add(new_cache)
            else:
                existing_cache.label = field.label
                existing_cache.field_type = field.type

            # 3. Update Semantic Metadata
            if table_name:
                norm_ui_name = normalize_name(field.name)
                sem_stmt = select(SemanticMetadata).where(
                    SemanticMetadata.client_id == payload.client_id,
                    SemanticMetadata.table_name == table_name,
                    SemanticMetadata.column_name == norm_ui_name
                )
                sem_res = await session.execute(sem_stmt)
                sem = sem_res.scalars().first()
                
                if sem:
                    # Update label if it hasn't been manually specialized
                    if sem.label.lower() == sem.column_name.lower().replace("_", " "):
                        sem.label = field.label
                else:
                    # Create new semantic mapping
                    new_sem = SemanticMetadata(
                        client_id=payload.client_id,
                        table_name=table_name,
                        column_name=norm_ui_name,
                        label=field.label,
                        data_format=field.type if field.type in ["date", "currency", "text"] else "text"
                    )
                    session.add(new_sem)

        await session.commit()
        return {"status": "success", "table_resolved": table_name}
        
    except Exception as e:
        await session.rollback()
        print(f"❌ [UI LEARNING] Error: {e}")
        return {"status": "error", "message": str(e)}
