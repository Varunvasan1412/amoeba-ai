from sqlmodel import SQLModel, Field
from typing import Optional

class ClientConfig(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    api_key: str = Field(index=True, unique=True)
    client_name: str = Field(unique=True, index=True)
    company_code: Optional[str] = Field(default=None, unique=True, index=True, nullable=True)
    db_connection_url: Optional[str] = Field(default="")
    created_at: str = Field(default_factory=lambda: __import__("datetime").datetime.utcnow().isoformat())
    is_active: bool = Field(default=True)
    total_tokens_used: int = Field(default=0)
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

    # --- FEATURE TOGGLES ---
    feature_wizard_enabled: bool = Field(default=True)
    feature_relationships_enabled: bool = Field(default=True)
    feature_semantic_enabled: bool = Field(default=True)
    feature_reports_enabled: bool = Field(default=True)
    feature_routing_enabled: bool = Field(default=True)
    feature_ai_settings_enabled: bool = Field(default=True)
    feature_health_enabled: bool = Field(default=True)
    feature_backups_enabled: bool = Field(default=True)
    feature_tenants_enabled: bool = Field(default=True)
    feature_security_enabled: bool = Field(default=True)

    # Onboarding Status
    onboarding_completed: bool = Field(default=False)
