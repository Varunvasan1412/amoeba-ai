from typing import List, Optional
from sqlmodel import SQLModel, Field, Column, JSON
from sqlalchemy import UniqueConstraint

class SemanticMetadata(SQLModel, table=True):
    __tablename__ = "semantic_metadata"
    __table_args__ = (
        UniqueConstraint("client_id", "table_name", "column_name", name="uix_client_table_column"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(index=True)
    table_name: str = Field(index=True)
    column_name: str = Field(index=True)
    
    # Semantic Fields
    label: str  # e.g. "Total Revenue"
    description: Optional[str] = None
    synonyms: List[str] = Field(default=[], sa_column=Column(JSON))
    data_format: str = Field(default="text") # currency, date, percent, text
    
    # Safety Flags
    is_pii: bool = Field(default=False)
    is_default_date: bool = Field(default=False)
