from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, UniqueConstraint
from sqlalchemy import Column, DateTime, text

class FieldMetadata(SQLModel, table=True):
    __tablename__ = "field_metadata"
    __table_args__ = (
        UniqueConstraint("client_id", "table_name", "column_name", name="uix_client_table_column_field_meta"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(index=True)
    table_name: str = Field(index=True)
    column_name: str = Field(index=True)
    
    label: str # Human-friendly name
    input_type: str # text | dropdown | checkbox | radio | date | number | textarea
    storage_type: str = Field(default="string") # string | integer | float | boolean | date
    
    # Dropdown logic
    data_source_table: Optional[str] = None
    value_column: Optional[str] = None # e.g. "id"
    display_column: Optional[str] = None # e.g. "name"
    
    # Form Logic
    required: bool = Field(default=False)
    readonly: bool = Field(default=False)
    is_visible: bool = Field(default=True)
    default_value: Optional[str] = None
    
    # Audit
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=text("now()"))
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=text("now()"), onupdate=text("now()"))
    )
