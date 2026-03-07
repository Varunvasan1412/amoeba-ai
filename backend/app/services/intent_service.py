import re
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.models.semantic_metadata import SemanticMetadata
from app.services.onboarding import discover_tables
from app.models.client_config import ClientConfig

# Intent keywords
INTENT_MAP = {
    "create": ["add", "create", "new", "insert", "post", "make"],
    "read": ["show", "list", "view", "get", "read", "fetch", "display"],
    "update": ["update", "change", "edit", "modify", "patch", "set"],
    "delete": ["delete", "remove", "destroy", "drop", "terminate"]
}

def normalize_entity_name(name: str) -> str:
    """Removes common prefixes and singularizes basic plurals."""
    name = name.lower().strip()
    # Remove common prefixes
    prefixes = ["mst_", "tbl_", "ref_", "sys_", "api_"]
    for p in prefixes:
        if name.startswith(p):
            name = name[len(p):]
            break
            
    # Simple singularization (basic)
    if name.endswith("ies"):
        name = name[:-3] + "y"
    elif name.endswith("s") and not name.endswith("ss"):
        name = name[:-1]
        
    return name

async def resolve_crud_intent(query: str, client_id: int, session: AsyncSession) -> Optional[Dict[str, Any]]:
    """
    Detects CRUD intent and resolves entity. 
    Returns a structured object if a CRUD keyword is detected, preventing LLM fallback.
    """
    query_lower = query.lower().strip()
    
    # 1. Resolve Intent via Keywords
    detected_intent = None
    for intent, keywords in INTENT_MAP.items():
        for kw in keywords:
            if re.search(rf"\b{kw}\b", query_lower):
                detected_intent = intent
                break
        if detected_intent:
            break
    
    if not detected_intent:
        return None # No CRUD keyword, okay to fall back to LLM

    # 3. Resolve Entity
    client_config = await session.get(ClientConfig, client_id)
    if not client_config:
        return {"intent": detected_intent, "entity": None, "status": "error_no_client"}
        
    try:
        tables = discover_tables(client_config.db_connection_url)
        table_names = [t["name"] for t in tables]
        
        # Get semantic metadata
        statement = select(SemanticMetadata).where(SemanticMetadata.client_id == client_id)
        result = await session.execute(statement)
        semantics = result.scalars().all()
        
        detected_entity = None
        
        # Normalize the query for entity search (remove intent keyword)
        # e.g. "Add customer" -> "customer"
        entity_query = query_lower
        for kw in INTENT_MAP[detected_intent]:
            entity_query = re.sub(rf"\b{kw}\b", "", entity_query).strip()
        
        norm_query = normalize_entity_name(entity_query)

        # Strategy A: Match normalized table names
        for table_name in table_names:
            norm_table = normalize_entity_name(table_name)
            if norm_table == norm_query or norm_table in norm_query or norm_query in norm_table:
                detected_entity = table_name
                break
                
        # Strategy B: Semantic Label/Synonym Match
        if not detected_entity:
            for sem in semantics:
                norm_label = normalize_entity_name(sem.label)
                if norm_label == norm_query or norm_label in norm_query:
                    detected_entity = sem.table_name
                    break
                for syn in (sem.synonyms or []):
                    norm_syn = normalize_entity_name(syn)
                    if norm_syn == norm_query or norm_syn in norm_query:
                        detected_entity = sem.table_name
                        break
                        
        if detected_entity:
            return {
                "intent": detected_intent,
                "entity": detected_entity,
                "status": "resolved"
            }
        else:
            # CRUD Keyword found but entity unknown
            return {
                "intent": detected_intent,
                "entity": None,
                "status": "unresolved_entity",
                "available_entities": table_names[:10] # Suggest some tables
            }
            
    except Exception as e:
        print(f"⚠️ CRUD Intent Resolution Error: {e}")
        return {"intent": detected_intent, "entity": None, "status": "error"}
