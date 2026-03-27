from fastapi import APIRouter, Depends, HTTPException, Security, Header
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from typing import List, Optional, Any, Dict
from pydantic import BaseModel

from app.core.database import get_session
from app.models.client_config import ClientConfig
from app.services.semantic_service import (
    bulk_upsert_semantics, 
    get_semantic_schema, 
    get_table_semantics
)
from app.core.auth_deps import get_current_active_admin

router = APIRouter(dependencies=[Depends(get_current_active_admin)])

# Security Scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_current_client(
    api_key: str = Security(api_key_header),
    session: AsyncSession = Depends(get_session)
) -> ClientConfig:
    """
    Validates API Key and returns the Client Config.
    Functions as the Admin Auth check (possession of API Key = Admin).
    """
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    
    statement = select(ClientConfig).where(ClientConfig.api_key == api_key)
    result = await session.execute(statement)
    client = result.scalars().first()
    
    if not client:
        raise HTTPException(status_code=403, detail="Invalid API Key")
        
    return client

# --- Request Models ---

class SemanticColumnPayload(BaseModel):
    table_name: str
    column_name: str
    label: str
    description: Optional[str] = None
    synonyms: List[str] = []
    data_format: str = "text"
    is_pii: bool = False
    is_default_date: bool = False

class BulkSemanticRequest(BaseModel):
    mappings: List[SemanticColumnPayload]

# --- Endpoints ---

@router.post("/v2/semantic/columns")
async def upsert_semantic_columns(
    payload: BulkSemanticRequest,
    client: ClientConfig = Depends(get_current_client),
    session: AsyncSession = Depends(get_session)
):
    """
    Bulk create or update semantic definitions.
    Rejects invalid tables/columns via SemanticService validation.
    """
    # Convert Pydantic to generic dict for service layer (keeps service clean of Pydantic if possible, or just pass objects)
    # The service expects List[Dict].
    mapping_dicts = [m.dict() for m in payload.mappings]
    
    result = await bulk_upsert_semantics(session, client.id, mapping_dicts)
    return result

@router.get("/v2/semantic/schema")
async def get_full_semantic_schema(
    client: ClientConfig = Depends(get_current_client),
    session: AsyncSession = Depends(get_session)
):
    """
    Get the full semantic map for the client.
    """
    return await get_semantic_schema(session, client.id)

@router.get("/v2/semantic/tables/{table_name}")
async def get_table_metadata(
    table_name: str,
    client: ClientConfig = Depends(get_current_client),
    session: AsyncSession = Depends(get_session)
):
    """
    Get semantic metadata for a specific table.
    """
    return await get_table_semantics(session, client.id, table_name)
