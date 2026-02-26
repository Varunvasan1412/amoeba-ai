from sqlmodel import SQLModel, Field
from typing import Optional

class ClientConfig(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    api_key: str = Field(index=True, unique=True)
    client_name: str
    db_connection_url: str 
    # In production, ENCRYPT this column!
    
    # Governance Mode: simple | guided | strict
    governance_mode: str = Field(default="guided", index=True)
