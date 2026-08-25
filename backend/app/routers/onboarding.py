from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_session
from app.models.client_config import ClientConfig
from app.security.permission_guard import require_permission

# Router handles client onboarding status/completion
router = APIRouter(tags=["Onboarding Status"])

@router.get("/clients/{client_id}/onboarding/status", dependencies=[Depends(require_permission("configure_system"))])
async def get_onboarding_status(
    client_id: int,
    session: AsyncSession = Depends(get_session)
):
    client = await session.get(ClientConfig, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"onboarding_completed": client.onboarding_completed}

@router.post("/clients/{client_id}/onboarding/complete", dependencies=[Depends(require_permission("configure_system"))])
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
