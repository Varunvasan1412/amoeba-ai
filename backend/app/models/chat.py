from sqlmodel import SQLModel, Field, Column, JSON
from typing import Optional, List, Dict, Any
from datetime import datetime

class ChatMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sender: str
    content: str
    actions: Optional[List[Dict[str, Any]]] = Field(default=[], sa_column=Column(JSON))
    timestamp: datetime = Field(default_factory=datetime.utcnow)