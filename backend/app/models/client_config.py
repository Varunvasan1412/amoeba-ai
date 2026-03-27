from sqlmodel import SQLModel, Field
from typing import Optional

class ClientConfig(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    api_key: str = Field(index=True, unique=True)
    client_name: str = Field(unique=True, index=True)
    db_connection_url: str 
    # In production, ENCRYPT this column!
    
    # Governance Mode: simple | guided | strict
    governance_mode: str = Field(default="guided", index=True)
    
    # --- DOCUMENT QUOTAS ---
    max_documents: int = Field(default=500)
    max_storage_mb: int = Field(default=2048)
    max_document_size_mb: int = Field(default=50)

    # --- KNOWLEDGE SOURCES ---
    erp_enabled: bool = Field(default=True)
    documents_enabled: bool = Field(default=True)
    web_enabled: bool = Field(default=False)

    # Onboarding Status
    onboarding_completed: bool = Field(default=False)
