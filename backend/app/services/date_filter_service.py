"""
Date Filter Service — Applies natural language date filters to CRUD queries.
Looks up the primary date field from FieldMetadata and injects date-based WHERE clauses.
"""
from typing import Dict, Any, Optional, Tuple
import re
from app.tools.dates import parse_date_range


def get_primary_date_column(table_name: str, client_id: int) -> Optional[str]:
    """
    Looks up the primary date column for a given table from FieldMetadata.
    Uses a sync connection since CRUDBuilder operates synchronously.
    """
    from app.core.config import settings
    from sqlalchemy import create_engine, text

    sync_url = settings.DATABASE_URL
    if "+asyncpg" in sync_url:
        sync_url = sync_url.replace("+asyncpg", "+psycopg2")

    try:
        engine = create_engine(sync_url)
        with engine.connect() as conn:
            # 1. Try to find explicitly marked primary date
            result = conn.execute(text(
                "SELECT column_name FROM field_metadata "
                "WHERE client_id = :cid AND table_name = :tbl AND is_primary_date = TRUE "
                "LIMIT 1"
            ), {"cid": client_id, "tbl": table_name})
            row = result.fetchone()
            if row:
                return row[0]
            
            # 2. FALLBACK: Try to find ANY date column (prioritizing common names)
            result = conn.execute(text(
                "SELECT column_name FROM field_metadata "
                "WHERE client_id = :cid AND table_name = :tbl AND storage_type = 'date' "
                "ORDER BY (CASE WHEN column_name IN ('created_at', 'date', 'entry_date', 'createddate') THEN 0 ELSE 1 END), column_name "
                "LIMIT 1"
            ), {"cid": client_id, "tbl": table_name})
            row = result.fetchone()
            if row:
                return row[0]
                
            # 3. FINAL FALLBACK: Inspect table directly via SQLAlchemy
            from sqlalchemy import inspect as sa_inspect
            inspector = sa_inspect(engine)
            columns = inspector.get_columns(table_name)
            # Prioritize common names
            candidates = ["created_at", "date", "entry_date", "createddate", "updated_at"]
            for cand in candidates:
                if any(c["name"].lower() == cand for c in columns):
                    return next(c["name"] for c in columns if c["name"].lower() == cand)
            
            # Just pick the first date/time column
            for col in columns:
                col_type = str(col["type"]).upper()
                if any(t in col_type for t in ["DATE", "TIME", "TIMESTAMP"]):
                    return col["name"]
                    
    except Exception as e:
        print(f"⚠️ [DATE_FILTER] Failed to lookup primary date column: {e}")

    return None


def apply_smart_filters(
    user_query: str,
    table_name: str,
    client_id: int,
    filters: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
    """
    Parses the user query for dates, limits, and SMART filters (like substrings).
    """
    if filters is None:
        filters = {}

    # 1. APPLY DATE & LIMIT FILTERS (Existing logic)
    filters, start_date, end_date = apply_date_filter_internal(user_query, table_name, client_id, filters)

    # 2. APPLY SMART SUBSTRING FILTERS
    # If the user query has "contains [word]" or similar intent, and NO text filter exists yet
    user_query_lower = user_query.lower()
    
    # Check if we already have a text filter (avoid double filtering)
    has_text_filter = any(isinstance(v, dict) and v.get("op") in ["contains", "like", "ilike"] for v in filters.values())
    
    if not has_text_filter:
        # Heuristic for "contains word" or "[word] items"
        # 1. Explicit: "contains blue", "in which material is blue", "contains the word sleeve"
        # This regex looks for keywords followed by optional fillers (the, word, as) then the actual term
        match = re.search(r'(?:contains|containing|is|labeled|called|word|showing)\s+(?:the\s+)?(?:word\s+)?(?:as\s+)?([a-zA-Z0-9_\-]+)', user_query_lower)
        search_term = None
        if match:
            search_term = match.group(1).strip()
            # Clean up trailing punctuation if any (though regex handles most)
            search_term = re.sub(r'[?.!,]$', '', search_term)
        
        # 2. Implicit: If the query is just a single word or few words and not a date
        elif len(user_query.split()) <= 4 and not any(d in user_query_lower for d in ["yesterday", "today", "last", "records"]):
             search_term = user_query.strip()

        if search_term and len(search_term) > 2:
            # Find the first meaningful text column to apply this search to
            # (In a real system, we'd use Semantic Metadata, but for now we look for 'name' or 'material' or first VARCHAR)
            search_col = get_best_search_column(table_name, client_id)
            if search_col:
                filters[search_col] = {"op": "contains", "value": search_term}
                print(f"🔎 [SMART_FILTER] Auto-applied substring filter: {search_col} CONTAINS '{search_term}'")

    return filters, start_date, end_date

def get_best_search_column(table_name: str, client_id: int) -> Optional[str]:
    """Finds the most logical column to apply a generic 'contains' search to."""
    from sqlalchemy import create_engine, text
    from app.core.config import settings
    
    sync_url = settings.DATABASE_URL.replace("+asyncpg", "+psycopg2")
    try:
        engine = create_engine(sync_url)
        with engine.connect() as conn:
            # Query our internal metadata for this table's columns
            result = conn.execute(text(
                "SELECT column_name FROM field_metadata "
                "WHERE client_id = :cid AND table_name = :tbl AND storage_type IN ('string', 'text', 'varchar') "
                "ORDER BY (CASE "
                "  WHEN column_name IN ('name', 'raw_material', 'product_name', 'title') THEN 0 "
                "  WHEN column_name IN ('label', 'description', 'part_number') THEN 1 "
                "  ELSE 2 END), column_name"
            ), {"cid": client_id, "tbl": table_name})
            
            row = result.fetchone()
            if row:
                return row[0]
                
            # Fallback: if no metadata, we can't safely guess without DB access
    except Exception as e:
        print(f"⚠️ [SMART_FILTER] Metadata lookup failed: {e}")
    
    return None

def apply_date_filter_internal(
    user_query: str,
    table_name: str,
    client_id: int,
    filters: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
    """Legacy date-range and limit extraction."""
    if filters is None:
        filters = {}

    user_query_lower = user_query.lower()

    # --- LIMIT EXTRACTION ---
    limit_match = re.search(r'\b(?:last|first|top|show)?\s*(\d+)\s*(?:records|items|rows|entries)?\b', user_query_lower)
    if limit_match:
        filters["__limit__"] = int(limit_match.group(1))
        print(f"🔢 [DATE_FILTER] Extracted limit: {filters['__limit__']}")

    # --- ORDERING EXTRACTION ---
    if any(word in user_query_lower for word in ["last", "latest", "recent", "newest"]):
        filters["__order__"] = "desc"
    elif "first" in user_query_lower or "oldest" in user_query_lower:
        filters["__order__"] = "asc"

    parsed = parse_date_range(user_query)

    if not parsed["matched"]:
        return filters, None, None

    date_column = get_primary_date_column(table_name, client_id)

    if not date_column:
        print(f"ℹ️ [DATE_FILTER] No primary date field configured for table '{table_name}'.")
        return filters, parsed["start_date"], parsed["end_date"]

    start_date = parsed["start_date"]
    end_date = parsed["end_date"]
    
    if len(end_date) == 10:
        end_date = f"{end_date} 23:59:59"

    filters["__date_column__"] = date_column
    filters["__date_start__"] = start_date
    filters["__date_end__"] = end_date

    return filters, start_date, end_date

# EXPORT under the original name to avoid breaking API but redirect to smart logic
def apply_date_filter(*args, **kwargs):
    return apply_smart_filters(*args, **kwargs)
