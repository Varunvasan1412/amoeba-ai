from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class UISchemaCache(SQLModel, table=True):
    __tablename__ = "ui_schema_cache"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(index=True)
    page_path: str = Field(index=True) # e.g. /enquiry/salescontact
    field_name: str # e.g. customer_id
    label: str # e.g. Customer Name
    field_type: str # e.g. text, select
    created_at: datetime = Field(default_factory=datetime.utcnow)
