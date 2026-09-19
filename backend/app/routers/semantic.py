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
from app.models.semantic_mapping import SemanticMapping
from app.services.llm_service import get_brain
from langchain_core.messages import HumanMessage, SystemMessage

router = APIRouter()

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

class SemanticMappingResponse(BaseModel):
    id: int
    ui_label: str
    database_table: str
    base_query: Optional[str] = None
    source_file: Optional[str] = None
    is_doubtful: bool

class SQLExtractRequest(BaseModel):
    php_code: str

class SemanticMappingUpdate(BaseModel):
    database_table: str

class SemanticMappingCreate(BaseModel):
    ui_label: str
    database_table: str
    base_query: Optional[str] = None
    default_filter: Optional[str] = None
    ui_columns: Optional[str] = None

# --- Endpoints ---

from app.models.schema_metadata import SchemaMetadata
import json

@router.post("/v2/semantic/discover")
async def discover_concepts(
    client: ClientConfig = Depends(get_current_client),
    session: AsyncSession = Depends(get_session),
    admin = Depends(get_current_active_admin)
):
    """
    Uses heuristics and LLM to propose business concepts from the raw database schema.
    Returns a list of suggested App Concepts for the 'Learn From My App' wizard.
    """
    # 1. Fetch all schema definitions
    schema_res = await session.execute(select(SchemaMetadata).where(SchemaMetadata.client_id == client.id))
    schemas = schema_res.scalars().all()
    
    if not schemas:
        return {"suggested_concepts": []}
        
    # Group schemas into a concise context block
    schema_text = "\n".join([s.schema_definition for s in schemas])
    
    # Trim to avoid token limits if necessary
    if len(schema_text) > 40000:
        schema_text = schema_text[:40000] + "\n... (truncated)"
        
    prompt = f"""
You are an expert application data modeler.
Analyze the following physical database schema and identify the primary high-level "Business Concepts" a non-technical user would care about (e.g., Quotations, Customers, Orders, Invoices).

For each concept, provide:
1. `concept_name`: The human-readable business name (e.g., "Quotation").
2. `source_table`: The physical database table that primarily stores this data.
3. `description`: A brief, non-technical explanation of what this data represents.
4. `likely_condition`: If the table stores multiple types of records (e.g., `enquiries` storing both tickets and quotes), propose a likely SQL filter condition (e.g., "type = 'quotation'"). Otherwise, leave null.

Return your response ONLY as a JSON array of objects.

SCHEMA:
{schema_text}
"""
    try:
        llm = get_brain()
        messages = [
            SystemMessage(content="You return ONLY raw JSON arrays. No markdown, no explanation."),
            HumanMessage(content=prompt)
        ]
        response = await llm.ainvoke(messages)
        
        content = response.content.strip()
        if content.startswith("```json"): content = content[7:]
        if content.endswith("```"): content = content[:-3]
        
        parsed = json.loads(content)
        return {"suggested_concepts": parsed}
    except Exception as e:
        print(f"Error in auto-discovery: {e}")
        return {"suggested_concepts": []}

@router.post("/v2/semantic/columns")
async def upsert_semantic_columns(
    payload: BulkSemanticRequest,
    client: ClientConfig = Depends(get_current_client),
    session: AsyncSession = Depends(get_session),
    admin = Depends(get_current_active_admin)
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
    session: AsyncSession = Depends(get_session),
    admin = Depends(get_current_active_admin)
):
    """
    Get the full semantic map for the client.
    """
    return await get_semantic_schema(session, client.id)

@router.get("/v2/semantic/tables/{table_name}")
async def get_table_metadata(
    table_name: str,
    client: ClientConfig = Depends(get_current_client),
    session: AsyncSession = Depends(get_session),
    admin = Depends(get_current_active_admin)
):
    """
    Get semantic metadata for a specific table.
    """
    return await get_table_semantics(session, client.id, table_name)

@router.get("/v2/semantic/mappings", response_model=List[SemanticMappingResponse])
async def get_ui_table_mappings(
    client_id: int,
    session: AsyncSession = Depends(get_session),
    admin = Depends(get_current_active_admin)
):
    """
    Get all UI-to-Table Semantic Mappings.
    Flags rows as doubtful if they lack a base_query.
    """
    statement = select(SemanticMapping).where(SemanticMapping.client_id == client_id)
    result = await session.execute(statement)
    mappings = result.scalars().all()
    
    response = []
    for m in mappings:
        if not m.id: continue
        response.append(SemanticMappingResponse(
            id=m.id,
            ui_label=m.ui_label or "",
            database_table=m.database_table or "",
            base_query=m.base_query,
            source_file=m.source_file,
            is_doubtful=True if not m.base_query else False
        ))
    return response

@router.put("/v2/semantic/mappings/{mapping_id}")
async def update_ui_table_mapping(
    mapping_id: int,
    client_id: int,
    payload: SemanticMappingUpdate,
    session: AsyncSession = Depends(get_session),
    admin = Depends(get_current_active_admin)
):
    """
    Update the database_table for a specific Semantic Mapping.
    """
    mapping = await session.get(SemanticMapping, mapping_id)
    if not mapping or mapping.client_id != client_id:
        raise HTTPException(status_code=404, detail="Mapping not found")
        
    mapping.database_table = payload.database_table
    session.add(mapping)
    await session.commit()
    return {"status": "success"}

@router.post("/v2/semantic/mappings", response_model=SemanticMappingResponse)
async def create_ui_table_mapping(
    client_id: int,
    payload: SemanticMappingCreate,
    session: AsyncSession = Depends(get_session),
    admin = Depends(get_current_active_admin)
):
    """
    Manually create a new UI-to-Table Semantic Mapping.
    """
    new_m = SemanticMapping(
        client_id=client_id,
        ui_label=payload.ui_label.strip(),
        database_table=payload.database_table.strip(),
        base_query=payload.base_query,
        default_filter=payload.default_filter,
        ui_columns=payload.ui_columns,
        source_file="manual"
    )
    session.add(new_m)
    await session.commit()
    await session.refresh(new_m)
    return SemanticMappingResponse(
        id=new_m.id,
        ui_label=new_m.ui_label,
        database_table=new_m.database_table,
        base_query=new_m.base_query,
        source_file=new_m.source_file,
        is_doubtful=False
    )

@router.delete("/v2/semantic/mappings/{mapping_id}")
async def delete_ui_table_mapping(
    mapping_id: int,
    client_id: int,
    session: AsyncSession = Depends(get_session),
    admin = Depends(get_current_active_admin)
):
    """
    Delete a specific Semantic Mapping.
    """
    mapping = await session.get(SemanticMapping, mapping_id)
    if not mapping or mapping.client_id != client_id:
        raise HTTPException(status_code=404, detail="Mapping not found")
    await session.delete(mapping)
    await session.commit()
    return {"status": "success"}

@router.post("/v2/semantic/mappings/purge")
async def purge_client_semantic_mappings(
    client_id: int,
    session: AsyncSession = Depends(get_session),
    admin = Depends(get_current_active_admin)
):
    """
    Purge all semantic mappings for a client.
    """
    from sqlalchemy import delete
    del_stmt = delete(SemanticMapping).where(SemanticMapping.client_id == client_id)
    res = await session.execute(del_stmt)
    await session.commit()
    return {"status": "success", "deleted_count": res.rowcount}


@router.post("/v2/semantic/extract-sql")
async def extract_sql_from_php(
    payload: SQLExtractRequest,
    api_key: str = Security(api_key_header),
    session: AsyncSession = Depends(get_session)
):
    """
    Uses the configured LLM to extract the exact base SQL query from a raw PHP code snippet.
    Used by the ingestion script to automatically handle complex dynamic filters and soft-deletes.
    This endpoint bypasses admin auth (dependencies=[]) and only requires an X-API-Key.
    """
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    
    client = await get_current_client(api_key=api_key, session=session)
    _, _, raw_llm = await get_brain(client_id=client.id, session=session)
    
    if not raw_llm:
        raise HTTPException(status_code=500, detail="Failed to initialize AI Brain")
    
    sys_prompt = SystemMessage(content='''You are an expert legacy PHP and SQL database engineer. 
Your only job is to analyze the provided PHP controller code and extract the final SQL `SELECT` query it generates.
You MUST include all dynamic `WHERE` clauses (such as is_deleted = 0, status = 'active', etc.) and `JOIN`s that the PHP code builds.
RETURN ONLY THE CLEAN SQL STRING. Do not return markdown, do not return explanations. Just the raw SQL.''')
    
    human_prompt = HumanMessage(content=f"PHP CODE:\n```php\n{payload.php_code}\n```")
    
    try:
        response = await raw_llm.ainvoke([sys_prompt, human_prompt])
        sql = response.content.strip()
        if sql.startswith("```sql"): sql = sql[6:]
        if sql.startswith("```"): sql = sql[3:]
        if sql.endswith("```"): sql = sql[:-3]
        return {"base_query": sql.strip()}
    except Exception as e:
        print(f"Error during LLM SQL extraction: {e}")
        return {"base_query": f"ERROR: {str(e)}"}
