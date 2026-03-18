from sqlmodel import SQLModel, Field, Column, JSON
from typing import Optional, List, Dict
from datetime import datetime

class ChatMemory(SQLModel, table=True):
    __tablename__ = "chat_memory"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(index=True, unique=True)
    client_id: int = Field(index=True)
    summary: str = Field(default="")
    entities_discussed: Optional[List[str]] = Field(default=[], sa_column=Column(JSON))
    updated_at: datetime = Field(default_factory=datetime.utcnow)
