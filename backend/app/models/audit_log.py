
import uuid
from typing import Optional, Dict, Any
from sqlmodel import SQLModel, Field, JSON
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, text
from sqlalchemy.dialects.postgresql import UUID, JSONB

class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), index=True, nullable=False)
    )
    client_id: Optional[int] = Field(default=None, index=True)
    user_id: Optional[str] = Field(default=None, index=True)
    action: str = Field(index=True) # CREATE, UPDATE, DELETE, READ, UPLOAD, RETRY, NAVIGATION, LOGIN, LOGOUT
    entity: Optional[str] = Field(default=None) # e.g. "Sales Enquiry"
    table_name: Optional[str] = Field(default=None) # e.g. "enquiry_detail"
    record_id: Optional[str] = Field(default=None)
    source: str = Field(index=True) # USER, AI, SYSTEM
    status: str = Field(index=True) # SUCCESS, FAILED
    details: Dict[str, Any] = Field(
        default={},
        sa_column=Column(JSONB)
    )
    ip_address: Optional[str] = Field(default=None)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=text("now()"))
    )

