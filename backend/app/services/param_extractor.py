"""
Param Extractor — Thin LLM layer for structured parameter extraction.

The LLM does NOT write SQL. It only extracts:
- Which table the user is asking about
- What action (list, count, sum, avg, min, max)
- What filters (WHERE conditions as key-value pairs)
- Which columns to display
- Sort order and limit

Created: 2026-09-30 as part of the Deterministic QueryBuilder refactor.
"""
import os
import json
import re
import logging
from typing import Optional, Dict, Any, List, Literal
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.schema_metadata import SchemaMetadata
from app.models.semantic_mapping import SemanticMapping
from app.models.field_metadata import FieldMetadata
from app.models.semantic_metadata import SemanticMetadata
from app.models.client_config import ClientConfig
from app.core.config import settings

logger = logging.getLogger(__name__)


# ─── Output Schema ───────────────────────────────────────────────────────────

class ExtractedParams(BaseModel):
    """Structured output from the parameter extractor."""
    table: str = Field(..., description="The physical database table name")
    action: Literal["list", "count", "sum", "avg", "min", "max"] = Field(
        default="list", description="What to do: list records, count them, or aggregate"
    )
    filters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Key-value pairs for WHERE conditions. Keys are physical column names or business labels."
    )
    columns: Optional[List[str]] = Field(
        default=None,
        description="Columns to include in SELECT. None = use defaults from SemanticMapping."
    )
    sort_by: Optional[str] = Field(default=None, description="Column to sort by")
    sort_order: Optional[Literal["asc", "desc"]] = Field(default=None, description="Sort direction")
    aggregate_column: Optional[str] = Field(
        default=None, description="For sum/avg/min/max: which column to aggregate"
    )
    limit: Optional[int] = Field(default=None, description="Max records to return")
    group_by: Optional[str] = Field(default=None, description="Column to group by for aggregations")
    confidence: float = Field(default=1.0, description="Extraction confidence 0.0-1.0")


# ─── Metadata Collector ──────────────────────────────────────────────────────

async def _build_context_for_llm(
    client_id: int,
    session: AsyncSession,
    target_table: Optional[str] = None
) -> str:
    """
    Builds a concise context string describing available tables, columns, and 
    business-term mappings for the LLM to reference during parameter extraction.
    
    This is intentionally much smaller than the schema_rag_service prompt — 
    we only need enough for the LLM to identify WHAT the user wants, not HOW to query it.
    """
    parts = []

    # 1. Semantic Mappings: UI labels → tables
    sm_res = await session.execute(
        select(SemanticMapping).where(SemanticMapping.client_id == client_id)
    )
    all_sms = sm_res.scalars().all()

    if all_sms:
        parts.append("AVAILABLE TABLES (UI Label → Physical Table):")
        for sm in all_sms:
            line = f"- \"{sm.ui_label}\" → table `{sm.database_table}`"
            if sm.synonyms:
                try:
                    syns = json.loads(sm.synonyms) if isinstance(sm.synonyms, str) else sm.synonyms
                    if syns:
                        line += f" (also known as: {', '.join(syns)})"
                except Exception:
                    pass
            parts.append(line)

    # 2. Field Metadata: business term → physical column (for the target table + related tables)
    fm_res = await session.execute(
        select(FieldMetadata).where(
            FieldMetadata.client_id == client_id,
            FieldMetadata.label != None,
            FieldMetadata.label != ""
        )
    )
    all_fields = fm_res.scalars().all()

    if all_fields:
        # Group by table for clarity
        table_fields: Dict[str, List[str]] = {}
        for fm in all_fields:
            key = fm.table_name
            if key not in table_fields:
                table_fields[key] = []
            type_hint = f" ({fm.storage_type})" if fm.storage_type else ""
            table_fields[key].append(f'"{fm.label}" → `{fm.column_name}`{type_hint}')

        parts.append("\nFIELD MAPPINGS (Business Term → Physical Column):")
        # Prioritize the target table
        if target_table and target_table in table_fields:
            parts.append(f"  Table `{target_table}` (PRIMARY):")
            for f in table_fields[target_table]:
                parts.append(f"    - {f}")

        for tbl, fields in table_fields.items():
            if tbl == target_table:
                continue
            parts.append(f"  Table `{tbl}`:")
            for f in fields[:15]:  # Cap at 15 fields per table to keep prompt small
                parts.append(f"    - {f}")

    # 3. Enum mappings (so LLM knows status=1 means "Active")
    enum_res = await session.execute(
        select(SemanticMetadata).where(
            SemanticMetadata.client_id == client_id,
            SemanticMetadata.enum_mappings != None
        )
    )
    enum_metadata = enum_res.scalars().all()

    if enum_metadata:
        parts.append("\nENUM MAPPINGS:")
        for em in enum_metadata:
            if em.enum_mappings:
                map_str = ", ".join([f"{k}='{v}'" for k, v in em.enum_mappings.items()])
                parts.append(f"- `{em.table_name}`.`{em.column_name}`: {map_str}")

    return "\n".join(parts)


# ─── LLM Extraction ─────────────────────────────────────────────────────────

async def extract_params(
    user_query: str,
    client_id: int,
    session: AsyncSession,
    target_table: Optional[str] = None
) -> ExtractedParams:
    """
    Extracts structured query parameters from a natural language question.
    
    The LLM receives:
    1. A simple, focused system prompt (~50 lines, not 400)
    2. Available tables and field mappings
    3. The user's question
    
    And returns ONLY structured JSON — no SQL.
    
    Falls back to keyword-based extraction if LLM call fails.
    """
    openai_key = os.getenv("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", None)

    # Build metadata context for the LLM
    context = await _build_context_for_llm(client_id, session, target_table)

    system_prompt = f"""You are a parameter extractor for a database query system.
Given a user's natural language question, extract the structured parameters needed to build a query.

RULES:
1. Output ONLY valid JSON matching the schema below. No markdown, no explanations.
2. Use the FIELD MAPPINGS to convert business terms to physical column names in filters.
3. For "action": use "list" for listing records, "count" for counting, "sum"/"avg"/"min"/"max" for aggregations.
4. For "filters": ONLY include actual filtering criteria where a specific VALUE is provided by the user.
   - Example: "quotations by John in Mumbai" -> filters: {{"customer_id": "John", "city_id": "Mumbai"}}
   - Example: "where status is pending" -> filters: {{"status": 1}}
   - Date filters should use "date_from" and "date_to" keys with YYYY-MM-DD format.
5. CRITICAL: "with <field1> and <field2>" (e.g. "with customer and city") means the user wants to see those COLUMNS in the output! Put them in "columns": ["customer_id", "city_id"] and leave "filters": {{}}! Do NOT filter by city or customer unless a specific name/value is given!
6. CRITICAL: "by <field>" or "grouped by <field>" or "per <field>" (e.g. "count customers by city") means GROUP BY aggregation! Put "group_by": "city_id", "action": "count", and leave "filters": {{}}!
7. For "aggregate_column": only set this for sum/avg/min/max actions — the physical column to aggregate.
8. The system has already guessed the target table is: '{target_table or "unknown"}'. Verify this against the available tables.
9. For "limit": extract if user says "top 5", "last 10", etc. Default to null (system will apply default limit).
10. For date parsing:
   - "this month" → date_from: first day of current month, date_to: today
   - "September" or "September 2026" → date_from: 2026-09-01, date_to: 2026-09-30
   - "last month" → previous month's date range
   - "today" → today's date for both date_from and date_to
   - "yesterday" → yesterday's date for both
   - Current date context: The current date is provided in the user query context.

{context}

JSON OUTPUT SCHEMA:
{{
  "table": "physical_table_name",
  "action": "list|count|sum|avg|min|max",
  "filters": {{"column_name": "value", "date_from": "YYYY-MM-DD", "date_to": "YYYY-MM-DD"}},
  "columns": ["col1", "col2"] or null,
  "sort_by": "column_name" or null,
  "sort_order": "asc|desc" or null,
  "aggregate_column": "column_name" or null,
  "group_by": "column_name" or null,
  "limit": number or null
}}
"""

    # Try LLM extraction first
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage

        llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=openai_key,
            temperature=0  # Deterministic extraction
        )

        # Add current date context to user query
        from datetime import datetime
        date_context = f" (Current date: {datetime.now().strftime('%Y-%m-%d')})"

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_query + date_context)
        ]

        response = await llm.ainvoke(messages)
        raw = response.content.strip()

        # Clean up markdown formatting if present
        if raw.startswith("```json"):
            raw = raw[7:]
        if raw.startswith("```"):
            raw = raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        parsed = json.loads(raw)

        # Ensure table falls back to target_table if not provided
        if not parsed.get("table") and target_table:
            parsed["table"] = target_table

        result = ExtractedParams(
            table=parsed.get("table", target_table or ""),
            action=parsed.get("action", "list"),
            filters=parsed.get("filters", {}),
            columns=parsed.get("columns"),
            sort_by=parsed.get("sort_by"),
            sort_order=parsed.get("sort_order"),
            aggregate_column=parsed.get("aggregate_column"),
            limit=parsed.get("limit"),
            group_by=parsed.get("group_by"),
            confidence=0.95  # LLM extraction confidence
        )

        logger.info(f"[PARAM_EXTRACTOR] Extracted params: {result.model_dump_json()}")
        print(f"[PARAM_EXTRACTOR] table={result.table} action={result.action} filters={result.filters}", flush=True)
        return result

    except json.JSONDecodeError as jde:
        logger.warning(f"[PARAM_EXTRACTOR] LLM returned non-JSON: {raw[:200]}. Falling back to keyword extraction.")
        print(f"[PARAM_EXTRACTOR] JSON parse failed: {jde}", flush=True)
    except Exception as e:
        logger.warning(f"[PARAM_EXTRACTOR] LLM call failed: {e}. Falling back to keyword extraction.")
        print(f"[PARAM_EXTRACTOR] LLM extraction failed: {e}", flush=True)

    # ─── Fallback: Keyword-based extraction ──────────────────────────────────
    return _keyword_fallback(user_query, target_table)


# ─── Keyword Fallback ────────────────────────────────────────────────────────

def _keyword_fallback(user_query: str, target_table: Optional[str] = None) -> ExtractedParams:
    """
    Simple keyword-based extraction as a safety net when LLM is unavailable.
    This handles basic patterns like "how many X", "show all X", "list X".
    """
    query_lower = user_query.lower().strip()

    # Detect action
    action = "list"
    aggregate_column = None

    if any(kw in query_lower for kw in ["how many", "count", "number of", "total number"]):
        action = "count"
    elif any(kw in query_lower for kw in ["total value", "total amount", "sum of", "sum total"]):
        action = "sum"
    elif any(kw in query_lower for kw in ["average", "avg of", "mean of"]):
        action = "avg"

    # Detect limit
    limit = None
    limit_match = re.search(r'\b(?:last|first|top|show)\s*(\d+)\b', query_lower)
    if limit_match:
        limit = int(limit_match.group(1))

    # Detect sort
    # Detect group_by
    group_by = None
    gb_match = re.search(r'\b(?:grouped\s+by|group\s+by|by|per)\s+([a-zA-Z0-9_]+)\b', query_lower)
    if gb_match:
        cand_gb = gb_match.group(1).lower().strip()
        if cand_gb not in ("all", "the", "a", "an", "and", "or", "desc", "asc", "date", "created_at"):
            group_by = cand_gb

    return ExtractedParams(
        table=target_table or "",
        action=action,
        filters={},
        columns=None,
        sort_by=None,
        sort_order=None,
        aggregate_column=aggregate_column,
        limit=limit,
        group_by=group_by,
        confidence=0.5  # Low confidence for keyword fallback
    )
