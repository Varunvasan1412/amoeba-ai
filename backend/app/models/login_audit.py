from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime
from sqlalchemy import Column, DateTime, String

class LoginAudit(SQLModel, table=True):
    __tablename__ = "login_audits"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, index=True)
    email: str = Field(index=True)
    client_id: Optional[int] = Field(default=None, index=True)
    company_code: Optional[str] = None
    ip_address: str
    user_agent: str
    status: str # SUCCESS | FAILED
    failure_reason: Optional[str] = None
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    )
