from fastapi import APIRouter, Depends
from sqlmodel import select
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_session
from app.models.navigation import NavigationItem
from app.core.auth_deps import get_current_active_admin

router = APIRouter(dependencies=[Depends(get_current_active_admin)])

@router.get("/", response_model=List[NavigationItem])
async def get_navigation_items(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(NavigationItem).order_by(NavigationItem.order))
    return result.scalars().all()

@router.post("/", response_model=NavigationItem)
async def add_navigation_item(item: NavigationItem, session: AsyncSession = Depends(get_session)):
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item
