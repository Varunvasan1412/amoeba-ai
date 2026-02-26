from sqlmodel import SQLModel, Field
from typing import Optional

class NavigationItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    label: str
    path: str
    icon: Optional[str] = "Circle" 
    order: int = 0
