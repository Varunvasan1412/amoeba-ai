import os
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.document import Document, DocumentChunk
from app.core.database import async_session

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")

async def run_cleanup():
    """
    Main cleanup task. Steps 7 & 8 from the request.
    Handles orphaned chunks, temp files, and processing timeouts.
    """
    print("🧹 [CLEANUP] Starting background maintenance...")
    async with async_session() as session:
        try:
            # 1. ORPHAN CLEANUP (Step 7)
            # Find chunks whose document_id does not exist in Document table
            # SQLModel/SQLAlchemy doesn't have an easy "orphan" check in one statement without subquery
            # We'll use a direct DELETE with a subquery
            from sqlalchemy import not_
            
            subquery = select(Document.id)
            orphan_stmt = delete(DocumentChunk).where(not_(DocumentChunk.document_id.in_(subquery)))
            result = await session.execute(orphan_stmt)
            print(f"✅ [CLEANUP] Removed {result.rowcount} orphaned chunks.")

            # 2. STATUS TIMEOUT PROTECTION (Step 8)
            # Mark documents in PROCESSING for > 10 minutes as FAILED
            ten_mins_ago = datetime.utcnow() - timedelta(minutes=10)
            timeout_stmt = select(Document).where(
                Document.status == "PROCESSING",
                Document.upload_time < ten_mins_ago
            )
            timed_out_res = await session.execute(timeout_stmt)
            timed_out_docs = timed_out_res.scalars().all()
            
            for doc in timed_out_docs:
                doc.status = "FAILED"
                doc.error_message = "Processing timeout (stuck in PROCESSING for >10 mins)."
                print(f"⚠️ [CLEANUP] Processing timeout for: {doc.filename}")
            
            if timed_out_docs:
                await session.commit()
                print(f"✅ [CLEANUP] Fixed {len(timed_out_docs)} hung documents.")

            # 3. TEMP FILE CLEANUP (Step 7)
            # Remove files in uploads that are not in Document table
            # (Requires listing local files and comparing with DB)
            doc_stmt = select(Document.id, Document.filename)
            res = await session.execute(doc_stmt)
            active_files = set()
            for doc_id, filename in res.all():
                active_files.add(f"{doc_id}_{filename}")
            
            if os.path.exists(UPLOAD_DIR):
                files_on_disk = os.listdir(UPLOAD_DIR)
                removed_count = 0
                for f in files_on_disk:
                    if f not in active_files:
                        try:
                            os.remove(os.path.join(UPLOAD_DIR, f))
                            removed_count += 1
                        except Exception as e:
                            print(f"⚠️ [CLEANUP] Failed to remove {f}: {e}")
                print(f"✅ [CLEANUP] Removed {removed_count} temporary/orphaned files from disk.")

            print("✨ [CLEANUP] Completed successfully.")
            
        except Exception as e:
            print(f"❌ [CLEANUP] Error during maintenance: {e}")
            await session.rollback()

async def cleanup_loop():
    """Infinite loop for the background worker (runs every 24h as requested)."""
    while True:
        await run_cleanup()
        # Sleep for 24 hours
        await asyncio.sleep(24 * 3600)
