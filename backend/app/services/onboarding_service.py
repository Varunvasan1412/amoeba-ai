import json
import logging
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.llm_service import get_brain
from app.services.schema_discovery_v2 import discover_full_schema
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

async def propose_concepts(client_id: int, session: AsyncSession, connection_url: str) -> List[Dict[str, Any]]:
    """
    Introspects the physical schema and uses the LLM to propose business concepts, fields, synonyms, and relationships.
    """
    try:
        raw_schema = discover_full_schema(connection_url)
    except Exception as e:
        logger.error(f"Failed to introspect schema: {e}")
        raise ValueError(f"Could not connect or read schema: {e}")

    # Pass the schema to LLM to get business concepts
    res_brain = await get_brain(client_id, session)
    if not res_brain:
        raise Exception("AI Brain failed to initialize.")
        
    provider = res_brain[1]
    base_llm = res_brain[2]
    
    if not base_llm:
        raise Exception("Base LLM not found.")
        
    if "OLLAMA" in provider.upper():
        llm = base_llm.bind(format="json")
    else:
        llm = base_llm

    # Only send a reasonable amount of schema to prevent context overflow.
    # In a real system, we'd chunk this or do it iteratively.
    schema_json = json.dumps(raw_schema)[:15000] 

    prompt = f"""You are Amoeba AI's Onboarding Expert.
Your job is to analyze the provided raw database schema (tables, columns, foreign keys) and translate it into a list of business-friendly App Concepts.

CRITICAL RULES:
1. ONLY return a JSON array of objects. No markdown formatting, no explanations.
2. Ignore metadata tables (like migrations, django_session, auth_group) and audit columns (like created_at, updated_at).
3. Provide simple English business names for tables and columns.
4. If a relationship (foreign key) exists, format it as a simple English sentence in "relationships".

SCHEMA DATA:
{schema_json}

JSON OUTPUT FORMAT:
[
  {{
    "concept_name": "Quotation", // Human readable
    "table_name": "sales_quotation_tbl", // Exact physical name
    "synonyms": ["Quote", "Sales Quote", "Estimate"],
    "fields": [
      {{
        "column_name": "total_amt", // Exact physical name
        "label": "Total Amount", // Human readable
        "type": "number", // string, number, date, boolean
        "synonyms": ["Amount", "Value", "Price"]
      }}
    ],
    "relationships": [
      {{"sentence": "A Quotation belongs to a Customer", "related_concept": "Customer", "foreign_key_col": "customer_id"}}
    ]
  }}
]

OUTPUT ONLY THE JSON ARRAY.
"""
    
    messages = [SystemMessage(content=prompt)]
    
    try:
        ai_msg = await llm.ainvoke(messages)
        content = ai_msg.content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
            
        return json.loads(content.strip())
    except Exception as e:
        logger.error(f"Failed to generate concept proposals: {e}")
        return []
