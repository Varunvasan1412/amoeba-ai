from typing import Optional, List, Any
from datetime import datetime
from sqlmodel import SQLModel, Field, Column
from sqlalchemy.dialects.postgresql import JSONB

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None

class Document(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(index=True)
    filename: str
    file_type: str
    file_size: int
    upload_time: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="UPLOADING")
    chunk_count: int = Field(default=0)
    error_message: Optional[str] = Field(default=None)
    processing_time_ms: Optional[int] = Field(default=None)

class DocumentChunk(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="document.id", index=True)
    client_id: int = Field(index=True)
    chunk_text: str
    page_number: Optional[int] = Field(default=None, index=True)
    chunk_index: int = Field(default=0, index=True)
    
    if Vector is not None:
        embedding_vector: Any = Field(sa_column=Column(Vector(3072)))  # Matching models/gemini-embedding-001
    else:
        # Fallback if pgvector not installed locally
        embedding_vector: Optional[str] = None
