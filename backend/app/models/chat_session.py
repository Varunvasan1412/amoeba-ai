from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
import uuid

class ChatSession(SQLModel, table=True):
    __tablename__ = "chat_session"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(index=True)
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()), index=True, unique=True)
    title: Optional[str] = Field(default="New Chat")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
