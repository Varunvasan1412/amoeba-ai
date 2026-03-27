from fastapi import APIRouter, Depends, HTTPException, Header, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any
from app.core.database import get_session
from app.routers.builder import get_client_id_by_key
from app.services.relationship_service import (
    bulk_update_relationships,
    get_approved_paths,
    approve_join_path
)
from app.models.approved_join_path import ApprovedJoinPath
from app.core.auth_deps import get_current_active_admin
from app.models.user import User

router = APIRouter(
    prefix="/v2/relationships", 
    tags=["v2 Relationships Bulk"],
    dependencies=[Depends(get_current_active_admin)]
)

@router.post("/bulk-update")
async def bulk_update(
    payload: Dict[str, str] = Body(...),
    api_key: str = Header(None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_session)
):
    """
    Perform bulk operations on relationships.
    Actions: 'auto_unlock_safe', 'auto_unlock_heuristics', 'enable_all', 'disable_all'
    """
    client_id = await get_client_id_by_key(api_key, session)
    action = payload.get("action")
    
    valid_actions = ["auto_unlock_safe", "auto_unlock_heuristics", "enable_all", "disable_all", "enable_safe", "disable_heuristic", "purge_all", "refresh_discovery"]
    if action not in valid_actions:
        raise HTTPException(status_code=400, detail=f"Invalid action: {action}")
        
    result = await bulk_update_relationships(session, client_id, action)
    return result

@router.get("/paths", response_model=List[ApprovedJoinPath])
async def list_approved_paths(
    api_key: str = Header(None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_session)
):
    """
    List all approved join paths.
    """
    client_id = await get_client_id_by_key(api_key, session)
    return await get_approved_paths(session, client_id)

@router.post("/paths/approve")
async def approve_path(
    payload: Dict[str, str] = Body(...),
    api_key: str = Header(None, alias="X-API-Key"),
    current_user: User = Depends(get_current_active_admin),
    session: AsyncSession = Depends(get_session)
):
    """
    Approve a specific join path.
    Payload: {"path_signature": "tableA->tableB->tableC"}
    """
    # Note: we still need the api_key for client context in some services, 
    # but we can also get it from client_id if needed.
    # For now, let's assume the frontend sends the X-API-Key header.
    # We can also get it from the header if needed.
    api_key = Header(None, alias="X-API-Key") # This won't work as a line, just for thought.
    
    # Let's get api_key from Header properly
    pass

@router.post("/paths/approve")
async def approve_path(
    payload: Dict[str, str] = Body(...),
    api_key: str = Header(None, alias="X-API-Key"),
    current_user: User = Depends(get_current_active_admin),
    session: AsyncSession = Depends(get_session)
):
    """
    Approve a specific join path.
    Payload: {"path_signature": "tableA->tableB->tableC"}
    """
    client_id = await get_client_id_by_key(api_key, session)
    path_signature = payload.get("path_signature")
    
    if not path_signature:
        raise HTTPException(status_code=400, detail="path_signature required")

    result = await approve_join_path(session, client_id, path_signature, str(current_user.id))
    return result
