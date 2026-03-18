from fastapi import APIRouter, Depends, Query, HTTPException
from sqlmodel import select, delete
from typing import List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_session
from app.models.navigation import NavigationItem
from app.tools.navigation import load_client_sitemap
from app.core.auth_deps import get_current_active_admin

router = APIRouter()

@router.get("/sitemap-data")
async def get_full_sitemap(
    client_id: int = Query(...),
    session: AsyncSession = Depends(get_session),
    current_admin: Any = Depends(get_current_active_admin)
):
    """Returns the comprehensive discovered sitemap for a specific client."""
    return await load_client_sitemap(session, client_id)

@router.get("/navigation", response_model=List[NavigationItem])
async def get_navigation_items(
    client_id: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_session),
    current_admin: Any = Depends(get_current_active_admin)
):
    statement = select(NavigationItem)
    if client_id:
        statement = statement.where(NavigationItem.client_id == client_id)
    result = await session.execute(statement.order_by(NavigationItem.order))
    return result.scalars().all()

@router.post("/navigation", response_model=NavigationItem)
async def add_navigation_item(
    item: NavigationItem, 
    session: AsyncSession = Depends(get_session),
    current_admin: Any = Depends(get_current_active_admin)
):
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item

@router.put("/navigation/{item_id}", response_model=NavigationItem)
async def update_navigation_item(
    item_id: int,
    item_update: NavigationItem,
    session: AsyncSession = Depends(get_session),
    current_admin: Any = Depends(get_current_active_admin)
):
    existing_item = await session.get(NavigationItem, item_id)
    if not existing_item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    # Update fields
    data = item_update.model_dump(exclude_unset=True)
    for key, value in data.items():
        if key != "id": # Don't update ID
            setattr(existing_item, key, value)
            
    session.add(existing_item)
    await session.commit()
    await session.refresh(existing_item)
    return existing_item

@router.delete("/navigation/{item_id}")
async def delete_navigation_item(
    item_id: int, 
    session: AsyncSession = Depends(get_session),
    current_admin: Any = Depends(get_current_active_admin)
):
    item = await session.get(NavigationItem, item_id)
    if item:
        await session.delete(item)
        await session.commit()
    return {"status": "success"}
