from sqlmodel import SQLModel, Field, Column, DateTime, text
from datetime import datetime
from typing import Optional

class BackupValidationLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    backup_file: str = Field(index=True)
    status: str # PASS, FAIL, SKIPPED
    tested_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    )
    duration_ms: int
    error_message: Optional[str] = None
