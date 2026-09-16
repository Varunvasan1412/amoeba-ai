import json
import logging
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.services.llm_service import get_brain
from langchain_core.messages import SystemMessage, HumanMessage
from app.prompts.crud_prompts import get_crud_filter_extraction_prompt, get_crud_generation_prompt
from app.models.field_metadata import FieldMetadata
from app.models.crud_schema import CrudOperation

logger = logging.getLogger(__name__)

class CrudLlmService:
    @staticmethod
    async def _get_field_metadata(session: AsyncSession, client_id: int, table_name: str) -> List[Dict[str, Any]]:
        stmt = select(FieldMetadata).where(
            FieldMetadata.client_id == client_id,
            FieldMetadata.table_name == table_name
        )
        res = await session.execute(stmt)
        return [
            {
                "column_name": f.column_name,
                "data_type": getattr(f, "data_type", getattr(f, "storage_type", "string")),
                "is_required": getattr(f, "is_required", getattr(f, "required", False)),
                "default_value": getattr(f, "default_value", None),
                "synonyms": __import__("json").loads(f.synonyms) if getattr(f, "synonyms", None) else []
            } for f in res.scalars().all()
        ]

    @staticmethod
    async def _invoke_json_llm(client_id: int, session: AsyncSession, prompt: str) -> Optional[Dict[str, Any]]:
        res_brain = await get_brain(client_id, session)
        if not res_brain:
            raise Exception("AI Brain failed to initialize.")
        
        provider = res_brain[1]
        base_llm = res_brain[2]
        
        if not base_llm:
            raise Exception("Base LLM not found.")
            
        # Force JSON mode
        if "OLLAMA" in provider.upper():
            llm = base_llm.bind(format="json")
        else:
            # Assuming OpenAI/Gemini support structured output or JSON mode
            # For simplicity across providers, we can rely on the prompt's strong "OUTPUT ONLY JSON" instructions,
            # but binding json is best for OpenAI if available, or just letting it run.
            llm = base_llm
            
        messages = [SystemMessage(content=prompt)]
        
        try:
            ai_msg = await llm.ainvoke(messages)
            content = ai_msg.content.strip()
            
            # Clean up potential markdown fences
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
                
            return json.loads(content.strip())
        except Exception as e:
            logger.error(f"Failed to generate/parse JSON from LLM: {e}")
            return None

    @staticmethod
    async def extract_filters(client_id: int, session: AsyncSession, action: str, table_name: str, concept: str, user_query: str) -> Dict[str, Any]:
        """
        Extracts search filters from a user query, mapped strictly to FieldMetadata columns.
        """
        field_metadata = await CrudLlmService._get_field_metadata(session, client_id, table_name)
        if not field_metadata:
            return {}
            
        prompt = get_crud_filter_extraction_prompt(action, table_name, concept, user_query, field_metadata)
        
        result = await CrudLlmService._invoke_json_llm(client_id, session, prompt)
        
        if result is None:
            return {}
            
        # Validate that extracted keys are actually in FieldMetadata
        valid_columns = {f["column_name"] for f in field_metadata}
        sanitized_filters = {}
        for k, v in result.items():
            if k in valid_columns:
                sanitized_filters[k] = v
            else:
                logger.warning(f"LLM generated invalid filter key '{k}' for table '{table_name}'. Rejected.")
                
        return sanitized_filters

    @staticmethod
    async def generate_crud_operation(client_id: int, session: AsyncSession, action: str, table_name: str, concept: str, user_query: str, record_id: int = None, record_data: dict = None) -> CrudOperation:
        """
        Generates the CrudOperation JSON representation.
        """
        field_metadata = await CrudLlmService._get_field_metadata(session, client_id, table_name)
        
        prompt = get_crud_generation_prompt(action, table_name, concept, user_query, field_metadata, record_id, record_data)
        
        result = await CrudLlmService._invoke_json_llm(client_id, session, prompt)
        
        if result is None:
            raise Exception("Failed to generate a valid JSON operation.")
            
        return CrudOperation(**result)
