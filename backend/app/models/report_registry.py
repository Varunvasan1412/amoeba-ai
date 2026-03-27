from typing import Optional, List
from datetime import datetime
from sqlmodel import SQLModel, Field, Column, JSON
from sqlalchemy import UniqueConstraint

class ReportRegistry(SQLModel, table=True):
    __tablename__ = "report_registry"
    __table_args__ = (
        UniqueConstraint("client_id", "report_key", name="unique_client_report"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(index=True)
    report_key: str = Field(index=True) # Unique ID from the JSON payload (e.g. "daily_prod")
    display_name: str
    user_phrases: List[str] = Field(default=[], sa_column=Column(JSON))
    sql_template: str
    builder_definition: dict = Field(default={}, sa_column=Column(JSON)) # UI State
    date_column: Optional[str] = None
    output_format: str = Field(default="xlsx")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
