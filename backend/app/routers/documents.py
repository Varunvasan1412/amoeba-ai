import os
import asyncio
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, Depends, Query
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_session
from app.models.document import Document
from app.services.document_ingestion_service import ingest_document

router = APIRouter(prefix="/documents", tags=["Documents"])

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".csv", ".xlsx"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    passed_client_id: Optional[int] = Form(None, alias="client_id"),
    api_key: Optional[str] = Form(None),
    session: AsyncSession = Depends(get_session)
):
    """Handles document upload with safety checks and triggers ingestion pipeline."""
    
    # 0) Resolve Client Config & ID
    resolved_client_id = passed_client_id
    client_config = None
    
    if api_key:
        from app.models.client_config import ClientConfig
        res = await session.execute(select(ClientConfig).where(ClientConfig.api_key == api_key))
        client_config = res.scalars().first()
        if not client_config:
            raise HTTPException(status_code=403, detail="Invalid API Key for upload.")
        resolved_client_id = client_config.id
    elif resolved_client_id:
        from app.models.client_config import ClientConfig
        client_config = await session.get(ClientConfig, resolved_client_id)
        if not client_config:
            raise HTTPException(status_code=404, detail="Client configuration not found.")
    else:
        raise HTTPException(status_code=400, detail="client_id or api_key is required for upload.")

    # 1) Safety Checks
    if not file.filename:
        raise HTTPException(status_code=400, detail="It looks like the filename is empty. Please check your file and try again!")
    
    # Check size by reading (For quota validation)
    file_bytes = await file.read()
    file_size = len(file_bytes)
    if file_size == 0:
        raise HTTPException(status_code=400, detail="This file appears to be empty. Please upload a file with content!")

    # 2) Quota Validation (Step 2 & 6)
    max_size_bytes = client_config.max_document_size_mb * 1024 * 1024
    if file_size > max_size_bytes:
         raise HTTPException(status_code=400, detail=f"File exceeds allowed size limit of {client_config.max_document_size_mb}MB.")

    # Check document count quota
    count_stmt = select(func.count(Document.id)).where(Document.client_id == resolved_client_id)
    current_count = (await session.execute(count_stmt)).scalar() or 0
    if current_count >= client_config.max_documents:
        raise HTTPException(status_code=403, detail="Document quota exceeded (count).")

    # Check storage quota
    storage_stmt = select(func.sum(Document.file_size)).where(Document.client_id == resolved_client_id)
    current_storage_bytes = (await session.execute(storage_stmt)).scalar() or 0
    current_storage_mb = current_storage_bytes / (1024 * 1024)
    if current_storage_mb >= client_config.max_storage_mb:
        raise HTTPException(status_code=403, detail="Document quota exceeded (storage).")

    # Storage Warning (Step 3)
    if current_storage_mb >= (client_config.max_storage_mb * 0.8):
        print(f"⚠️ STORAGE WARNING: client_id={resolved_client_id}, usage_percent={round(current_storage_mb/client_config.max_storage_mb*100, 1)}%, remaining_storage_mb={round(client_config.max_storage_mb - current_storage_mb, 2)}")

    # 3) Format & Duplicate Detection
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"We don't support that file type yet. Please use: {', '.join([ext.upper().replace('.', '') for ext in ALLOWED_EXTENSIONS])}")
        
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="This file is too large (>50MB).")
        
    dup_stmt = select(Document).where(
        Document.client_id == resolved_client_id,
        Document.filename == file.filename,
        Document.file_size == file_size
    )
    dup_res = await session.execute(dup_stmt)
    if dup_res.scalars().first():
        raise HTTPException(status_code=400, detail="This document is already in your knowledge base!")

    # Reset cursor for ingestion (if needed, but we used file_bytes)
    await file.seek(0)
    
    # 4) DB Entry (UPLOADING)
    doc = Document(
        client_id=resolved_client_id,
        filename=file.filename,
        file_type=ext.replace(".", ""),
        file_size=file_size,
        status="UPLOADING"
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)

    # 5) Save File
    safe_filename = f"{doc.id}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    with open(file_path, "wb") as f:
        f.write(file_bytes)
        
    # 6) Trigger Background Ingestion
    background_tasks.add_task(ingest_document, doc.id, file_path, resolved_client_id)
    
    return {"message": "Upload started", "document_id": doc.id}

@router.get("")
async def list_documents(
    client_id: int, 
    page: int = 1, 
    page_size: int = 20, 
    status: Optional[str] = None,
    session: AsyncSession = Depends(get_session)
):
    """List all documents for a client with pagination and status filtering."""
    offset = (page - 1) * page_size
    
    statement = select(Document).where(Document.client_id == client_id)
    
    if status:
        statement = statement.where(Document.status == status.upper())
        
    statement = statement.order_by(Document.upload_time.desc()).offset(offset).limit(page_size)
    
    results = await session.execute(statement)
    documents = results.scalars().all()
    
    # Get total count for pagination
    count_stmt = select(func.count(Document.id)).where(Document.client_id == client_id)
    if status:
        count_stmt = count_stmt.where(Document.status == status.upper())
    total = (await session.execute(count_stmt)).scalar() or 0
    
    return {
        "items": [
            {
                "id": d.id,
                "filename": d.filename,
                "status": d.status,
                "file_size": d.file_size,
                "chunk_count": d.chunk_count,
                "upload_time": d.upload_time,
                "processing_time_ms": d.processing_time_ms,
                "error_message": d.error_message
            }
            for d in documents
        ],
        "total": total,
        "page": page,
        "page_size": page_size
    }

@router.delete("/all")
async def delete_all_documents(client_id: int, force: bool = Query(False), session: AsyncSession = Depends(get_session)):
    """
    Deletes ALL documents and chunks for a specific client.
    Requires force=true for safety.
    """
    if not force:
        raise HTTPException(status_code=400, detail="Bulk deletion requires confirmation. Please set force=true.")
    
    from app.models.document import DocumentChunk
    from sqlalchemy import delete
    
    # 1. Delete all chunks for this client
    chunk_del_stmt = delete(DocumentChunk).where(DocumentChunk.client_id == client_id)
    await session.execute(chunk_del_stmt)
    
    # 2. Delete all documents for this client
    doc_del_stmt = delete(Document).where(Document.client_id == client_id)
    await session.execute(doc_del_stmt)
    
    await session.commit()
    
    # 3. Cleanup uploads folder (id-prefixed files)
    # Clear db is priority. Physical cleanup helps storage.
    
    print(f"\nBULK DELETE TRIGGERED: client_id={client_id}\n")
    return {"message": f"All documents for client {client_id} have been deleted."}

@router.delete("/{document_id}")
async def delete_document(document_id: int, force: bool = Query(False), session: AsyncSession = Depends(get_session)):
    """
    Deletes a document, its metadata, and all associated vector chunks.
    Step 8: Add Document Deletion Safety
    """
    if not force:
        raise HTTPException(status_code=400, detail="Deletion requires confirmation. Please set force=true.")
    from app.models.document import DocumentChunk
    from sqlalchemy import delete
    
    # 1. Fetch doc
    doc = await session.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    
    # 2. Delete associated chunks from vector store
    chunk_del_stmt = delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
    await session.execute(chunk_del_stmt)
    
    # 3. Delete metadata
    await session.delete(doc)
    await session.commit()
    
    # 4. Optional: Delete physical file
    safe_filename = f"{doc.id}_{doc.filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    print(f"\nDOCUMENT DELETED:\ndocument_id: {document_id}\nfilename: {doc.filename}\n")
    return {"message": "Document and associated knowledge deleted successfully."}

@router.post("/{document_id}/reindex")
async def reindex_document(
    document_id: int, 
    background_tasks: BackgroundTasks, 
    session: AsyncSession = Depends(get_session)
):
    """
    Re-runs the ingestion pipeline for an existing document.
    Step 4: Add Reindex Endpoint
    """
    from app.models.document import DocumentChunk
    from sqlalchemy import delete
    
    # 1. Fetch doc
    doc = await session.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    
    # 2. Clear old chunks
    chunk_del_stmt = delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
    await session.execute(chunk_del_stmt)
    
    # 3. Reset status
    doc.status = "PROCESSING"
    doc.chunk_count = 0
    await session.commit()
    
    # 4. Trigger ingestion
    safe_filename = f"{doc.id}_{doc.filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    if not os.path.exists(file_path):
        doc.status = "FAILED"
        doc.error_message = "Physical file missing on server."
        await session.commit()
        raise HTTPException(status_code=400, detail="Original file missing. Please re-upload.")

    background_tasks.add_task(ingest_document, doc.id, file_path, doc.client_id)
    
    print(f"\nDOCUMENT REINDEXED:\ndocument_id: {document_id}\nfilename: {doc.filename}\n")
    return {"message": "Reindexing triggered."}
@router.post("/{document_id}/retry")
async def retry_document(
    document_id: int, 
    background_tasks: BackgroundTasks, 
    session: AsyncSession = Depends(get_session)
):
    """
    Re-triggers ingestion for a FAILED document.
    Step 3: Add Document Retry Endpoint
    """
    # 1. Fetch doc
    doc = await session.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    
    # 2. Check if it's actually failed
    if doc.status != "FAILED":
        raise HTTPException(status_code=400, detail=f"Only FAILED documents can be retried. Current status: {doc.status}")
    
    # 3. Reset status and error
    doc.status = "PROCESSING"
    doc.error_message = None
    doc.chunk_count = 0
    await session.commit()
    
    # 4. Trigger ingestion
    safe_filename = f"{doc.id}_{doc.filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    if not os.path.exists(file_path):
        doc.status = "FAILED"
        doc.error_message = "Original file missing on server. Please re-upload manually."
        await session.commit()
        raise HTTPException(status_code=400, detail="Original file missing. Please re-upload.")

    background_tasks.add_task(ingest_document, doc.id, file_path, doc.client_id)
    
    print(f"\nDOCUMENT RETRY TRIGGERED:\ndocument_id: {document_id}\nfilename: {doc.filename}\n")
    return {"message": "Retry triggered successfully.", "document_id": document_id}

# --- ADMIN QUOTA MANAGEMENT (Step 5) ---
@router.post("/admin/client/{target_client_id}/quota")
async def update_client_quota(
    target_client_id: int,
    max_documents: Optional[int] = None,
    max_storage_mb: Optional[int] = None,
    max_document_size_mb: Optional[int] = None,
    session: AsyncSession = Depends(get_session)
):
    """Allows administrators to override document quotas for a specific client."""
    from app.models.client_config import ClientConfig
    client = await session.get(ClientConfig, target_client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    if max_documents is not None:
        client.max_documents = max_documents
    if max_storage_mb is not None:
        client.max_storage_mb = max_storage_mb
    if max_document_size_mb is not None:
        client.max_document_size_mb = max_document_size_mb
        
    session.add(client)
    await session.commit()
    
    return {
        "status": "success",
        "client_id": target_client_id,
        "new_limits": {
            "max_documents": client.max_documents,
            "max_storage_mb": client.max_storage_mb,
            "max_document_size_mb": client.max_document_size_mb
        }
    }
