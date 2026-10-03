import re
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
    def _extract_json_from_llm(raw: str) -> Optional[Dict[str, Any]]:
        """
        Robustly extracts and parses JSON from LLM output, handling markdown blocks,
        leading text/thoughts, JS comments, and trailing commas.
        """
        if not raw:
            return None
        text = str(raw).strip()

        # 1. Strip markdown code fences anywhere in the string
        if "```json" in text:
            try:
                text = text.split("```json", 1)[1].split("```", 1)[0].strip()
            except Exception:
                pass
        elif "```" in text:
            try:
                text = text.split("```", 1)[1].split("```", 1)[0].strip()
            except Exception:
                pass

        # 2. Strip JS/C-style line comments (// ...) and block comments (/* ... */)
        text = re.sub(r'//.*?\n', '\n', text)
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)

        # 3. Strip trailing commas before closing braces/brackets
        text = re.sub(r',\s*\}', '}', text)
        text = re.sub(r',\s*\]', ']', text)

        # 4. Direct JSON parsing
        try:
            res = json.loads(text.strip())
            if isinstance(res, dict):
                return res
        except Exception:
            pass

        # 5. Regex extraction for the outer-most {...} block
        m = re.search(r'(\{[\s\S]*\})', text)
        if m:
            cand = m.group(1).strip()
            cand = re.sub(r'//.*?\n', '\n', cand)
            cand = re.sub(r'/\*.*?\*/', '', cand, flags=re.DOTALL)
            cand = re.sub(r',\s*\}', '}', cand)
            cand = re.sub(r',\s*\]', ']', cand)
            try:
                res = json.loads(cand)
                if isinstance(res, dict):
                    return res
            except Exception:
                pass

        return None

    @staticmethod
    async def _get_field_metadata(session: AsyncSession, client_id: int, table_name: str) -> List[Dict[str, Any]]:
        from sqlalchemy import func
        stmt = select(FieldMetadata).where(
            FieldMetadata.client_id == client_id,
            func.lower(FieldMetadata.table_name) == table_name.lower()
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
            
        # Force JSON mode if supported
        if "OLLAMA" in provider.upper():
            llm = base_llm.bind(format="json")
        else:
            llm = base_llm
            
        messages = [SystemMessage(content=prompt)]
        
        try:
            ai_msg = await llm.ainvoke(messages)
            content = ai_msg.content if hasattr(ai_msg, "content") else str(ai_msg)
            parsed = CrudLlmService._extract_json_from_llm(content)
            if parsed is not None:
                return parsed
            raise ValueError(f"Could not parse valid JSON from LLM output: {str(content)[:100]}")
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "rate_limit" in err_str or "tokens per min" in err_str:
                logger.warning("⚠️ OpenAI 429 TPM Rate Limit reached. Auto-retrying with gpt-4o-mini...")
                try:
                    from langchain_openai import ChatOpenAI
                    from app.core.config import settings
                    fallback_llm = ChatOpenAI(
                        model="gpt-4o-mini",
                        api_key=settings.OPENAI_API_KEY,
                        temperature=0.0
                    )
                    ai_msg = await fallback_llm.ainvoke(messages)
                    content = ai_msg.content if hasattr(ai_msg, "content") else str(ai_msg)
                    return CrudLlmService._extract_json_from_llm(content)
                except Exception as fb_err:
                    logger.error(f"Fallback to gpt-4o-mini also failed: {fb_err}")
                    return None
            else:
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
        
        if result is None or not isinstance(result, dict):
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
        
        if result is None or not isinstance(result, dict):
            logger.warning(f"⚠️ [CRUD] LLM returned empty/invalid JSON for {action} on {table_name}. Falling back to clean empty operation.")
            return CrudOperation(
                action=action,
                table=table_name,
                record_id=record_id,
                fields={}
            )
            
        # Ensure mandatory keys exist
        if "action" not in result: result["action"] = action
        if "table" not in result: result["table"] = table_name
        if "fields" not in result or not isinstance(result["fields"], dict): result["fields"] = {}
        if record_id is not None and "record_id" not in result: result["record_id"] = record_id
        
        return CrudOperation(**result)

