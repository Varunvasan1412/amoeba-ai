import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import engine
from app.models.audit_log import AuditLog

# Configure logger
logger = logging.getLogger("audit")

async def _persist_audit_log(
    client_id: Optional[int],
    user_id: Optional[str],
    action: str,
    entity: Optional[str],
    table_name: Optional[str],
    record_id: Optional[str],
    source: str,
    status: str,
    details: Dict[str, Any],
    ip_address: Optional[str]
):
    """Internal function to save audit log to DB."""
    try:
        if not entity and table_name:
            entity = table_name.replace("_", " ").title()
            
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            entry = AuditLog(
                client_id=client_id,
                user_id=user_id,
                action=action,
                entity=entity,
                table_name=table_name,
                record_id=record_id,
                source=source,
                status=status,
                details=details,
                ip_address=ip_address
            )
            session.add(entry)
            await session.commit()
    except Exception as e:
        # SAFETY: Never crash the main app if audit logging fails
        logger.warning(f"AUDIT LOG FAILURE: {str(e)}")
        print(f"⚠️ AUDIT LOG FAILURE: {e}")

def log_event(
    client_id: Optional[int] = None,
    user_id: Optional[str] = None,
    action: str = "READ",
    entity: Optional[str] = None,
    table_name: Optional[str] = None,
    record_id: Optional[str] = None,
    source: str = "SYSTEM",
    status: str = "SUCCESS",
    details: Dict[str, Any] = {},
    ip_address: Optional[str] = None
):
    """
    Centralized Audit Logger.
    Non-blocking, safe, and transparent.
    """
    asyncio.create_task(
        _persist_audit_log(
            client_id, user_id, action, entity, table_name, 
            record_id, source, status, details, ip_address
        )
    )

def log_audit(client_id: Optional[int], action: str, details: Dict[str, Any] = {}):
    """Legacy wrapper for log_audit used by existing modules."""
    log_event(client_id=client_id, action=action, details=details, source="SYSTEM")


