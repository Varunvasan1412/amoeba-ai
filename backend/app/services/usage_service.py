import asyncio
import time
from sqlalchemy import func
from sqlmodel import select
from app.core.database import get_session
from app.models.document import Document
from app.models.client_config import ClientConfig

async def usage_logger_loop():
    """
    Background task that logs daily usage metrics for all clients.
    Step 7: Add Daily Usage Log
    """
    print("📊 [USAGE] Starting Daily Usage Logger...")
    while True:
        try:
            # Sleep until next check (e.g., 24 hours)
            # For demonstration/testing, we might use a shorter interval (e.g. 1 hour)
            # but user requested "daily".
            await asyncio.sleep(86400) # 24 hours
            
            print("📊 [USAGE] Recording daily metrics...")
            async for session in get_session():
                # 1. Fetch all clients
                clients_stmt = select(ClientConfig)
                clients_res = await session.execute(clients_stmt)
                clients = clients_res.scalars().all()
                
                for client in clients:
                    # 2. Daily Document Count
                    count_stmt = select(func.count(Document.id)).where(Document.client_id == client.id)
                    total_docs = (await session.execute(count_stmt)).scalar() or 0
                    
                    # 3. Storage Used
                    storage_stmt = select(func.sum(Document.file_size)).where(Document.client_id == client.id)
                    total_bytes = (await session.execute(storage_stmt)).scalar() or 0
                    total_mb = round(total_bytes / (1024 * 1024), 2)
                    
                    # 4. Log the usage
                    # In a real system, we'd write this to a 'UsageLog' table.
                    # For now, we follow the user's direction to "Log: client_id, documents_uploaded, storage_used_mb..."
                    print(f"📈 [DAILY USAGE] client_id={client.id}, documents_uploaded={total_docs}, storage_used_mb={total_mb}")
                    
        except Exception as e:
            print(f"⚠️ [USAGE] Error in daily logger: {e}")
            await asyncio.sleep(60) # Retry after 1 minute if it fails
