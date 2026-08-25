import os
import time
import asyncio
from typing import List
from sqlmodel import select
from app.core.database import async_session
from app.models.document import Document, DocumentChunk
from app.services.audit_service import log_event

def extract_text_pages(file_path: str) -> List[dict]:

    """Extracts text from various file formats, returning a list of {'text': str, 'page': int}.
    NOTE: This is intentionally SYNC (not async) because it is called via run_in_executor."""

    ext = os.path.splitext(file_path)[1].lower()
    pages = []
    
    try:
        if ext == ".pdf":
            import pypdf
            with open(file_path, "rb") as f:
                reader = pypdf.PdfReader(f)
                for i, page in enumerate(reader.pages):
                    t = page.extract_text()
                    if t and t.strip():
                        pages.append({"text": t.strip(), "page": i + 1})
        elif ext == ".docx":
            import docx
            doc = docx.Document(file_path)
            # Docx doesn't have native "pages" in a simple way; treat as one page if small, or split by sections
            full_text = "\n".join(para.text for para in doc.paragraphs)
            if full_text.strip():
                pages.append({"text": full_text.strip(), "page": 1})
        elif ext == ".txt":
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
                if text.strip():
                    pages.append({"text": text.strip(), "page": 1})
        elif ext in {".csv", ".xlsx"}:
            import pandas as pd
            if ext == ".csv":
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)
            text = df.to_string()
            if text.strip():
                pages.append({"text": text.strip(), "page": 1})
    except Exception as e:
        print(f"❌ Extraction error for {file_path}: {e}")
        
    return pages

def chunk_text_with_page(pages: List[dict], chunk_size: int = 1500, overlap: int = 200) -> List[dict]:
    """Splits page-aware text into overlapping chunks, preserving page attribution."""
    all_chunks = []
    chunk_idx = 0
    
    for page_data in pages:
        text = page_data["text"]
        page_num = page_data["page"]
        
        start = 0
        text_len = len(text)
        while start < text_len:
            end = start + chunk_size
            chunk_text = text[start:end]
            all_chunks.append({
                "text": chunk_text,
                "page": page_num,
                "index": chunk_idx
            })
            chunk_idx += 1
            start += (chunk_size - overlap)
            
    return all_chunks

async def ingest_document(document_id: int, file_path: str, client_id: int):
    """Pipeline to extract, chunk, and embed a document."""
    from app.services.rag_service import rag_engine

    start_time = time.time()
    
    async with async_session() as session:
        # 1. Fetch document and mark PROCESSING
        doc = await session.get(Document, document_id)
        if not doc:
            return
            
        doc.status = "PROCESSING"
        await session.commit()
        
        try:
            # 2. Extract (Offload to thread pool to avoid blocking)
            loop = asyncio.get_event_loop()
            pages = await loop.run_in_executor(None, extract_text_pages, file_path)
            if not pages:
                raise ValueError("No text extracted from file.")
                
            # 3. Chunk
            chunks = chunk_text_with_page(pages)
            
            # 4. Generate embeddings and store
            await rag_engine.initialize()
            chunks_saved = 0
            
            for chunk_data in chunks:
                text = chunk_data["text"]
                if not text.strip():
                    continue
                
                # Get embedding from existing engine
                embedding = await rag_engine._get_embedding(text)
                
                doc_chunk = DocumentChunk(
                    document_id=document_id,
                    client_id=client_id,
                    chunk_text=text,
                    page_number=chunk_data["page"],
                    chunk_index=chunk_data["index"],
                    embedding_vector=embedding if embedding else None
                )
                session.add(doc_chunk)
                chunks_saved += 1
                
            # 5. Update Status
            doc.status = "READY"
            doc.chunk_count = chunks_saved
            doc.error_message = None
            
            time_ms = int((time.time() - start_time) * 1000)
            doc.processing_time_ms = time_ms
            await session.commit()
            
            print(f"\nDOCUMENT READY:\n\nfilename: {doc.filename}\nchunks: {chunks_saved}\ntime_ms: {time_ms}\n")
            
        except Exception as e:
            error_msg = str(e)
            print(f"\nDOCUMENT INGESTION FAILED:\n\nfilename: {doc.filename}\nerror: {error_msg}\ntimestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            doc.status = "FAILED"
            doc.error_message = error_msg
            await session.commit()
            
            log_event(
                client_id=client_id,
                action="DOCUMENT_PROCESS_FAILED",
                entity=doc.filename,
                table_name="documents",
                record_id=str(document_id),
                source="SYSTEM",
                status="FAILED",
                details={"error": error_msg}
            )
