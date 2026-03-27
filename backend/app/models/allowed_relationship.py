from typing import Optional, List
from sqlmodel import SQLModel, Field, Column, JSON
from datetime import datetime

class AllowedRelationship(SQLModel, table=True):
    __tablename__ = "allowed_relationships"

    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(index=True)

    parent_table: str = Field(index=True)
    parent_column: str

    child_table: str = Field(index=True)
    child_column: str

    is_enabled: bool = Field(default=False)
    is_restricted: bool = Field(default=False)

    # NEW: Store which columns from the related table should be included
    # Format: ["col1", "col2", "col3"]
    selected_columns: List[str] = Field(default=[], sa_column=Column(JSON))

    # Risk Classification (v3)
    risk_level: str = Field(default="safe") # safe | heuristic | circular | high_cardinality
    confidence_score: float = Field(default=1.0) # 1.0 = Explicit, <1.0 = Heuristic

    created_at: datetime = Field(default_factory=datetime.utcnow)
