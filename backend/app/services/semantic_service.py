from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from fastapi import HTTPException

from app.models.semantic_metadata import SemanticMetadata
from app.models.client_config import ClientConfig
from app.services.onboarding import discover_tables
from app.services.audit_service import log_audit
import json

async def auto_map_table_semantics(client_id: int, table_name: str, db_url: str):
    """
    Uses LLM to automatically suggest business labels and synonyms for table columns.
    """
    try:
        # Get raw schema for the table
        real_schema = discover_tables(db_url)
        table_info = next((t for t in real_schema if t["name"] == table_name), None)
        
        if not table_info:
            raise ValueError(f"Table {table_name} not found in database.")
            
        columns = table_info["columns"]
        
        from app.services.llm_service import get_brain
        from langchain_core.messages import SystemMessage, HumanMessage
        
        res_brain = await get_brain(client_id=client_id)
        llm = res_brain[0] if res_brain else None
        if not llm:
            raise ValueError("AI Brain not configured.")
            
        # We unbind tools for this specific prompt to force a JSON response
        llm_no_tools = llm
        if hasattr(llm, "bind_tools"):
             # depending on langchain version, we might just use the underlying model or passing empty tools.
             pass 
             
        prompt = f"""You are an ERP data expert. I have a database table named '{table_name}'.
The columns are: {', '.join(columns)}

Generate a user-friendly 'Business Label' and a list of 'Synonyms' for each column.
Format the output EXACTLY as a JSON array of objects. Do not wrap in markdown blocks like ```json.
Example:
[
  {{"column_name": "customer_id", "label": "Customer Name", "synonyms": ["Client", "Buyer"]}},
  {{"column_name": "created_at", "label": "Created Date", "synonyms": ["Date Added"]}}
]

Output only valid JSON."""

        # Attempt to get LLM response.
        from app.core.config import settings
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_openai import ChatOpenAI
        
        try:
            clean_llm = None
            if settings.AI_PROVIDER.upper() == "GEMINI":
                clean_llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-lite", google_api_key=settings.GOOGLE_API_KEY, temperature=0)
            elif settings.AI_PROVIDER.upper() == "GPT4":
                clean_llm = ChatOpenAI(model="gpt-4-turbo", api_key=settings.OPENAI_API_KEY, temperature=0)
            
            if not clean_llm:
                raise ValueError("No AI provider configured for mapping.")

            res = await clean_llm.ainvoke([SystemMessage(content="You return only JSON."), HumanMessage(content=prompt)])
            
            content = res.content
            if content.startswith("```json"):
                content = content[7:-3].strip()
            elif content.startswith("```"):
                content = content[3:-3].strip()
                
            suggestions = json.loads(content)
        except Exception as ai_err:
            print(f"⚠️ AI Mapping failed (Quota/Connection), using Deterministic Fallback: {ai_err}")
            # Generate deterministic suggestions as fallback
            suggestions = []
            for col in columns:
                label = col.replace("_", " ").title()
                # Basic synonym guessing
                syns = []
                if "id" in col: syns = ["Identifier", "Key"]
                if "amount" in col: syns = ["Value", "Price", "Cost"]
                if "date" in col: syns = ["On", "Timeline"]
                suggestions.append({"column_name": col, "label": label, "synonyms": syns})
        
        # Format for frontend
        results = []
        for col in columns:
            match = next((s for s in suggestions if s.get("column_name") == col), None)
            if match:
                # Detect format based on column name for the fallback/final results
                fmt = "text"
                c_low = col.lower()
                if "date" in c_low: fmt = "date"
                elif any(x in c_low for x in ["amount", "price", "total", "cost", "tax"]): fmt = "currency"
                elif any(x in c_low for x in ["qty", "quantity", "count", "age"]): fmt = "number"
                elif "is_" in c_low or "has_" in c_low or "flag" in c_low: fmt = "boolean"

                results.append({
                    "table_name": table_name,
                    "column_name": col,
                    "label": match.get("label", col.replace("_", " ").title()),
                    "synonyms": match.get("synonyms", []),
                    "data_format": fmt,
                    "is_default_date": fmt == "date"
                })
            else:
                results.append({
                    "table_name": table_name,
                    "column_name": col,
                    "label": col.replace("_", " ").title(),
                    "synonyms": [],
                    "data_format": "text",
                    "is_default_date": False
                })
        return results
    except Exception as e:
        print(f"Auto-Map Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_semantic_schema(session: AsyncSession, client_id: int) -> List[SemanticMetadata]:
    """
    Fetch all semantic mappings for a client.
    """
    statement = select(SemanticMetadata).where(SemanticMetadata.client_id == client_id)
    result = await session.execute(statement)
    return result.scalars().all()

async def get_table_semantics(session: AsyncSession, client_id: int, table_name: str) -> List[SemanticMetadata]:
    """
    Fetch semantic mappings for a specific table.
    """
    statement = select(SemanticMetadata).where(
        SemanticMetadata.client_id == client_id,
        SemanticMetadata.table_name == table_name
    )
    result = await session.execute(statement)
    return result.scalars().all()

async def bulk_upsert_semantics(session: AsyncSession, client_id: int, mappings: List[Dict[str, Any]]):
    """
    Validates and upserts semantic metadata.
    
    Validation:
    1. Table must exist in Client DB.
    2. Column must exist in Client DB Table.
    
    Security:
    - Admin-only (enforced by router).
    - No mapping of ghost columns.
    """
    
    # 1. Fetch Client Config to access DB
    client_config = await session.get(ClientConfig, client_id)
    if not client_config:
        raise HTTPException(status_code=404, detail="Client not found")
        
    # 2. Discover Real Schema (Validation Source of Truth)
    try:
        # Note: discover_tables is synchronous, might block slightly. 
        # In high-load, offload to threadpool. For admin action, it's fine.
        real_schema = discover_tables(client_config.db_connection_url)
        # Convert to fast lookup dict: {"table_name": {"col1", "col2"}}
        schema_map = {
            t["name"]: set(t["columns"]) for t in real_schema
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not validate schema against client database: {str(e)}")

    # 3. Process Mappings
    updated_count = 0
    created_count = 0
    
    for mapping in mappings:
        table_name = mapping.get("table_name")
        column_name = mapping.get("column_name")
        
        # Validation checks
        if table_name not in schema_map:
            raise HTTPException(status_code=400, detail=f"Table '{table_name}' does not exist in the database.")
        
        if column_name not in schema_map[table_name]:
            raise HTTPException(status_code=400, detail=f"Column '{column_name}' does not exist in table '{table_name}'.")

        # Check existing
        statement = select(SemanticMetadata).where(
            SemanticMetadata.client_id == client_id,
            SemanticMetadata.table_name == table_name,
            SemanticMetadata.column_name == column_name
        )
        result = await session.execute(statement)
        existing = result.scalars().first()
        
        if existing is not None:
            # Update
            existing.label = mapping.get("label", existing.label)
            existing.description = mapping.get("description", existing.description)
            existing.synonyms = mapping.get("synonyms", existing.synonyms)
            existing.data_format = mapping.get("data_format", existing.data_format)
            existing.is_pii = mapping.get("is_pii", existing.is_pii)
            existing.is_default_date = mapping.get("is_default_date", existing.is_default_date)
            session.add(existing)
            updated_count += 1
        else:
            # Create
            new_meta = SemanticMetadata(
                client_id=client_id,
                table_name=table_name,
                column_name=column_name,
                label=mapping.get("label"),
                description=mapping.get("description"),
                synonyms=mapping.get("synonyms", []),
                data_format=mapping.get("data_format", "text"),
                is_pii=mapping.get("is_pii", False),
                is_default_date=mapping.get("is_default_date", False)
            )
            session.add(new_meta)
            created_count += 1

    await session.commit()
    
    log_audit(client_id, "semantic_update", {
        "created": created_count,
        "updated": updated_count,
        "tables_touched": list(set(m["table_name"] for m in mappings))
    })
    
    return {"status": "success", "created": created_count, "updated": updated_count}
