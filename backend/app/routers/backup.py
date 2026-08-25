from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Dict, Any
from app.core.database import get_session, async_session
from app.models.backup_settings import BackupSettings
from app.models.backup_validation import BackupValidationLog
from app.services import backup_service, backup_validation_service
from app.core.scheduler import scheduler, CronTrigger
from app.core.auth_deps import get_current_super_admin
from app.security.permission_guard import require_permission

router = APIRouter(prefix="/system", tags=["Backups"], dependencies=[Depends(get_current_super_admin)])

@router.get("/backups")
async def get_backups():
    """
    Returns list of backup files with validation status.
    """
    backups = await backup_service.list_backups()
    
    # Enrich with validation logs
    async with async_session() as session:
        for bk in backups:
            # Find the latest validation log for this backup
            stmt = select(BackupValidationLog).where(
                BackupValidationLog.backup_file == bk["file_name"]
            ).order_by(desc(BackupValidationLog.tested_at)).limit(1)
            
            res = await session.execute(stmt)
            log = res.scalar_one_or_none()
            
            if log:
                bk["is_validated"] = True
                bk["last_tested_at"] = log.tested_at.isoformat()
                bk["validation_status"] = log.status
                bk["validation_error"] = log.error_message
            else:
                bk["is_validated"] = False
                bk["validation_status"] = "NOT TESTED"

    return backups

@router.post("/backup", dependencies=[Depends(require_permission("create_record"))])
async def trigger_manual_backup():
    """
    Triggers an immediate database dump.
    """
    result = await backup_service.create_backup()
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", "Backup failed"))
    return result

@router.post("/restore", dependencies=[Depends(require_permission("restore_backup"))])
async def restore_db(payload: Dict[str, Any] = Body(...)):
    """
    Restores the database from a backup file.
    """
    filename = payload.get("backup_file_name")
    confirm = payload.get("confirm", False)
    
    if not filename:
        raise HTTPException(status_code=400, detail="Missing backup_file_name")
    if not confirm:
        raise HTTPException(status_code=400, detail="Restore confirmation required")

    result = await backup_service.restore_backup(filename, confirm)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", "Restore failed"))
    return result

@router.delete("/backup/{filename}", dependencies=[Depends(require_permission("delete_system_data"))])
async def delete_backup_file(filename: str):
    """
    Delete a backup file.
    """
    success = await backup_service.delete_backup(filename)
    if not success:
        raise HTTPException(status_code=404, detail="File not found")
    return {"status": "success"}

@router.get("/backup/{filename}/inspect", dependencies=[Depends(require_permission("view_logs"))])
async def inspect_backup_file(filename: str):
    """
    Inspects the contents of a backup file.
    """
    result = await backup_service.inspect_backup(filename)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", "Inspection failed"))
    return result

@router.post("/backup/{filename}/validate", dependencies=[Depends(require_permission("update_record"))])
async def validate_backup_file(filename: str):
    """
    Manually triggers a validation test for a backup file.
    """
    result = await backup_validation_service.test_restore(filename)
    if not result["success"]:
        return result # Return failure info safely instead of raising 500 if it was a PASS/FAIL logic
    return result

@router.get("/backup/schedule")
async def get_backup_schedule(session: AsyncSession = Depends(get_session)):
    """
    Returns current backup schedule settings.
    """
    stmt = select(BackupSettings).limit(1)
    res = await session.execute(stmt)
    settings = res.scalar_one_or_none()
    
    if not settings:
        settings = BackupSettings()
        session.add(settings)
        await session.commit()
        await session.refresh(settings)
    
    return settings

@router.put("/backup/schedule", dependencies=[Depends(require_permission("configure_system"))])
async def update_backup_schedule(
    hour: int = Body(...), 
    minute: int = Body(...),
    session: AsyncSession = Depends(get_session)
):
    """
    Updates the backup schedule and reschedules the background job.
    """
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise HTTPException(status_code=400, detail="Invalid time format")

    stmt = select(BackupSettings).limit(1)
    res = await session.execute(stmt)
    settings = res.scalar_one_or_none()
    
    if not settings:
        settings = BackupSettings()
    
    settings.schedule_hour = hour
    settings.schedule_minute = minute
    session.add(settings)
    await session.commit()
    
    # Reschedule the job
    try:
        from app.services.backup_service import create_backup
        
        # Helper function to run the async task
        def run_backup():
            import asyncio
            asyncio.run(create_backup())

        job_id = "daily_backup"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
            
        scheduler.add_job(
            run_backup,
            CronTrigger(hour=hour, minute=minute),
            id=job_id,
            replace_existing=True
        )
        
        return {"status": "success", "next_run": f"{hour:02d}:{minute:02d}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rescheduling failed: {str(e)}")
