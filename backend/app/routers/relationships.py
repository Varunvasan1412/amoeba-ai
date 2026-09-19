from fastapi import APIRouter, Depends, HTTPException, Header, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict
from app.core.database import get_session
from app.models.allowed_relationship import AllowedRelationship
from app.services.relationship_service import get_all_relationships, clear_relationship_cache
from app.routers.builder import get_client_id_by_key # Reuse helper
from app.core.auth_deps import get_current_active_admin
from sqlmodel import select
from pydantic import BaseModel

async def validate_activation(session: AsyncSession, client_id: int, rel: AllowedRelationship):
    from app.models.semantic_mapping import SemanticMapping
    # 1. Relationship exists (checked by caller)
    # 2. Technical relationship is valid (assumed if it exists in DB)
    # 3 & 4. Source and target have approved App Concepts
    stmt_parent = select(SemanticMapping).where(
        SemanticMapping.client_id == client_id,
        SemanticMapping.database_table == rel.parent_table
    )
    parent_concept = (await session.execute(stmt_parent)).scalars().first()
    
    stmt_child = select(SemanticMapping).where(
        SemanticMapping.client_id == client_id,
        SemanticMapping.database_table == rel.child_table
    )
    child_concept = (await session.execute(stmt_child)).scalars().first()
    
    if not parent_concept or not child_concept:
        missing = []
        if not parent_concept: missing.append(rel.parent_table)
        if not child_concept: missing.append(rel.child_table)
        raise HTTPException(status_code=400, detail=f"Cannot approve relationship. Missing App Concepts for {', '.join(missing)}.")
        
    # 5. Relationship is not ambiguous
    if rel.approval_status == "ambiguous":
         raise HTTPException(status_code=400, detail="Cannot approve an ambiguous relationship. Please resolve ambiguity first.")
         
    # 6. User has permission (checked by Depends(get_current_active_admin) in router)
    # 7. Explicitly requested (checked by caller via explicit route)
    return True

router = APIRouter(
    prefix="/v2/relationships", 
    tags=["v2 Relationships"],
    dependencies=[Depends(get_current_active_admin)]
)

@router.get("", response_model=List[AllowedRelationship])
async def list_relationships(
    sync: bool = False,
    api_key: str = Header(None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_session)
):
    """
    List all discovered relationships (Enabled & Disabled).
    """
    client_id = await get_client_id_by_key(api_key, session)
    return await get_all_relationships(session, client_id, sync=sync)

@router.get("/health", response_model=dict)
async def get_relationships_health(
    api_key: str = Header(None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_session)
):
    """
    Get a summary of the relationship health (counts of statuses).
    """
    client_id = await get_client_id_by_key(api_key, session)
    from app.services.relationship_service import get_relationship_health_summary
    return await get_relationship_health_summary(session, client_id)

class ManualRelationshipCreate(BaseModel):
    parent_table: str
    parent_column: str
    child_table: str
    child_column: str

@router.post("", response_model=AllowedRelationship)
async def create_manual_relationship(
    payload: ManualRelationshipCreate,
    api_key: str = Header(None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_session)
):
    """
    Manually define a relationship between two tables.
    """
    client_id = await get_client_id_by_key(api_key, session)
    
    # Check if exists
    stmt = select(AllowedRelationship).where(
        AllowedRelationship.client_id == client_id,
        AllowedRelationship.parent_table == payload.parent_table,
        AllowedRelationship.child_table == payload.child_table
    )
    existing = (await session.execute(stmt)).scalars().first()
    if existing:
        return existing
        
    new_rel = AllowedRelationship(
        client_id=client_id,
        parent_table=payload.parent_table,
        parent_column=payload.parent_column,
        child_table=payload.child_table,
        child_column=payload.child_column,
        is_enabled=True,
        risk_level="manual",
        confidence_score=1.0
    )
    session.add(new_rel)
    await session.commit()
    await session.refresh(new_rel)
    
    clear_relationship_cache(client_id)
    return new_rel

class SemanticRelationshipCreate(BaseModel):
    source_table: str
    target_table: str
    relationship_type: str # "belongs_to" or "contains"

@router.post("/semantic", response_model=AllowedRelationship)
async def create_semantic_relationship(
    payload: SemanticRelationshipCreate,
    api_key: str = Header(None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_session)
):
    """
    Creates a business-level relationship and relies on the backend to resolve technical FKs.
    """
    client_id = await get_client_id_by_key(api_key, session)
    from app.services.relationship_service import resolve_semantic_relationship
    
    return await resolve_semantic_relationship(
        session, 
        client_id, 
        payload.source_table, 
        payload.target_table, 
        payload.relationship_type
    )

@router.post("/{rel_id}/toggle")
async def toggle_relationship(
    rel_id: int,
    payload: Dict[str, bool] = Body(...),
    api_key: str = Header(None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_session)
):
    """
    Enable or Disable a relationship.
    """
    client_id = await get_client_id_by_key(api_key, session)
    
    stmt = select(AllowedRelationship).where(
        AllowedRelationship.id == rel_id, 
        AllowedRelationship.client_id == client_id
    )
    rel = (await session.execute(stmt)).scalars().first()
    
    if not rel:
        raise HTTPException(status_code=404, detail="Relationship not found")
        
    is_enabled_payload = payload.get("is_enabled", rel.is_enabled)
    if is_enabled_payload and not rel.is_enabled:
        await validate_activation(session, client_id, rel)
        rel.approval_status = "approved"
        
    rel.is_enabled = is_enabled_payload
    session.add(rel)
    await session.commit()
    await session.refresh(rel)
    
    # Invalidate cache so next builder request gets updated graph
    clear_relationship_cache(client_id)
    
    return {"status": "success", "data": rel}

@router.post("/{rel_id}/restrict")
async def restrict_relationship(
    rel_id: int,
    payload: Dict[str, bool] = Body(...),
    api_key: str = Header(None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_session)
):
    """
    Mark a relationship as Restricted (Admin Only Block).
    """
    client_id = await get_client_id_by_key(api_key, session)
    
    stmt = select(AllowedRelationship).where(
        AllowedRelationship.id == rel_id, 
        AllowedRelationship.client_id == client_id
    )
    rel = (await session.execute(stmt)).scalars().first()
    
    if not rel:
        raise HTTPException(status_code=404, detail="Relationship not found")
        
    rel.is_restricted = payload.get("is_restricted", rel.is_restricted)
    session.add(rel)
    await session.commit()
    await session.refresh(rel)
    
    clear_relationship_cache(client_id)
    
    return {"status": "success", "data": rel}

@router.delete("/{rel_id}")
async def delete_relationship(
    rel_id: int,
    api_key: str = Header(None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_session)
):
    """
    Permanently remove a relationship.
    """
    client_id = await get_client_id_by_key(api_key, session)
    
    stmt = select(AllowedRelationship).where(
        AllowedRelationship.id == rel_id, 
        AllowedRelationship.client_id == client_id
    )
    rel = (await session.execute(stmt)).scalars().first()
    
    if not rel:
        raise HTTPException(status_code=404, detail="Relationship not found")
        
    await session.delete(rel)
    await session.commit()
    
    clear_relationship_cache(client_id)
    return {"status": "success", "message": "Relationship deleted"}

class ColumnSelectionRequest(BaseModel):
    columns: List[str]

@router.post("/{rel_id}/columns")
async def update_relationship_columns(
    rel_id: int,
    payload: ColumnSelectionRequest,
    api_key: str = Header(None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_session)
):
    """
    Save which columns from the joined table should be included.
    """
    client_id = await get_client_id_by_key(api_key, session)
    
    stmt = select(AllowedRelationship).where(
        AllowedRelationship.id == rel_id, 
        AllowedRelationship.client_id == client_id
    )
    rel = (await session.execute(stmt)).scalars().first()
    
    if not rel:
        raise HTTPException(status_code=404, detail="Relationship not found")
        
    rel.selected_columns = payload.columns
    session.add(rel)
    await session.commit()
    await session.refresh(rel)
    
    clear_relationship_cache(client_id)
    
    return {"status": "success", "data": rel}

class RelationshipStatusUpdate(BaseModel):
    status: str # "discovered", "needs_review", "ambiguous", "approved", "rejected"

@router.put("/{rel_id}/status")
async def update_relationship_status(
    rel_id: int,
    payload: RelationshipStatusUpdate,
    api_key: str = Header(None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_session)
):
    """
    Update the lifecycle status of a relationship and enforce invariants.
    """
    client_id = await get_client_id_by_key(api_key, session)
    
    stmt = select(AllowedRelationship).where(
        AllowedRelationship.id == rel_id, 
        AllowedRelationship.client_id == client_id
    )
    rel = (await session.execute(stmt)).scalars().first()
    
    if not rel:
        raise HTTPException(status_code=404, detail="Relationship not found")
        
    valid_statuses = {"discovered", "needs_review", "ambiguous", "approved", "rejected"}
    if payload.status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Invalid status")
        
    rel.approval_status = payload.status
    
    # Enforce Invariants
    if payload.status == "approved":
        await validate_activation(session, client_id, rel)
        rel.is_enabled = True
    else:
        rel.is_enabled = False
        
    session.add(rel)
    await session.commit()
    await session.refresh(rel)
    
    clear_relationship_cache(client_id)
    
    return {"status": "success", "data": rel}
