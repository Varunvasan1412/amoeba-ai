from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone

class Blog(SQLModel, table=True):
    __tablename__ = "blogs"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    content: str
    image_url: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
