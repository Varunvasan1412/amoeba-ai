from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from app.core.database import get_session
from app.services.admin_validator import AdminValidator
from app.services.admin_autofix import AdminAutofix
from app.core.auth_deps import get_current_active_admin

router = APIRouter(prefix="/admin/validation", tags=["Admin Validation"])

class FixRequest(BaseModel):
    action: str
    item_id: Optional[int] = None
    field: Optional[str] = None
    value: Any = None
    remove_from_ids: Optional[List[int]] = None
    synonym: Optional[str] = None

@router.get("/warnings", response_model=Dict[str, Any])
async def get_validation_warnings(
    client_id: int = Query(...),
    session: AsyncSession = Depends(get_session),
    current_admin: Any = Depends(get_current_active_admin)
):
    """
    Returns a list of configuration warnings and errors for the admin panel.
    """
    try:
        return await AdminValidator.get_configuration_warnings(client_id, session)
    except Exception as e:
        import traceback
        error_msg = f"WARNINGS_CRASH: {str(e)}\n{traceback.format_exc()}"
        print(f"❌ {error_msg}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/term-search")
async def term_search(
    client_id: int = Query(...),
    term: str = Query(...),
    session: AsyncSession = Depends(get_session),
    current_admin: Any = Depends(get_current_active_admin)
):
    """
    Searches for all occurrences of a term across Navigation and Semantic Metadata.
    """
    return await AdminValidator.term_search(client_id, term, session)

@router.post("/apply-fix")
async def apply_configuration_fix(
    fix: FixRequest,
    session: AsyncSession = Depends(get_session),
    current_admin: Any = Depends(get_current_active_admin)
):
    """
    Applies an automated configuration fix.
    """
    success, undo_payload = await AdminAutofix.apply_fix(fix.dict(), session)
    return {
        "status": "success" if success else "failed",
        "undo_fixes": [undo_payload] if undo_payload else []
    }

@router.post("/apply-all")
async def batch_apply_configuration_fixes(
    client_id: int = Query(...),
    session: AsyncSession = Depends(get_session),
    current_admin: Any = Depends(get_current_active_admin)
):
    """
    Applies all valid auto-suggestions for a client.
    """
    return await AdminAutofix.batch_apply_fixes(client_id, session)

@router.post("/run-batch")
async def run_configuration_batch(
    payload: Dict[str, Any],
    session: AsyncSession = Depends(get_session),
    current_admin: Any = Depends(get_current_active_admin)
):
    """
    Applies a batch of fixes provided in the request body (e.g. for Revert).
    """
    fixes = payload.get("fixes", [])
    return await AdminAutofix.run_batch(fixes, session)

