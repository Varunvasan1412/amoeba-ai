from typing import Optional
from sqlmodel import SQLModel, Field

class BackupSettings(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    schedule_hour: int = Field(default=2)
    schedule_minute: int = Field(default=0)
    retention_days: int = Field(default=7)
    enabled: bool = Field(default=True)
    last_restore_at: Optional[str] = Field(default=None) # ISO timestamp
    last_restore_file: Optional[str] = Field(default=None)
