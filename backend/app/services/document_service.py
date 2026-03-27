from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.document import Document

async def calculate_storage_usage(client_id: int, session: AsyncSession):
    """
    Calculates storage usage metrics for a specific client.
    Returns MB, count, and average size.
    """
    stmt = select(
        func.sum(Document.file_size).label("total_bytes"),
        func.count(Document.id).label("doc_count"),
        func.avg(Document.file_size).label("avg_bytes")
    ).where(Document.client_id == client_id)
    
    result = await session.execute(stmt)
    row = result.fetchone()
    
    if not row or row.doc_count == 0:
        return {
            "total_storage_mb": 0.0,
            "document_count": 0,
            "average_document_size_kb": 0.0
        }
        
    total_bytes = row.total_bytes or 0
    doc_count = row.doc_count or 0
    avg_bytes = row.avg_bytes or 0
    
    return {
        "total_storage_mb": round(total_bytes / (1024 * 1024), 2),
        "document_count": doc_count,
        "average_document_size_kb": round(avg_bytes / 1024, 2)
    }
