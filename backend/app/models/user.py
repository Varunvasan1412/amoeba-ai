from typing import Optional
from sqlmodel import SQLModel, Field

class User(SQLModel, table=True):
    __tablename__ = "users"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    hashed_password: str
    is_active: bool = Field(default=True)
    is_admin: bool = Field(default=False)
