import json
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_session
from app.models.client_config import ClientConfig
from app.models.semantic_mapping import SemanticMapping
from app.models.field_metadata import FieldMetadata
from app.security.permission_guard import require_permission
from app.services.onboarding_service import propose_concepts
from sqlalchemy.future import select
from sqlalchemy import create_engine

# Router handles client onboarding status/completion
router = APIRouter(tags=["Onboarding"])

class DBConnectRequest(BaseModel):
    db_url: str

class ConceptApprovalRequest(BaseModel):
    concept_name: str
    table_name: str
    synonyms: List[str]
    relationships: List[Dict[str, Any]]
    fields: List[Dict[str, Any]]

class ActivationRequest(BaseModel):
    assistant_enabled: bool
    operations_enabled: bool

@router.get("/clients/{client_id}/onboarding/status", dependencies=[Depends(require_permission("configure_system"))])
async def get_onboarding_status(
    client_id: int,
    session: AsyncSession = Depends(get_session)
):
    client = await session.get(ClientConfig, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return {
        "onboarding_completed": client.onboarding_completed,
        "assistant_enabled": client.assistant_enabled,
        "operations_enabled": client.operations_enabled
    }

@router.post("/clients/{client_id}/onboarding/connect", dependencies=[Depends(require_permission("configure_system"))])
async def connect_app(
    client_id: int,
    req: DBConnectRequest,
    session: AsyncSession = Depends(get_session)
):
    """Validates connection and saves to ClientConfig."""
    try:
        # Sync test connection
        engine = create_engine(req.db_url, connect_args={"connect_timeout": 10})
        with engine.connect() as conn:
            pass
        engine.dispose()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Database connection failed: {e}")

    client = await session.get(ClientConfig, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
        
    client.db_connection_url = req.db_url
    session.add(client)
    await session.commit()
    
    return {"status": "success", "message": "Connected successfully."}

@router.post("/clients/{client_id}/onboarding/discover", dependencies=[Depends(require_permission("configure_system"))])
async def discover_concepts(
    client_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Introspects schema and proposes business concepts via LLM."""
    client = await session.get(ClientConfig, client_id)
    if not client or not client.db_connection_url:
        raise HTTPException(status_code=400, detail="Database not connected.")
        
    try:
        proposals = await propose_concepts(client_id, session, client.db_connection_url)
        return {"proposals": proposals}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/clients/{client_id}/onboarding/concepts", dependencies=[Depends(require_permission("configure_system"))])
async def save_approved_concept(
    client_id: int,
    req: ConceptApprovalRequest,
    session: AsyncSession = Depends(get_session)
):
    """Saves an approved concept to SemanticMapping and FieldMetadata."""
    
    # 1. Check if concept exists, otherwise create
    stmt = select(SemanticMapping).where(
        SemanticMapping.client_id == client_id,
        SemanticMapping.database_table == req.table_name
    )
    res = await session.execute(stmt)
    mapping = res.scalars().first()
    
    if not mapping:
        mapping = SemanticMapping(
            client_id=client_id,
            ui_label=req.concept_name,
            database_table=req.table_name
        )
        
    mapping.synonyms = json.dumps(req.synonyms)
    mapping.relationships = json.dumps(req.relationships)
    session.add(mapping)
    
    # 2. Process Fields
    # Clear existing fields for simplicity during onboarding
    stmt_del = select(FieldMetadata).where(
        FieldMetadata.client_id == client_id,
        FieldMetadata.table_name == req.table_name
    )
    res_del = await session.execute(stmt_del)
    for existing_f in res_del.scalars().all():
        await session.delete(existing_f)
        
    for f in req.fields:
        field_meta = FieldMetadata(
            client_id=client_id,
            table_name=req.table_name,
            column_name=f["column_name"],
            label=f["label"],
            input_type="text", # default simplified
            storage_type=f.get("type", "string"),
            required=f.get("required", False),
            default_value=f.get("default_value"),
            synonyms=json.dumps(f.get("synonyms", []))
        )
        session.add(field_meta)
        
    await session.commit()
    return {"status": "success", "message": f"Concept {req.concept_name} saved."}

@router.post("/clients/{client_id}/onboarding/activate", dependencies=[Depends(require_permission("configure_system"))])
async def activate_modes(
    client_id: int,
    req: ActivationRequest,
    session: AsyncSession = Depends(get_session)
):
    client = await session.get(ClientConfig, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
        
    client.assistant_enabled = req.assistant_enabled
    client.operations_enabled = req.operations_enabled
    client.onboarding_completed = True
    
    session.add(client)
    await session.commit()
    
    return {"status": "success", "message": "Modes activated successfully."}

class SandboxRequest(BaseModel):
    query: str
    session_id: str

@router.post("/clients/{client_id}/onboarding/sandbox", dependencies=[Depends(require_permission("configure_system"))])
async def sandbox_test(
    client_id: int,
    req: SandboxRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Evaluates the user's query against the configured AST boundary and returns what it understood,
    without executing anything.
    """
    from app.services.intent_service import evaluate_intent
    
    # Run the standard intent evaluation
    intent_data = await evaluate_intent(req.query, client_id, req.session_id, session)
    
    # Return a simplified view for the Sandbox UI
    return {
        "status": "success",
        "understood_ast": {
            "intent": intent_data.get("intent"),
            "target": intent_data.get("label") or intent_data.get("entity"),
            "raw_ast": intent_data
        }
    }
