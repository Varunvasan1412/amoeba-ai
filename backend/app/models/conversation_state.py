from typing import Optional, Dict, Any
from sqlmodel import SQLModel, Field, Column, JSON
from datetime import datetime

class ConversationState(SQLModel, table=True):
    __tablename__ = "conversation_state"

    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(index=True)
    session_id: str = Field(index=True)
    intent: str  # create, read, update, delete
    entity_name: str
    current_step: str
    collected_data: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
