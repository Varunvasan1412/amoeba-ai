from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_session
from app.models.client_config import ClientConfig
from app.core.auth_deps import get_current_active_admin

# Router handles client onboarding status/completion
router = APIRouter(prefix="/clients", dependencies=[Depends(get_current_active_admin)])

@router.get("/{client_id}/onboarding/status")
async def get_onboarding_status(
    client_id: int,
    session: AsyncSession = Depends(get_session)
):
    client = await session.get(ClientConfig, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"onboarding_completed": client.onboarding_completed}

@router.post("/{client_id}/onboarding/complete")
async def complete_onboarding(
    client_id: int,
    session: AsyncSession = Depends(get_session)
):
    client = await session.get(ClientConfig, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    client.onboarding_completed = True
    session.add(client)
    await session.commit()
    return {"status": "success", "message": "Onboarding marked as complete."}
