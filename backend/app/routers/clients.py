# ACP v1 FINAL — Do not extend without version bump

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlmodel import select
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_session
from app.models.client_config import ClientConfig
from app.services.onboarding import generate_api_key, build_connection_url, test_db_connection, discover_tables
from app.services.field_metadata_service import generate_field_metadata
from app.services.audit_service import log_audit
from app.services.relationship_service import clear_relationship_cache
from app.core.auth_deps import get_current_active_admin

router = APIRouter(dependencies=[Depends(get_current_active_admin)])

# --- Request Models ---
class CreateClientRequest(BaseModel):
    client_name: str

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

# --- Endpoints ---

@router.post("/clients")
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
        api_key=new_api_key,
        db_connection_url="" # Empty initially
    )
    
    session.add(client)
    await session.commit()
    await session.refresh(client)
    
    log_audit(client.id, "client_created", {"name": payload.client_name})
    
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

    # 3. Test Connection
    if not test_db_connection(url):
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
        tables = discover_tables(client.db_connection_url)
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
async def list_clients(session: AsyncSession = Depends(get_session)):
    """
    List all clients for the Admin Dashboard dropdown.
    """
    statement = select(ClientConfig).order_by(ClientConfig.id)
    result = await session.execute(statement)
    clients = result.scalars().all()
    
    return {
        "clients": [
            {
                "id": c.id, 
                "client_name": c.client_name,
                "api_key": c.api_key, 
                "governance_mode": c.governance_mode,
                "max_documents": c.max_documents,
                "max_storage_mb": c.max_storage_mb,
                "max_document_size_mb": c.max_document_size_mb,
                "erp_enabled": c.erp_enabled,
                "documents_enabled": c.documents_enabled,
                "web_enabled": c.web_enabled
            } 
            for c in clients
        ]
    }

@router.post("/clients/{client_id}/quota")
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

@router.post("/clients/{client_id}/sources")
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

@router.patch("/clients/{client_id}/governance-mode")
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
