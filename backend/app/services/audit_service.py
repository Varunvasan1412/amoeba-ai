# Amoeba AI v1 FIXED — Do not extend without version bump

import asyncio
# from app.core.database import SessionLocal # REMOVED (Not exists)
from app.models.audit_log import AuditLog
from sqlalchemy.orm import sessionmaker
from app.core.database import engine
from sqlalchemy.ext.asyncio import AsyncSession

# We need a way to log without awaiting if we want true "fire and forget effect" 
# or just await it if we are already in an async path (usually safer for consistency).
# The user req says "Fire-and-forget, Never block execution".
# asyncio.create_task() is the way.

async def _log_entry(client_id: int | None, action: str, meta: dict):
    try:
        # Create a new session for this log to avoid tying to the main request transaction
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            entry = AuditLog(
                client_id=client_id,
                action=action,
                metadata_payload=meta
            )
            session.add(entry)
            await session.commit()
    except Exception as e:
        # SAFETY: Never crash the main app
        print(f"⚠️ Audit Log Failed: {e}")

def log_audit(client_id: int | None, action: str, meta: dict = {}):
    """
    Fire-and-forget audit logger.
    Doesn't block the caller.
    """
    asyncio.create_task(_log_entry(client_id, action, meta))
