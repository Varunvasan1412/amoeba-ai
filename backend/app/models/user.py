from typing import Optional, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from app.models.rbac import Role

class User(SQLModel, table=True):
    __tablename__ = "users"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    email: Optional[str] = Field(default=None, index=True, unique=True)
    hashed_password: str
    is_active: bool = Field(default=True)
    is_admin: bool = Field(default=False)
    is_platform_user: bool = Field(default=False)
    
    client_id: Optional[int] = Field(default=None, foreign_key="clientconfig.id")
    
    role_id: Optional[int] = Field(default=None, foreign_key="roles.id")
    role: Optional["Role"] = Relationship(back_populates="users")
