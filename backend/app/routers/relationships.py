from fastapi import APIRouter, Depends, HTTPException, Header, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict
from app.core.database import get_session
from app.models.allowed_relationship import AllowedRelationship
from app.services.relationship_service import get_all_relationships, clear_relationship_cache
from app.routers.builder import get_client_id_by_key # Reuse helper
from app.core.auth_deps import get_current_active_admin
from sqlmodel import select

router = APIRouter(
    prefix="/v2/relationships", 
    tags=["v2 Relationships"],
    dependencies=[Depends(get_current_active_admin)]
)

@router.get("", response_model=List[AllowedRelationship])
async def list_relationships(
    api_key: str = Header(None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_session)
):
    """
    List all discovered relationships (Enabled & Disabled).
    """
    client_id = await get_client_id_by_key(api_key, session)
    # This ensures sync runs if not already
    return await get_all_relationships(session, client_id)

from pydantic import BaseModel

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
        
    rel.is_enabled = payload.get("is_enabled", rel.is_enabled)
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
