from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, text

class TableHealth(SQLModel, table=True):
    __tablename__ = "table_health"

    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(index=True)
    table_name: str = Field(index=True)
    repaired: bool = Field(default=True)
    repair_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=text("now()"))
    )
    repair_reason: Optional[str] = Field(default=None)
