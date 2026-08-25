from typing import List, Optional
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime

class RolePermissionLink(SQLModel, table=True):
    __tablename__ = "role_permissions"
    id: Optional[int] = Field(default=None, primary_key=True)
    role_id: int = Field(foreign_key="roles.id")
    permission_id: int = Field(foreign_key="permissions.id")

class Permission(SQLModel, table=True):
    __tablename__ = "permissions"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    description: Optional[str] = None
    
    roles: List["Role"] = Relationship(back_populates="permissions", link_model=RolePermissionLink)

class Role(SQLModel, table=True):
    __tablename__ = "roles"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # NULL client_id means it's a platform-wide global role
    client_id: Optional[int] = Field(default=None, foreign_key="clientconfig.id")
    
    permissions: List[Permission] = Relationship(back_populates="roles", link_model=RolePermissionLink)
    users: List["User"] = Relationship(back_populates="role")
