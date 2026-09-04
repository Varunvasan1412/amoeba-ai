# ACP v1 FINAL — Do not extend without version bump

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlmodel import select
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool
import asyncio
import logging

from app.core.database import get_session
from app.models.client_config import ClientConfig
from app.services.onboarding import generate_api_key, build_connection_url, test_db_connection, discover_tables
from app.services.field_metadata_service import generate_field_metadata
from app.services.audit_service import log_audit
from app.services.relationship_service import clear_relationship_cache
from app.core.auth_deps import get_current_super_admin
from app.security.permission_guard import require_permission, get_current_user
from app.models.user import User
from app.services.client_service import sanitize_client_data

router = APIRouter(tags=["Clients"])
logger = logging.getLogger(__name__)

# --- Request Models ---
class CreateClientRequest(BaseModel):
    client_name: str
    company_code: Optional[str] = None

class DBConnectionRequest(BaseModel):
    db_type: str
    host: str
    port: int
    database: str
    username: str
    password: str

class GovernanceModeRequest(BaseModel):
    governance_mode: str

class QuotaRequest(BaseModel):
    max_documents: int
    max_storage_mb: int
    max_document_size_mb: int

class SourcesRequest(BaseModel):
    erp: bool
    documents: bool
    web: bool

class UpdateClientRequest(BaseModel):
    client_name: Optional[str] = None
    company_code: Optional[str] = None
    feature_wizard_enabled: Optional[bool] = None
    feature_relationships_enabled: Optional[bool] = None
    feature_semantic_enabled: Optional[bool] = None
    feature_reports_enabled: Optional[bool] = None
    feature_routing_enabled: Optional[bool] = None
    feature_ai_settings_enabled: Optional[bool] = None
    feature_health_enabled: Optional[bool] = None
    feature_backups_enabled: Optional[bool] = None
    feature_tenants_enabled: Optional[bool] = None
    feature_security_enabled: Optional[bool] = None
    schema_rag_enabled: Optional[bool] = None

class StatusRequest(BaseModel):
    is_active: bool

# --- Endpoints ---

@router.post("/clients", dependencies=[Depends(get_current_super_admin)])
async def create_client(
    payload: CreateClientRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Step 1: Create a new Client and return their API Key.
    """
    # Check for existing name
    existing_stmt = select(ClientConfig).where(ClientConfig.client_name == payload.client_name)
    existing = (await session.execute(existing_stmt)).scalars().first()
    if existing:
        raise HTTPException(status_code=400, detail=f"A company named '{payload.client_name}' is already registered.")

    # Generate Key
    new_api_key = generate_api_key()
    
    client = ClientConfig(
        client_name=payload.client_name,
        company_code=payload.company_code,
        api_key=new_api_key,
        db_connection_url="" 
    )
    
    session.add(client)
    await session.commit()
    await session.refresh(client)
    
    log_audit(client.id, "client_created", {"name": payload.client_name})
    
    # Audit access (Feature 3)
    logger.info(f"API key created/accessed by platform admin during generation for client {client.id}")

    return {
        "status": "success",
        "data": {
            "client_id": client.id,
            "api_key": client.api_key
        }
    }

@router.post("/clients/{client_id}/database")
async def connect_database(
    client_id: int,
    payload: DBConnectionRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Step 2: Configure and Test ERP Database Connection.
    """
    # 1. Get Client
    client = await session.get(ClientConfig, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
        
    # 2. Build URL
    try:
        url = build_connection_url(
            payload.db_type, payload.username, payload.password,
            payload.host, payload.port, payload.database
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 3. Test Connection (hard 15s deadline)
    try:
        result = await asyncio.wait_for(
            run_in_threadpool(test_db_connection, url),
            timeout=15.0
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="Connection timed out after 15 seconds. Verify host is reachable.")
    if not result:
         raise HTTPException(status_code=400, detail="Connection failed. Please check credentials and firewall.")

    # 4. Save (Encrypt in Prod, Plain for now per instructions)
    client.db_connection_url = url
    session.add(client)
    await session.commit()
    
    log_audit(client_id, "db_connected", {"db_type": payload.db_type, "host": payload.host})
    
    return {"status": "success", "message": "Database connection verified and saved."}

@router.get("/clients/{client_id}/tables")
async def get_client_tables(
    client_id: int,
    session: AsyncSession = Depends(get_session)
):
    """
    Step 3: Discover Tables and Columns from ERP.
    """
    client = await session.get(ClientConfig, client_id)
    if client is None or not client.db_connection_url:
        raise HTTPException(status_code=404, detail="Client or Database connection not found")
        
    try:
        tables = await asyncio.wait_for(
            run_in_threadpool(discover_tables, client.db_connection_url),
            timeout=30.0
        )
        # Auto-generate UX metadata
        try:
            count = await generate_field_metadata(client_id, session)
            log_audit(client_id, "field_metadata_generated", {"count": count})
        except Exception as meta_err:
            import traceback
            print(f"❌ Field Metadata Generation Error: {meta_err}")
            print(traceback.format_exc())
            # We don't fail discovery just because metadata failed
        
        log_audit(client_id, "tables_discovered", {"count": len(tables)})
        return {"tables": tables}
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ Discovery failed for client {client_id}: {e}")
        print(error_trace)
        raise HTTPException(status_code=500, detail=f"Discovery failed: {str(e)}")


@router.get("/clients")
async def list_clients(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    List all clients. API Key is masked for non-platform users (Feature 3).
    """
    from app.services.client_service import sanitize_client_data
    statement = select(ClientConfig).order_by(ClientConfig.id)
    result = await session.execute(statement)
    clients = result.scalars().all()
    
    output = []
    for c in clients:
        client_dict = {
            "id": c.id, 
            "client_name": c.client_name,
            "company_code": c.company_code,
            "api_key": c.api_key, 
            "created_at": getattr(c, "created_at", None),
            # ... rest of the fields
        }
        # Explicit mapping for safety
        base_data = {
            "id": c.id, 
            "client_name": c.client_name,
            "company_code": c.company_code,
            "api_key": c.api_key, 
            "created_at": getattr(c, "created_at", None),
            "is_active": getattr(c, "is_active", True),
            "governance_mode": c.governance_mode,
            "max_documents": c.max_documents,
            "max_storage_mb": c.max_storage_mb,
            "max_document_size_mb": c.max_document_size_mb,
            "erp_enabled": c.erp_enabled,
            "documents_enabled": c.documents_enabled,
            "web_enabled": c.web_enabled,
            "feature_wizard_enabled": getattr(c, "feature_wizard_enabled", True),
            "feature_relationships_enabled": getattr(c, "feature_relationships_enabled", True),
            "feature_semantic_enabled": getattr(c, "feature_semantic_enabled", True),
            "feature_reports_enabled": getattr(c, "feature_reports_enabled", True),
            "feature_routing_enabled": getattr(c, "feature_routing_enabled", True),
            "feature_ai_settings_enabled": getattr(c, "feature_ai_settings_enabled", True),
            "feature_health_enabled": getattr(c, "feature_health_enabled", True),
            "feature_backups_enabled": getattr(c, "feature_backups_enabled", True),
            "feature_tenants_enabled": getattr(c, "feature_tenants_enabled", True),
            "feature_security_enabled": getattr(c, "feature_security_enabled", True),
            "schema_rag_enabled": getattr(c, "schema_rag_enabled", False),
            "schema_synced": getattr(c, "schema_synced", False)
        }
        output.append(sanitize_client_data(base_data, current_user))

    return {"clients": output}

@router.post("/clients/{client_id}/quota", dependencies=[Depends(get_current_super_admin)])
async def update_client_quota(
    client_id: int,
    payload: QuotaRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Update document quotas for a client.
    """
    client = await session.get(ClientConfig, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
        
    client.max_documents = payload.max_documents
    client.max_storage_mb = payload.max_storage_mb
    client.max_document_size_mb = payload.max_document_size_mb
    
    session.add(client)
    await session.commit()
    log_audit(client_id, "quota_updated", payload.dict())
    return {"status": "success", "message": "Quotas updated successfully"}

@router.post("/clients/{client_id}/sources", dependencies=[Depends(require_permission("configure_system"))])
async def update_client_sources(
    client_id: int,
    payload: SourcesRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Toggle Knowledge Sources (ERP, Documents, Web).
    """
    client = await session.get(ClientConfig, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
        
    client.erp_enabled = payload.erp
    client.documents_enabled = payload.documents
    client.web_enabled = payload.web
    
    session.add(client)
    await session.commit()
    log_audit(client_id, "sources_updated", payload.dict())
    return {"status": "success", "message": "Knowledge sources updated"}

@router.patch("/clients/{client_id}/governance-mode", dependencies=[Depends(require_permission("configure_system"))])
async def update_governance_mode(
    client_id: int,
    payload: GovernanceModeRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Update the Governance Mode for a client (Simple, Guided, Strict).
    """
    valid_modes = ["simple", "guided", "strict"]
    if payload.governance_mode not in valid_modes:
        raise HTTPException(status_code=400, detail=f"Invalid mode. Must be one of {valid_modes}")

    client = await session.get(ClientConfig, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
        
    old_mode = client.governance_mode
    client.governance_mode = payload.governance_mode
    session.add(client)
    await session.commit()
    await session.refresh(client)
    
    # clear cache to force re-discovery with new rules
    clear_relationship_cache(client_id)
    
    log_audit(client_id, "governance_mode_updated", {"old": old_mode, "new": payload.governance_mode})
    
    return {"status": "success", "data": client}

@router.patch("/clients/{client_id}")
async def update_client(
    client_id: int,
    payload: UpdateClientRequest,
    u: User = Depends(get_current_super_admin),
    session: AsyncSession = Depends(get_session)
):
    """
    Update basic client details (Name, Company Code).
    """
    try:
        client = await session.get(ClientConfig, client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
            
        if payload.client_name is not None:
            # Check uniqueness
            stmt = select(ClientConfig).where(ClientConfig.client_name == payload.client_name).where(ClientConfig.id != client_id)
            existing = await session.execute(stmt)
            if existing.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Client name already exists")
            client.client_name = payload.client_name
            
        if payload.company_code is not None:
            # Check uniqueness
            if payload.company_code.strip():
                stmt = select(ClientConfig).where(ClientConfig.company_code == payload.company_code).where(ClientConfig.id != client_id)
                existing = await session.execute(stmt)
                if existing.scalar_one_or_none():
                    raise HTTPException(status_code=400, detail="Company code already exists")
            client.company_code = payload.company_code or None
            
        # Update Feature Flags
        if payload.feature_wizard_enabled is not None:
            client.feature_wizard_enabled = payload.feature_wizard_enabled
        if payload.feature_relationships_enabled is not None:
            client.feature_relationships_enabled = payload.feature_relationships_enabled
        if payload.feature_semantic_enabled is not None:
            client.feature_semantic_enabled = payload.feature_semantic_enabled
        if payload.feature_reports_enabled is not None:
            client.feature_reports_enabled = payload.feature_reports_enabled
        if payload.feature_routing_enabled is not None:
            client.feature_routing_enabled = payload.feature_routing_enabled
        if payload.feature_ai_settings_enabled is not None:
            client.feature_ai_settings_enabled = payload.feature_ai_settings_enabled
        if payload.feature_health_enabled is not None:
            client.feature_health_enabled = payload.feature_health_enabled
        if payload.feature_backups_enabled is not None:
            client.feature_backups_enabled = payload.feature_backups_enabled
        if payload.feature_tenants_enabled is not None:
            client.feature_tenants_enabled = payload.feature_tenants_enabled
        if payload.feature_security_enabled is not None:
            client.feature_security_enabled = payload.feature_security_enabled
        if payload.schema_rag_enabled is not None:
            client.schema_rag_enabled = payload.schema_rag_enabled

        session.add(client)
        await session.commit()
        await session.refresh(client)
        
        log_audit(client_id, "client_updated", payload.dict(exclude_none=True))
        return {"status": "success", "data": client}
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/clients/{client_id}/generate-code", dependencies=[Depends(get_current_super_admin)])
async def generate_client_code(
    client_id: int,
    session: AsyncSession = Depends(get_session)
):
    """
    Generate a new unique company code for an existing client.
    """
    from app.services.onboarding import generate_company_code
    client = await session.get(ClientConfig, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
        
    new_code = generate_company_code(client.client_name)
    client.company_code = new_code
    session.add(client)
    await session.commit()
    await session.refresh(client)
    
    log_audit(client_id, "code_generated", {"code": new_code})
    return {"status": "success", "code": new_code}

@router.post("/clients/{client_id}/rotate-key", dependencies=[Depends(get_current_super_admin)])
async def rotate_client_api_key(
    client_id: int,
    session: AsyncSession = Depends(get_session)
):
    """
    Regenerate the API key for a client.
    """
    from app.services.onboarding import generate_api_key
    client = await session.get(ClientConfig, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
        
    old_key = client.api_key
    new_key = generate_api_key()
    client.api_key = new_key
    session.add(client)
    await session.commit()
    await session.refresh(client)
    
    log_audit(client_id, "api_key_rotated", {"old": f"{old_key[:8]}...", "new": f"{new_key[:8]}..."})
    
    # Audit access
    import logging
    logging.getLogger(__name__).info(f"API key regenerated/accessed by platform admin for client {client_id}")

    return {"status": "success", "api_key": new_key}

@router.patch("/clients/{client_id}/status", dependencies=[Depends(get_current_super_admin)])
async def update_client_status(
    client_id: int,
    payload: StatusRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Disable or Enable a client configuration.
    """
    client = await session.get(ClientConfig, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
        
    client.is_active = payload.is_active
    session.add(client)
    await session.commit()
    await session.refresh(client)
    
    log_audit(client_id, "status_updated", {"is_active": payload.is_active})
    return {"status": "success", "is_active": payload.is_active}

@router.delete("/clients/{client_id}", dependencies=[Depends(get_current_super_admin)])
async def delete_client(
    client_id: int,
    session: AsyncSession = Depends(get_session)
):
    """
    Delete a client permanently.
    """
    from sqlalchemy import delete
    
    client = await session.get(ClientConfig, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Unlink or delete users attached to this client. We will unset their client_id.
    await session.execute(
        select(User).where(User.client_id == client_id)
    ) # just a check, but we will simply execute an update
    
    from sqlalchemy import update
    await session.execute(
        update(User).where(User.client_id == client_id).values(client_id=None, is_active=False)
    )
    
    await session.delete(client)
    await session.commit()
    
    log_audit(client_id, "client_deleted", {"client_name": client.client_name})
    return {"status": "success", "message": "Client deleted"}
