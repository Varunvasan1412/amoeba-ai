from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime

class ApprovedJoinPath(SQLModel, table=True):
    __tablename__ = "approved_join_paths"

    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(index=True)
    
    # Path Signature: "table_a->table_b->table_c"
    # Canonical format: Sorted tables? Or directional path? 
    # For now, let's use directional path string: "table_a:col_a->table_b:col_b"
    # Actually, simplistic "table_a->table_b" sequence is easier for approval logic if we assume unique paths.
    # But let's act on the plan: "path_signature"
    path_signature: str = Field(index=True) 
    
    is_enabled: bool = Field(default=True)
    approved_by: Optional[str] = Field(default=None) # User email/ID
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
