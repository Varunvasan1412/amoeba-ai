from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.core.database import get_session
from app.models.ai_settings import AISettings
from app.core.auth_deps import get_current_active_admin
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/ai-settings", dependencies=[Depends(get_current_active_admin)])

class AISettingsUpdate(BaseModel):
    provider: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 2048

@router.get("/{client_id}", response_model=AISettings)
async def get_ai_settings(client_id: int, session: AsyncSession = Depends(get_session)):
    stmt = select(AISettings).where(AISettings.client_id == client_id)
    settings = (await session.execute(stmt)).scalars().first()
    if not settings:
        settings = AISettings(client_id=client_id)
        session.add(settings)
        await session.commit()
        await session.refresh(settings)
    return settings

@router.put("/{client_id}", response_model=AISettings)
async def update_ai_settings(
    client_id: int, 
    payload: AISettingsUpdate, 
    session: AsyncSession = Depends(get_session)
):
    stmt = select(AISettings).where(AISettings.client_id == client_id)
    settings = (await session.execute(stmt)).scalars().first()
    if not settings:
        settings = AISettings(client_id=client_id)
    
    settings.provider = payload.provider
    settings.model = payload.model
    settings.temperature = payload.temperature
    settings.max_tokens = payload.max_tokens
    
    session.add(settings)
    await session.commit()
    await session.refresh(settings)
    return settings
