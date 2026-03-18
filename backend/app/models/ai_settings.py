from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime, text

class AISettings(SQLModel, table=True):
    __tablename__ = "ai_settings"

    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(index=True, unique=True)
    
    provider: str = Field(default="gemini") # gemini | openai | ollama | claude
    model: str = Field(default="gemini-2.0-flash-lite")
    temperature: float = Field(default=0.7)
    max_tokens: int = Field(default=2048)
    
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=text("now()"))
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=text("now()"), onupdate=text("now()"))
    )
