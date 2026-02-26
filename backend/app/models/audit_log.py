
from typing import Optional, Dict, Any
from sqlmodel import SQLModel, Field, JSON
from datetime import datetime
from sqlalchemy import Column

class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: Optional[int] = Field(default=None, index=True) # Optional because some actions might be pre-client
    action: str = Field(index=True) # e.g. "client_created", "report_exported"
    metadata_payload: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
