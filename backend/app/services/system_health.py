from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.document import Document, DocumentChunk
from typing import Dict, Any

class SystemHealth:
    @staticmethod
    async def get_document_metrics(session: AsyncSession) -> Dict[str, Any]:
        """
        Gathers health metrics for the Document System.
        Step 5: Add Document Health Metrics
        """
        # 1. Total Documents
        stmt_total = select(func.count(Document.id))
        res_total = await session.execute(stmt_total)
        total_docs = res_total.scalar() or 0
        
        # 2. Status Counts
        stmt_ready = select(func.count(Document.id)).where(Document.status == "READY")
        res_ready = await session.execute(stmt_ready)
        ready_docs = res_ready.scalar() or 0
        
        stmt_processing = select(func.count(Document.id)).where(Document.status == "PROCESSING")
        res_processing = await session.execute(stmt_processing)
        processing_docs = res_processing.scalar() or 0
        
        stmt_failed = select(func.count(Document.id)).where(Document.status == "FAILED")
        res_failed = await session.execute(stmt_failed)
        failed_docs = res_failed.scalar() or 0
        
        # 3. Total Chunks
        stmt_chunks = select(func.count(DocumentChunk.id))
        res_chunks = await session.execute(stmt_chunks)
        total_chunks = res_chunks.scalar() or 0
        
        # 4. Avg Ingestion Time
        stmt_avg = select(func.avg(Document.processing_time_ms)).where(Document.processing_time_ms.isnot(None))
        res_avg = await session.execute(stmt_avg)
        avg_time = int(res_avg.scalar() or 0)
        
        return {
            "DOCUMENT SYSTEM": {
                "total_documents": total_docs,
                "documents_ready": ready_docs,
                "documents_processing": processing_docs,
                "documents_failed": failed_docs,
                "total_chunks": total_chunks,
                "avg_ingestion_time_ms": avg_time
            }
        }
