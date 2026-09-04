from sqlmodel import SQLModel, Field, Column
from pgvector.sqlalchemy import Vector
from typing import Optional, List

class NavigationItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    label: str # e.g. "Sales Enquiry"
    module: Optional[str] = None # e.g. "CRM", "Sales", "Support"
    table_name: Optional[str] = None # e.g. "sales_enquiry_head"
    path: str
    icon: Optional[str] = "Circle" 
    order: int = 0
    client_id: int = Field(index=True)
    is_discovered: bool = Field(default=False, index=True)
    embedding: Optional[List[float]] = Field(default=None, sa_column=Column(Vector(1536)))
