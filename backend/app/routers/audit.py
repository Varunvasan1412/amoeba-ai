import csv
import io
from typing import List, Optional, Any
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException, Response
from sqlmodel import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_session
from app.models.audit_log import AuditLog
from app.models.user import User
from app.core.auth_deps import get_current_super_admin
from app.security.permission_guard import require_permission, get_current_user

router = APIRouter(prefix="/audit", tags=["Audit Log"])

@router.get("/logs", dependencies=[Depends(get_current_super_admin)])
async def get_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    client_id: Optional[int] = Query(None),
    user_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    entity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    sort_by: str = Query("timestamp"),
    sort_order: str = Query("desc"),
    session: AsyncSession = Depends(get_session),
):

    """Returns paginated audit logs with filtering."""
    statement = select(AuditLog)
    filters = []
    
    if client_id:
        filters.append(AuditLog.client_id == client_id)
    if user_id:
        filters.append(AuditLog.user_id == user_id)
    if action:
        filters.append(AuditLog.action == action)
    if entity:
        filters.append(AuditLog.entity == entity)
    if status:
        filters.append(AuditLog.status == status)
    if date_from:
        filters.append(AuditLog.timestamp >= date_from)
    if date_to:
        filters.append(AuditLog.timestamp <= date_to)
        
    if filters:
        statement = statement.where(and_(*filters))
        
    # Count total
    count_statement = select(func.count()).select_from(statement.subquery())
    total_records = (await session.execute(count_statement)).scalar() or 0
    
    # Sorting
    if hasattr(AuditLog, sort_by):
        sort_attr = getattr(AuditLog, sort_by)
    else:
        sort_attr = AuditLog.timestamp

    if sort_order.lower() == "asc":
        statement = statement.order_by(sort_attr.asc())
    else:
        statement = statement.order_by(sort_attr.desc())

        
    # Final Pagination
    statement = statement.offset((page - 1) * page_size).limit(page_size)
    results = await session.execute(statement)
    records = results.scalars().all()

    
    return {
        "records": records,
        "page": page,
        "page_size": page_size,
        "total_records": total_records
    }

@router.get("/export", dependencies=[Depends(get_current_super_admin)])
async def export_audit_logs(
    client_id: Optional[int] = Query(None),
    user_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    entity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """Exports audit logs as CSV."""
    statement = select(AuditLog)
    filters = []
    
    if client_id:
        filters.append(AuditLog.client_id == client_id)
    if user_id:
        filters.append(AuditLog.user_id == user_id)
    if action:
        filters.append(AuditLog.action == action)
    if entity:
        filters.append(AuditLog.entity == entity)
    if status:
        filters.append(AuditLog.status == status)
    if date_from:
        filters.append(AuditLog.timestamp >= date_from)
    if date_to:
        filters.append(AuditLog.timestamp <= date_to)
        
    if filters:
        statement = statement.where(and_(*filters))
        
    statement = statement.order_by(AuditLog.timestamp.desc()).limit(10000) # Safety limit for export
    results = await session.execute(statement)
    records = results.scalars().all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Timestamp", "Client ID", "User ID", "Action", "Entity", "Table", "Record ID", "Source", "Status", "Details", "IP Address"])
    
    for log in records:
        writer.writerow([
            str(log.id),
            log.timestamp.isoformat(),
            log.client_id,
            log.user_id,
            log.action,
            log.entity,
            log.table_name,
            log.record_id,
            log.source,
            log.status,
            str(log.details),
            log.ip_address
        ])
        
    csv_data = output.getvalue()
    filename = f"audit_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.delete("/clear", dependencies=[Depends(require_permission("delete_system_data"))])
async def clear_audit_logs(
    session: AsyncSession = Depends(get_session)
):
    """Deletes all audit logs. Admin only."""
    from sqlalchemy import delete
    await session.execute(delete(AuditLog))
    await session.commit()
    return {"message": "Audit history cleared successfully."}

@router.get("/login")
async def get_login_audits(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    query: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Returns paginated login audits with filtering and tenant isolation."""
    from app.models.login_audit import LoginAudit
    from sqlalchemy import or_
    from app.services.rbac_service import get_user_permissions

    # Check permission or admin status
    permissions = await get_user_permissions(current_user.id)
    if not current_user.is_admin and "view_logs" not in permissions:
        raise HTTPException(status_code=403, detail="Missing required permission: view_logs")

    statement = select(LoginAudit)
    filters = []
    
    # 1. Multi-tenant Isolation
    if not current_user.is_platform_user:
        filters.append(LoginAudit.client_id == current_user.client_id)
    
    # 2. Search Query (User/Email or Company Code)
    if query:
        filters.append(or_(
            LoginAudit.email.contains(query),
            LoginAudit.company_code.contains(query)
        ))
        
    if status:
        filters.append(LoginAudit.status == status)
    if date_from:
        filters.append(LoginAudit.created_at >= date_from)
    if date_to:
        filters.append(LoginAudit.created_at <= date_to)
        
    if filters:
        statement = statement.where(and_(*filters))
        
    # Count total
    count_statement = select(func.count()).select_from(statement.subquery())
    total_records = (await session.execute(count_statement)).scalar() or 0
    
    # Final Pagination & Sorting
    statement = statement.order_by(LoginAudit.created_at.desc())
    statement = statement.offset((page - 1) * page_size).limit(page_size)
    results = await session.execute(statement)
    records = results.scalars().all()
    
    return {
        "records": records,
        "page": page,
        "page_size": page_size,
        "total_records": total_records
    }

purge_router = APIRouter(prefix="/audit", tags=["Audit Log Purge"])

@purge_router.post("/purge-login-audits")
async def purge_login_audits(
    days: int = Query(30, ge=0),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Deletes login audit records older than X days. Isolated by tenant for client admins."""
    from datetime import timedelta, datetime, timezone
    from sqlalchemy import delete, and_
    from app.models.login_audit import LoginAudit
    from app.services.rbac_service import get_user_permissions
    
    # 1. Authorization Check
    permissions = await get_user_permissions(current_user.id)
    if not current_user.is_admin and "view_logs" not in permissions:
        raise HTTPException(status_code=403, detail="Not authorized to purge logs.")
    
    # 2. Calculate Cutoff
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # 3. Build Filters (Age + Tenant)
    filters = [LoginAudit.created_at < cutoff_date]
    
    if not current_user.is_platform_user:
        filters.append(LoginAudit.client_id == current_user.client_id)
        
    statement = delete(LoginAudit).where(and_(*filters))
    result = await session.execute(statement)
    await session.commit()
    
    return {
        "message": f"Successfully purged logs older than {days} days.",
        "deleted_count": result.rowcount
    }
