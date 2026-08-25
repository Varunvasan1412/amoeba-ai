from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_session
from app.models.document import Document
from app.services.document_service import calculate_storage_usage
from app.services.system_health_service import get_system_health
from app.core.auth_deps import get_current_super_admin
from app.security.permission_guard import require_permission

from app.core.rate_limiter import limiter
from app.core.config import settings

router = APIRouter(prefix="/system", tags=["System Health"])

@router.get("/documents/metrics", dependencies=[Depends(require_permission("access_health"))])
@limiter.limit(settings.RATE_LIMIT_HEALTH)
async def get_document_metrics(request: Request, client_id: int, session: AsyncSession = Depends(get_session)):
    """
    Returns high-level metrics for the document knowledge system.
    Step 4: Add Document Limit Dashboard Metrics
    """
    from app.models.client_config import ClientConfig
    client = await session.get(ClientConfig, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    try:
        # 1. Basic Counts
        total_stmt = select(func.count(Document.id)).where(Document.id.isnot(None)) # Global or client? User request was ambiguous, but Document usually client-scoped.
        # User requested GET /system/documents/metrics, usually admin/system level.
        # But for Amoeba, almost everything is client_id filtered.
        # I'll stick to client_id but support global if client_id is 0?
        # Actually, let's just use client_id as requested.
        
        counts_stmt = select(
            Document.status, 
            func.count(Document.id).label("count"),
            func.sum(Document.chunk_count).label("chunks")
        ).where(Document.client_id == client_id).group_by(Document.status)
        
        counts_res = await session.execute(counts_stmt)
        rows = counts_res.all()
        
        metrics = {
            "total_documents": 0,
            "documents_ready": 0,
            "documents_processing": 0,
            "documents_failed": 0,
            "total_chunks": 0,
            "average_ingestion_time_ms": 0,
            "largest_document_size_mb": 0.0,
            "storage_used_mb": 0.0,
            "storage_limit_mb": client.max_storage_mb,
            "document_count": 0,
            "document_limit": client.max_documents
        }
        
        for row in rows:
            metrics["total_documents"] += row.count
            metrics["total_chunks"] += (row.chunks or 0)
            if row.status == "READY":
                metrics["documents_ready"] = row.count
            elif row.status == "PROCESSING":
                metrics["documents_processing"] = row.count
            elif row.status == "FAILED":
                metrics["documents_failed"] = row.count
                
        # 2. Performance metrics
        perf_stmt = select(
            func.avg(Document.processing_time_ms).label("avg_time"),
            func.max(Document.file_size).label("max_size")
        ).where(Document.client_id == client_id, Document.status == "READY")
        
        perf_res = await session.execute(perf_stmt)
        perf_row = perf_res.fetchone()
        
        if perf_row:
            metrics["average_ingestion_time_ms"] = int(perf_row.avg_time or 0)
            metrics["largest_document_size_mb"] = round(float((perf_row.max_size or 0) / (1024 * 1024)), 2)
            
        # 3. Quota Metrics (Step 4)
        usage_stmt = select(func.sum(Document.file_size)).where(Document.client_id == client_id)
        usage_res = await session.execute(usage_stmt)
        total_bytes = usage_res.scalar() or 0
        metrics["storage_used_mb"] = round(float(total_bytes / (1024 * 1024)), 2)
        metrics["document_count"] = metrics["total_documents"]

        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch metrics: {str(e)}")

@router.get("/documents/storage", dependencies=[Depends(require_permission("view_logs"))])
@limiter.limit(settings.RATE_LIMIT_HEALTH)
async def get_storage_metrics(request: Request, client_id: int, session: AsyncSession = Depends(get_session)):
    """Integration for Step 4"""
    usage = await calculate_storage_usage(client_id, session)
    return usage

@router.get("/health", dependencies=[Depends(require_permission("view_logs"))])
@limiter.limit(settings.RATE_LIMIT_HEALTH)
async def system_health_dashboard(request: Request, client_id: int | None = None, session: AsyncSession = Depends(get_session)):
    """
    Returns real-time aggregated metrics across the database and documents.
    """
    health_data = await get_system_health(session, client_id)
    return health_data

@router.post("/repair", dependencies=[Depends(require_permission("configure_system"))])
@limiter.limit(settings.RATE_LIMIT_REPORT) # Using report limit as it's a heavy operation
async def trigger_system_repair(request: Request, session: AsyncSession = Depends(get_session)):
    """
    Triggers automated repairs for detected infrastructure issues.
    """
    from app.services.system_health_service import perform_system_repair
    repair_results = await perform_system_repair(session)
    
    if not repair_results["success"]:
        raise HTTPException(status_code=500, detail=f"Repair failed: {repair_results['errors']}")
        
    return {
        "status": "success", 
        "message": f"Successfully repaired {len(repair_results['repaired_tables'])} tables.",
        "details": repair_results
    }
