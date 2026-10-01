"""
Query Builder Service — Deterministic SQL generation from structured parameters.

This is the core engine that replaces LLM-generated SQL. It builds SQL queries 
programmatically using the existing metadata models:
- SchemaMetadata → table/column existence validation
- AllowedRelationship → JOIN paths
- FieldMetadata → business term → physical column mapping
- SemanticMetadata → enum CASE WHEN mappings
- SemanticMapping → default filters, UI columns

ZERO LLM involvement. Same input = Same output. Always.

Created: 2026-09-30 as part of the Deterministic QueryBuilder refactor.
"""
import re
import json
import logging
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from sqlalchemy import or_

from app.models.schema_metadata import SchemaMetadata
from app.models.semantic_mapping import SemanticMapping
from app.models.field_metadata import FieldMetadata
from app.models.semantic_metadata import SemanticMetadata
from app.models.allowed_relationship import AllowedRelationship
from app.models.client_config import ClientConfig
from app.services.param_extractor import ExtractedParams
from app.core.context import current_db_url

logger = logging.getLogger(__name__)


# ─── Output Schema ───────────────────────────────────────────────────────────

class QueryResult:
    """Result of a deterministic query build."""
    def __init__(self, sql: str, table_filters: Dict[str, str], display_title: str, is_aggregation: bool = False):
        self.sql = sql
        self.table_filters = table_filters  # For enforce_structural_filters
        self.display_title = display_title
        self.is_aggregation = is_aggregation


# ─── Metadata Loader ─────────────────────────────────────────────────────────

class _TableMeta:
    """Holds all metadata for a single table needed during query building."""
    def __init__(self):
        self.columns: Dict[str, Dict[str, Any]] = {}       # col_name → {type, label, ...}
        self.label_to_column: Dict[str, str] = {}           # lowercase label → col_name
        self.synonym_to_column: Dict[str, str] = {}         # lowercase synonym → col_name
        self.enum_mappings: Dict[str, Dict[str, str]] = {}  # col_name → {int_val: str_label}
        self.primary_date_column: Optional[str] = None
        self.primary_keys: List[str] = []


async def _load_table_metadata(
    table_name: str,
    client_id: int,
    session: AsyncSession
) -> _TableMeta:
    """Load all metadata for a table from the Amoeba metadata stores."""
    meta = _TableMeta()

    # 1. Load FieldMetadata → columns, labels, types
    fm_res = await session.execute(
        select(FieldMetadata).where(
            FieldMetadata.client_id == client_id,
            FieldMetadata.table_name == table_name
        )
    )
    fields = fm_res.scalars().all()

    for fm in fields:
        meta.columns[fm.column_name] = {
            "type": fm.storage_type or "string",
            "label": fm.label,
            "input_type": fm.input_type,
            "is_primary_date": fm.is_primary_date,
            "data_source_table": fm.data_source_table,
            "value_column": fm.value_column,
            "display_column": fm.display_column,
        }
        if fm.label:
            meta.label_to_column[fm.label.lower().strip()] = fm.column_name
        if fm.is_primary_date:
            meta.primary_date_column = fm.column_name
        if fm.synonyms:
            try:
                syns = json.loads(fm.synonyms) if isinstance(fm.synonyms, str) else fm.synonyms
                if isinstance(syns, list):
                    for syn in syns:
                        meta.synonym_to_column[syn.lower().strip()] = fm.column_name
            except Exception:
                pass

    # 2. Load SemanticMetadata → enum mappings + synonyms
    sm_res = await session.execute(
        select(SemanticMetadata).where(
            SemanticMetadata.client_id == client_id,
            SemanticMetadata.table_name == table_name
        )
    )
    semantics = sm_res.scalars().all()

    for sm in semantics:
        if sm.enum_mappings:
            meta.enum_mappings[sm.column_name] = sm.enum_mappings
        if sm.synonyms:
            for syn in sm.synonyms:
                meta.synonym_to_column[syn.lower().strip()] = sm.column_name
        if sm.label:
            meta.label_to_column[sm.label.lower().strip()] = sm.column_name

    # 3. Load SchemaMetadata as supplemental column source
    sm_meta_res = await session.execute(
        select(SchemaMetadata).where(
            SchemaMetadata.client_id == client_id,
            SchemaMetadata.table_name == table_name
        )
    )
    schema_entry = sm_meta_res.scalars().first()
    if schema_entry and schema_entry.columns:
        try:
            cols = json.loads(schema_entry.columns) if isinstance(schema_entry.columns, str) else schema_entry.columns
            if isinstance(cols, list):
                for c in cols:
                    c_name = c.get("name") if isinstance(c, dict) else str(c)
                    if c_name and c_name not in meta.columns:
                        c_type = c.get("type", "string") if isinstance(c, dict) else "string"
                        meta.columns[c_name] = {"type": c_type, "label": c_name.replace("_", " ").title()}
                        if not meta.primary_date_column and any(dk in c_name.lower() for dk in ("date", "created_at", "timestamp")):
                            meta.primary_date_column = c_name
        except Exception:
            pass

    # Heuristic primary date detection if still none found
    if not meta.primary_date_column:
        for col_name, col_info in meta.columns.items():
            if col_info.get("type") in ("date", "datetime") or any(dk in col_name.lower() for dk in ("date", "created_at", "timestamp")):
                meta.primary_date_column = col_name
                break

    return meta


# ─── Column Resolver ─────────────────────────────────────────────────────────

def _resolve_column(
    term: str,
    table_meta: _TableMeta,
    all_field_labels: Optional[Dict[str, Tuple[str, str]]] = None
) -> Optional[str]:
    """
    Resolves a business term or label to a physical column name.
    
    Resolution order:
    1. Exact physical column name match
    2. Label match from FieldMetadata
    3. Synonym match from SemanticMetadata
    4. Fuzzy normalized match (snake_case conversion)
    5. Direct identifier fallback
    """
    if not term:
        return None

    term_lower = term.lower().strip()
    term_normalized = re.sub(r'[^a-z0-9]', '_', term_lower).strip('_')

    # Special handling for "date" synonym
    if term_lower in ("date", "created_at", "time", "doc_date", "document_date"):
        if table_meta.primary_date_column:
            return table_meta.primary_date_column

    # 1. Exact physical column match
    if term_lower in table_meta.columns:
        return term_lower
    if term_normalized in table_meta.columns:
        return term_normalized

    # 2. Label match
    if term_lower in table_meta.label_to_column:
        return table_meta.label_to_column[term_lower]

    # 3. Synonym match
    if term_lower in table_meta.synonym_to_column:
        return table_meta.synonym_to_column[term_lower]

    # 3b. Foreign key suffix check: "city" -> "city_id", "status" -> "status_id"
    if f"{term_lower}_id" in table_meta.columns:
        return f"{term_lower}_id"
    if f"{term_normalized}_id" in table_meta.columns:
        return f"{term_normalized}_id"

    # 4. Fuzzy match — check if normalized form matches a column
    for col_name in table_meta.columns:
        col_normalized = re.sub(r'[^a-z0-9]', '_', col_name.lower())
        if term_normalized == col_normalized:
            return col_name

    # 5. Cross-table label lookup (for joined columns)
    if all_field_labels:
        if term_lower in all_field_labels:
            return all_field_labels[term_lower][1]  # (table_name, col_name)

    # 6. Fallback: if it looks like a clean physical column identifier, return it
    if re.match(r'^[a-zA-Z0-9_]+$', term):
        return term

    return None


# ─── JOIN Builder ─────────────────────────────────────────────────────────────

async def _build_joins(
    base_table: str,
    client_id: int,
    session: AsyncSession,
    requested_columns: Optional[List[str]] = None,
    filter_columns: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Determines which JOINs are needed based on:
    1. AllowedRelationships that are enabled (including multi-hop)
    2. FieldMetadata dropdown references (data_source_table)
    3. Columns requested in SELECT or WHERE that belong to other tables
    
    Returns a list of JOIN definitions: [{table, alias, local_table, on_local, on_remote, columns, fk_column}]
    """
    joins = []
    already_joined = {base_table.lower()}

    # 1. Fetch direct enabled relationships (child_table == base_table)
    rel_res = await session.execute(
        select(AllowedRelationship).where(
            AllowedRelationship.client_id == client_id,
            AllowedRelationship.child_table == base_table,
            AllowedRelationship.is_enabled == True,
            AllowedRelationship.is_restricted == False,
            or_(
                AllowedRelationship.approval_status == "approved",
                AllowedRelationship.approval_status.is_(None)
            )
        )
    )
    relationships = list(rel_res.scalars().all())

    for rel in relationships:
        parent_lower = rel.parent_table.lower()
        if parent_lower in already_joined:
            continue

        selected_cols = rel.selected_columns or []
        if not selected_cols:
            parent_fm_res = await session.execute(
                select(FieldMetadata).where(
                    FieldMetadata.client_id == client_id,
                    FieldMetadata.table_name == rel.parent_table,
                    FieldMetadata.is_visible == True
                )
            )
            parent_fields = parent_fm_res.scalars().all()
            for pf in parent_fields:
                if any(kw in pf.column_name.lower() for kw in ["name", "title", "label", "code"]):
                    selected_cols.append(pf.column_name)
                    break

        joins.append({
            "table": rel.parent_table,
            "alias": rel.parent_table,
            "local_table": base_table,
            "on_local": rel.child_column,
            "on_remote": rel.parent_column,
            "columns": selected_cols,
            "fk_column": rel.child_column
        })
        already_joined.add(parent_lower)

    # 2. Add dropdown FK references from FieldMetadata
    fm_res = await session.execute(
        select(FieldMetadata).where(
            FieldMetadata.client_id == client_id,
            FieldMetadata.table_name == base_table,
            FieldMetadata.data_source_table != None,
            FieldMetadata.data_source_table != ""
        )
    )
    dropdown_fields = fm_res.scalars().all()
    for df in dropdown_fields:
        ds_tbl = df.data_source_table.lower().strip()
        if ds_tbl not in already_joined:
            val_col = df.value_column or "id"
            disp_col = [df.display_column] if df.display_column else []
            joins.append({
                "table": df.data_source_table,
                "alias": df.data_source_table,
                "local_table": base_table,
                "on_local": df.column_name,
                "on_remote": val_col,
                "columns": disp_col,
                "fk_column": df.column_name
            })
            already_joined.add(ds_tbl)

    # 3. Multi-Hop Joins: For each joined table, check if it has parent relationships
    current_joined_tables = [j["table"] for j in list(joins)]
    for parent_table_name in current_joined_tables:
        hop_res = await session.execute(
            select(AllowedRelationship).where(
                AllowedRelationship.client_id == client_id,
                AllowedRelationship.child_table == parent_table_name,
                AllowedRelationship.is_enabled == True,
                AllowedRelationship.is_restricted == False,
                or_(
                    AllowedRelationship.approval_status == "approved",
                    AllowedRelationship.approval_status.is_(None)
                )
            )
        )
        hop_rels = hop_res.scalars().all()
        for h_rel in hop_rels:
            h_parent_lower = h_rel.parent_table.lower()
            if h_parent_lower in already_joined:
                continue

            h_selected_cols = h_rel.selected_columns or []
            if not h_selected_cols:
                h_parent_fm_res = await session.execute(
                    select(FieldMetadata).where(
                        FieldMetadata.client_id == client_id,
                        FieldMetadata.table_name == h_rel.parent_table,
                        FieldMetadata.is_visible == True
                    )
                )
                h_parent_fields = h_parent_fm_res.scalars().all()
                for pf in h_parent_fields:
                    if any(kw in pf.column_name.lower() for kw in ["name", "title", "label", "code"]):
                        h_selected_cols.append(pf.column_name)
                        break

            joins.append({
                "table": h_rel.parent_table,
                "alias": h_rel.parent_table,
                "local_table": parent_table_name,
                "on_local": h_rel.child_column,
                "on_remote": h_rel.parent_column,
                "columns": h_selected_cols,
                "fk_column": h_rel.child_column
            })
            already_joined.add(h_parent_lower)

    return joins


# ─── SQL Builder ─────────────────────────────────────────────────────────────

def _quote_identifier(name: str, dialect: str = "mysql") -> str:
    """Safely quotes a table or column name for the given dialect."""
    if dialect == "mysql":
        return f"`{name}`"
    return f'"{name}"'


def _build_enum_case_when(column_ref: str, mappings: Dict[str, str]) -> str:
    """Builds a CASE WHEN statement to convert integer enums to readable strings."""
    cases = []
    for int_val, str_label in mappings.items():
        cases.append(f"WHEN {column_ref} = {int_val} THEN '{str_label}'")
    return f"CASE {' '.join(cases)} ELSE {column_ref} END"


async def build_query(
    extracted: ExtractedParams,
    client_id: int,
    session: AsyncSession
) -> QueryResult:
    """
    Builds a deterministic SQL query from the extracted parameters.
    
    This is the core function that replaces LLM-generated SQL.
    It uses metadata from:
    - SemanticMapping → for default_filter, display_title
    - FieldMetadata → for label→column resolution
    - AllowedRelationship → for JOINs
    - SemanticMetadata → for enum CASE WHEN mappings
    """
    table_name = extracted.table
    action = extracted.action
    filters = extracted.filters or {}

    # Detect database dialect from connection URL
    client_config = await session.get(ClientConfig, client_id)
    db_url_str = str((client_config.db_connection_url if client_config else "") or current_db_url.get() or "").lower()
    dialect = "mysql" if "mysql" in db_url_str else "postgres"
    q = lambda name: _quote_identifier(name, dialect)

    print(f"[QUERY_BUILDER] Building {action} query for table={table_name}, dialect={dialect}, filters={filters}", flush=True)

    # ─── 1. Load Metadata ────────────────────────────────────────────────────
    table_meta = await _load_table_metadata(table_name, client_id, session)

    # Get SemanticMapping for default filter and display title
    sm_res = await session.execute(
        select(SemanticMapping).where(
            SemanticMapping.client_id == client_id,
            SemanticMapping.database_table == table_name
        )
    )
    semantic_mapping = sm_res.scalars().first()

    # Determine display title
    display_title = table_name.replace("_", " ").title()
    table_filters: Dict[str, str] = {}  # For structural filter enforcement
    if semantic_mapping:
        display_title = semantic_mapping.ui_label.split(",")[0].strip()
        if semantic_mapping.default_filter:
            table_filters[table_name] = semantic_mapping.default_filter

    # ─── 1b. Sanitize Filters vs Requested Columns ───────────────────────────
    # If a filter has value identical to its key (e.g. {"city": "city"}, {"customer": "customer"}),
    # it was a requested column to display, NOT a WHERE value filter!
    clean_filters = {}
    for fk, fv in filters.items():
        if isinstance(fv, str) and fv.lower().strip() in (fk.lower().strip(), f"{fk.lower().strip()}_id", fk.lower().replace("_id", "")):
            if extracted.columns is None:
                extracted.columns = []
            if fk not in extracted.columns:
                extracted.columns.append(fk)
        else:
            clean_filters[fk] = fv
    filters = clean_filters

    # ─── 2. Build JOINs ─────────────────────────────────────────────────────
    joins = await _build_joins(table_name, client_id, session)

    # Load metadata for joined tables too
    joined_metas: Dict[str, _TableMeta] = {}
    for j in joins:
        joined_metas[j["table"]] = await _load_table_metadata(j["table"], client_id, session)

    # ─── 3. Build SELECT Columns ─────────────────────────────────────────────
    select_parts = []
    base_alias = q(table_name)

    if action in ("count", "sum", "avg", "min", "max"):
        if action == "count":
            select_parts.append(f"COUNT(*) AS `Total`")
        elif action in ("sum", "avg", "min", "max"):
            agg_col = extracted.aggregate_column
            if agg_col:
                resolved_col = _resolve_column(agg_col, table_meta)
                if resolved_col:
                    agg_func = action.upper()
                    select_parts.append(f"{agg_func}({base_alias}.{q(resolved_col)}) AS `{action}`")
                else:
                    select_parts.append(f"COUNT(*) AS `Total`")
                    action = "count"
            else:
                select_parts.append(f"COUNT(*) AS `Total`")
                action = "count"

        # Add group_by column to SELECT if present (for count, sum, avg, etc.)
        if extracted.group_by:
            gb_col = _resolve_column(extracted.group_by, table_meta)
            gb_target_alias = base_alias
            gb_label = extracted.group_by.replace("_", " ").title()

            if not gb_col:
                for j in joins:
                    j_meta = joined_metas.get(j["table"])
                    if j_meta:
                        j_gb = _resolve_column(extracted.group_by, j_meta)
                        if j_gb:
                            gb_col = j_gb
                            gb_target_alias = q(j["table"])
                            j_label = j_meta.columns.get(j_gb, {}).get("label", j_gb)
                            gb_label = j_label.replace("_", " ").title()
                            break

            if gb_col:
                # Check if there's an enum mapping for this column
                if gb_target_alias == base_alias and gb_col in table_meta.enum_mappings:
                    case_when = _build_enum_case_when(
                        f"{base_alias}.{q(gb_col)}", table_meta.enum_mappings[gb_col]
                    )
                    select_parts.insert(0, f"{case_when} AS {q(gb_label)}")
                else:
                    select_parts.insert(0, f"{gb_target_alias}.{q(gb_col)} AS {q(gb_label)}")
    else:
        # LIST action — determine which columns to show
        # Always include primary code/number/name and date columns if present
        primary_identifiers = []
        for col_name in table_meta.columns:
            col_low = col_name.lower()
            if any(k in col_low for k in ("number", "code", "no", "name", "title")) and col_low not in ("id", "log_status", "status_id"):
                primary_identifiers.append(col_name)
                break
        if table_meta.primary_date_column and table_meta.primary_date_column not in primary_identifiers:
            primary_identifiers.append(table_meta.primary_date_column)

        if extracted.columns:
            # User requested specific columns or "with X and Y"
            selected_cols = list(primary_identifiers)
            for col_term in extracted.columns:
                resolved = _resolve_column(col_term, table_meta)
                if resolved and resolved not in selected_cols:
                    selected_cols.append(resolved)

            for col_name in selected_cols:
                if col_name in table_meta.columns:
                    # Check if this is a foreign key that can be replaced by joined name
                    joined_match = next((j for j in joins if j.get("on_local") == col_name or j.get("fk_column") == col_name), None)
                    if joined_match:
                        j_meta = joined_metas.get(joined_match["table"])
                        name_col = next((c for c in (j_meta.columns if j_meta else {}) if any(k in c.lower() for k in ("name", "title", "label"))), None)
                        if name_col:
                            fk_label = col_name.replace("_id", "").replace("_", " ").title()
                            select_parts.append(f"{q(joined_match['table'])}.{q(name_col)} AS {q(fk_label)}")
                            continue

                    if col_name in table_meta.enum_mappings:
                        case_when = _build_enum_case_when(
                            f"{base_alias}.{q(col_name)}", table_meta.enum_mappings[col_name]
                        )
                        label = table_meta.columns.get(col_name, {}).get("label", col_name)
                        select_parts.append(f"{case_when} AS {q(label)}")
                    else:
                        label = table_meta.columns.get(col_name, {}).get("label", col_name)
                        select_parts.append(f"{base_alias}.{q(col_name)} AS {q(label)}")
                else:
                    # Check joined tables for this column term
                    for j in joins:
                        j_meta = joined_metas.get(j["table"])
                        if j_meta:
                            j_resolved = _resolve_column(col_term, j_meta)
                            if j_resolved:
                                j_alias = q(j["table"])
                                j_label = j_meta.columns.get(j_resolved, {}).get("label", j_resolved)
                                select_parts.append(f"{j_alias}.{q(j_resolved)} AS {q(j_label)}")
                                break
        else:
            # Default UI Columns from SemanticMapping or visible columns
            ui_columns_str = None
            if semantic_mapping and semantic_mapping.ui_columns:
                raw_ui_cols = re.sub(r'\[Filter:.*?\]', '', semantic_mapping.ui_columns).strip().rstrip(",;")
                ui_column_labels = [c.strip() for c in raw_ui_cols.split(",") if c.strip()]
                ui_columns_str = ui_column_labels

            if ui_columns_str:
                for label in ui_columns_str:
                    resolved = _resolve_column(label, table_meta)
                    if resolved:
                        if resolved in table_meta.enum_mappings:
                            case_when = _build_enum_case_when(
                                f"{base_alias}.{q(resolved)}", table_meta.enum_mappings[resolved]
                            )
                            select_parts.append(f"{case_when} AS {q(label)}")
                        else:
                            select_parts.append(f"{base_alias}.{q(resolved)} AS {q(label)}")
                    else:
                        for j in joins:
                            j_meta = joined_metas.get(j["table"])
                            if j_meta:
                                j_resolved = _resolve_column(label, j_meta)
                                if j_resolved:
                                    j_alias = q(j["table"])
                                    select_parts.append(f"{j_alias}.{q(j_resolved)} AS {q(label)}")
                                    break
            else:
                for col_name, col_info in table_meta.columns.items():
                    if col_name.lower() in ("id", "log_status", "created_by", "updated_by"):
                        continue
                    label = col_info.get("label", col_name)
                    if col_name in table_meta.enum_mappings:
                        case_when = _build_enum_case_when(
                            f"{base_alias}.{q(col_name)}", table_meta.enum_mappings[col_name]
                        )
                        select_parts.append(f"{case_when} AS {q(label)}")
                    else:
                        select_parts.append(f"{base_alias}.{q(col_name)} AS {q(label)}")

            # Add readable name columns from JOINs
            for j in joins:
                for join_col in j.get("columns", []):
                    j_meta = joined_metas.get(j["table"])
                    if j_meta and join_col in j_meta.columns:
                        j_label = j_meta.columns[join_col].get("label", join_col)
                        fk_base = j.get("fk_column", "").replace("_id", "").replace("_", " ").title()
                        alias_label = f"{fk_base} {j_label}" if fk_base else j_label
                        select_parts.append(f"{q(j['table'])}.{q(join_col)} AS {q(alias_label)}")

    # If no columns were resolved at all, fallback to SELECT *
    if not select_parts:
        select_parts = [f"{base_alias}.*"]

    # ─── 4. Build FROM + JOIN clauses ────────────────────────────────────────
    from_clause = f"FROM {q(table_name)}"
    join_clauses = []
    for j in joins:
        local_tbl = j.get("local_table", table_name)
        join_clauses.append(
            f"LEFT JOIN {q(j['table'])} ON {q(local_tbl)}.{q(j['on_local'])} = {q(j['table'])}.{q(j['on_remote'])}"
        )

    # ─── 5. Build WHERE clause ───────────────────────────────────────────────
    where_parts = []

    for filter_key, filter_value in filters.items():
        # Skip internal/meta keys
        if filter_key.startswith("__") or filter_key in ("date_from", "date_to"):
            continue

        # Try to resolve the filter key to a physical column
        resolved_col = _resolve_column(filter_key, table_meta)
        target_table_ref = base_alias

        if not resolved_col:
            # Check joined tables
            for j in joins:
                j_meta = joined_metas.get(j["table"])
                if j_meta:
                    j_resolved = _resolve_column(filter_key, j_meta)
                    if j_resolved:
                        resolved_col = j_resolved
                        target_table_ref = q(j["table"])
                        break

        if not resolved_col:
            print(f"[QUERY_BUILDER] Could not resolve filter key '{filter_key}' to any column. Skipping.", flush=True)
            continue

        col_ref = f"{target_table_ref}.{q(resolved_col)}"

        # Determine the filter type and build the condition
        if isinstance(filter_value, dict) and "op" in filter_value:
            # Operator-based filter: {"op": "contains", "value": "Priya"}
            op = filter_value["op"].lower()
            val = filter_value.get("value", "")
            if op == "contains" or op == "like":
                where_parts.append(f"{col_ref} LIKE '%{_escape_sql(str(val))}%'")
            elif op == "=":
                where_parts.append(f"{col_ref} = '{_escape_sql(str(val))}'")
            elif op == "between" and isinstance(val, list) and len(val) == 2:
                where_parts.append(f"{col_ref} BETWEEN '{_escape_sql(str(val[0]))}' AND '{_escape_sql(str(val[1]))}'")
        elif isinstance(filter_value, (int, float)):
            where_parts.append(f"{col_ref} = {filter_value}")
        elif isinstance(filter_value, str):
            # Determine if this should be exact match or LIKE
            col_type = table_meta.columns.get(resolved_col, {}).get("type", "string")
            if col_type in ("integer", "float", "boolean"):
                # For numeric types, try exact match
                try:
                    where_parts.append(f"{col_ref} = {int(filter_value)}")
                except ValueError:
                    where_parts.append(f"{col_ref} = '{_escape_sql(filter_value)}'")
            else:
                # For string types, use LIKE for flexibility
                where_parts.append(f"{col_ref} LIKE '%{_escape_sql(filter_value)}%'")

    # Handle date filters
    date_from = filters.get("date_from")
    date_to = filters.get("date_to")
    if date_from or date_to:
        date_col = table_meta.primary_date_column
        if not date_col:
            # Try to find a date column heuristically
            for col_name, col_info in table_meta.columns.items():
                if col_info.get("type") in ("date", "datetime") or col_info.get("is_primary_date"):
                    date_col = col_name
                    break
        if not date_col:
            for col_name in table_meta.columns:
                if any(dk in col_name.lower() for dk in ("date", "created_at", "time", "timestamp")):
                    date_col = col_name
                    break
        if not date_col:
            # Standard default date column name
            date_col = "date"

        date_ref = f"{base_alias}.{q(date_col)}"
        if date_from and date_to:
            where_parts.append(f"{date_ref} BETWEEN '{_escape_sql(date_from)}' AND '{_escape_sql(date_to)} 23:59:59'")
        elif date_from:
            where_parts.append(f"{date_ref} >= '{_escape_sql(date_from)}'")
        elif date_to:
            where_parts.append(f"{date_ref} <= '{_escape_sql(date_to)} 23:59:59'")

    # ─── 6. Build ORDER BY ───────────────────────────────────────────────────
    order_clause = ""
    if action == "list":
        if extracted.sort_by:
            sort_col = _resolve_column(extracted.sort_by, table_meta) or extracted.sort_by
            if sort_col:
                direction = (extracted.sort_order or "asc").upper()
                order_clause = f"ORDER BY {base_alias}.{q(sort_col)} {direction}"
        elif table_meta.primary_date_column:
            # Default: order by primary date descending
            order_clause = f"ORDER BY {base_alias}.{q(table_meta.primary_date_column)} DESC"
        elif any(dk in c.lower() for c in table_meta.columns for dk in ("date", "created_at")):
            d_col = next(c for c in table_meta.columns if any(dk in c.lower() for dk in ("date", "created_at")))
            order_clause = f"ORDER BY {base_alias}.{q(d_col)} DESC"

    # ─── 7. Build GROUP BY ───────────────────────────────────────────────────
    group_clause = ""
    if extracted.group_by and action in ("count", "sum", "avg", "min", "max"):
        gb_col = _resolve_column(extracted.group_by, table_meta)
        gb_target_alias = base_alias
        if not gb_col:
            for j in joins:
                j_meta = joined_metas.get(j["table"])
                if j_meta:
                    j_gb = _resolve_column(extracted.group_by, j_meta)
                    if j_gb:
                        gb_col = j_gb
                        gb_target_alias = q(j["table"])
                        break

        if gb_col:
            group_clause = f"GROUP BY {gb_target_alias}.{q(gb_col)}"
            if not order_clause:
                order_clause = "ORDER BY COUNT(*) DESC"

    # ─── 8. Build LIMIT ─────────────────────────────────────────────────────
    limit_clause = ""
    if action == "list":
        limit = extracted.limit or 100  # Default limit
        limit_clause = f"LIMIT {limit}"

    # ─── 9. Assemble the final SQL ───────────────────────────────────────────
    select_str = ", ".join(select_parts)
    sql = f"SELECT {select_str} {from_clause}"

    if join_clauses:
        sql += " " + " ".join(join_clauses)

    if where_parts:
        sql += " WHERE " + " AND ".join(where_parts)

    if group_clause:
        sql += " " + group_clause

    if order_clause:
        sql += " " + order_clause

    if limit_clause:
        sql += " " + limit_clause

    print(f"[QUERY_BUILDER] Generated SQL: {sql}", flush=True)
    logger.info(f"[QUERY_BUILDER] SQL: {sql}")

    is_aggregation = action in ("count", "sum", "avg", "min", "max") and not extracted.group_by

    return QueryResult(
        sql=sql,
        table_filters=table_filters,
        display_title=display_title,
        is_aggregation=is_aggregation
    )


# ─── SQL Escaping ────────────────────────────────────────────────────────────

def _escape_sql(value: str) -> str:
    """Basic SQL string escaping to prevent injection."""
    if not value:
        return value
    return value.replace("'", "''").replace("\\", "\\\\").replace(";", "")


# ─── Full Pipeline (Extract + Build + Execute) ──────────────────────────────

async def execute_deterministic_query(
    user_query: str,
    target_table: str,
    client_id: int,
    session: AsyncSession
) -> Dict[str, Any]:
    """
    Full pipeline: Extract params → Build SQL → Execute → Return results.
    
    Returns the same format as schema_rag_service.query_legacy_db_with_schema():
    {
        "generated_sql": str,
        "records": list,
        "thought_process": str,
        "user_message": str,
        "display_title": str
    }
    
    This makes it a drop-in replacement in execute_read_pipeline.
    """
    # Step 1: Set database context token
    client_config = await session.get(ClientConfig, client_id)
    if not client_config or not client_config.db_connection_url:
        raise Exception("No client database connection configured.")

    token = current_db_url.set(client_config.db_connection_url)
    try:
        # Step 2: Extract structured parameters
        extracted = await extract_params(user_query, client_id, session, target_table)
        print(f"[DETERMINISTIC] Extracted: table={extracted.table} action={extracted.action} filters={extracted.filters}", flush=True)

        # Step 3: Build deterministic SQL
        query_result = await build_query(extracted, client_id, session)
        print(f"[DETERMINISTIC] Built SQL: {query_result.sql}", flush=True)

        # Step 4: Execute the SQL
        records = await execute_sql_query(query_result.sql, table_filters=query_result.table_filters)
    finally:
        current_db_url.reset(token)

    if isinstance(records, str) and "Error" in records:
        print(f"[DETERMINISTIC] SQL execution error: {records}", flush=True)
        return {
            "generated_sql": query_result.sql,
            "records": [{"Error": records}],
            "thought_process": f"Deterministic query failed: {records}",
            "user_message": f"Query encountered an error. The system will retry with the legacy engine.",
            "display_title": query_result.display_title
        }

    # Build user-friendly message for aggregations
    user_message = ""
    if query_result.is_aggregation and records:
        first_row = records[0] if isinstance(records, list) and records else {}
        if isinstance(first_row, dict):
            for key, val in first_row.items():
                agg_label = key.replace("_", " ").title()
                user_message = f"The {agg_label.lower()} is **{val}**."
                break

    return {
        "generated_sql": query_result.sql,
        "records": records if isinstance(records, list) else [],
        "thought_process": f"Deterministic QueryBuilder: table={extracted.table}, action={extracted.action}, filters={extracted.filters}",
        "user_message": user_message,
        "display_title": query_result.display_title
    }
