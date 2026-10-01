import re
import logging
import json
import time
from typing import List, Dict, Any, Optional, Tuple, Union
from sqlalchemy import create_engine, MetaData, Table, insert, select, update, delete, text, cast, DateTime, Date, Integer, Float, Boolean, String, func, desc, asc
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
from app.core.config import settings
from app.core.context import current_db_url
from app.tools.database import execute_sql_query, execute_sql_write
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class CRUDBuilder:
    def __init__(self, connection_url: str):
        print(f"DEBUG CRUDBuilder INIT URL: {connection_url}", flush=True)
        self.engine = create_engine(connection_url)
        self.metadata = MetaData()
        self.metadata.reflect(bind=self.engine)
        
        # Build fuzzy column map: {normalized_name: actual_name}
        self._column_maps = {} # {table_name: {normalized_key: actual_col_name}}
        for t_name, table in self.metadata.tables.items():
            self._column_maps[t_name] = {
                self._normalize_key(c.name): c.name for c in table.c
            }

    def _normalize_key(self, key: str) -> str:
        """Normalizes a key (e.g. 'Sold Stock' -> 'sold_stock')."""
        if not key: return ""
        k = key.lower().strip()
        k = k.replace(" ", "_").replace("-", "_")
        k = re.sub(r'[^a-z0-9_]', '', k)
        return k

    def _cast_value(self, column, value):
        """Validates and casts input values based on SQLAlchemy column type."""
        try:
            if value is None: return None
            col_type = column.type
            if isinstance(col_type, Integer): return int(value)
            if isinstance(col_type, (Float, String)) and hasattr(col_type, 'python_type') and col_type.python_type in (float, int): return float(value)
            if isinstance(col_type, Boolean):
                if isinstance(value, str): return value.lower() in ("true", "1", "yes")
                return bool(value)
            if isinstance(col_type, (DateTime, Date)):
                 from datetime import datetime
                 if isinstance(value, datetime): return value
                 for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d-%m-%Y"):
                     try: return datetime.strptime(value, fmt)
                     except: continue
            return value
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail=f"Invalid filter value type for column '{column.name}'")

    def _apply_filters(self, stmt, table, filters: Dict[str, Any]) -> Tuple[Any, List[str]]:
        """Internal helper to apply complex operator-based filters."""
        if not filters: return stmt, []
        skipped_filters = []
        table_map = self._column_maps.get(table.name, {})
        for key, filter_val in filters.items():
            if key.startswith("__") and key.endswith("__"): continue
            norm_key = self._normalize_key(key)
            actual_key = table_map.get(norm_key)
            if not actual_key:
                print(f"⚠️ [CRUD] Filter key '{key}' ('{norm_key}') not found in {table.name}.", flush=True)
                skipped_filters.append(key)
                continue
            column = getattr(table.c, actual_key)
            print(f"✅ [CRUD] Applying filter on '{actual_key}' (AI key: '{key}', Type: {column.type})", flush=True)
            if isinstance(filter_val, dict) and "op" in filter_val:
                op = filter_val["op"].lower()
                value = filter_val.get("value")
            else:
                op = "="
                value = filter_val
            if op not in ("in", "not_in", "between", "is_null", "is_not_null"):
                value = self._cast_value(column, value)
            elif op == "between" and isinstance(value, list) and len(value) == 2:
                value = [self._cast_value(column, v) for v in value]
            elif op in ("in", "not_in") and isinstance(value, list):
                value = [self._cast_value(column, v) for v in value]
            try:
                if op == "=": stmt = stmt.where(column == value)
                elif op == "!=": stmt = stmt.where(column != value)
                elif op == ">": stmt = stmt.where(column > value)
                elif op == "<": stmt = stmt.where(column < value)
                elif op == ">=": stmt = stmt.where(column >= value)
                elif op == "<=": stmt = stmt.where(column <= value)
                elif op == "like": stmt = stmt.where(column.like(f"%{value}%"))
                elif op == "ilike" or op == "contains": stmt = stmt.where(column.ilike(f"%{value}%"))
                elif op == "startswith": stmt = stmt.where(column.ilike(f"{value}%"))
                elif op == "endswith": stmt = stmt.where(column.ilike(f"%{value}"))
                elif op == "in": stmt = stmt.where(column.in_(value))
                elif op == "not_in": stmt = stmt.where(~column.in_(value))
                elif op == "between": stmt = stmt.where(column.between(value[0], value[1]))
                elif op == "is_null": stmt = stmt.where(column.is_(None))
                elif op == "is_not_null": stmt = stmt.where(column.is_not(None))
                else: raise HTTPException(status_code=400, detail=f"Unsupported operator: {op}")
                logger.info("FILTER_APPLIED", extra={"table": table.name, "column": column.name, "operator": op, "value": str(value)})
            except Exception as e:
                if isinstance(e, HTTPException): raise e
                raise HTTPException(status_code=400, detail=f"Error applying filter '{op}' on '{key}': {str(e)}")
        return stmt, skipped_filters

    def apply_aggregation(self, table: Table, filters: Dict[str, Any]) -> Tuple[Any, Optional[str]]:
        """
        Builds an aggregation query.
        Returns (stmt, aggregate_key).
        """
        agg_type = filters.get("aggregate", "").lower()
        agg_col_key = filters.get("column")
        group_by_key = filters.get("group_by")
        
        table_map = self._column_maps.get(table.name, {})
        
        # Resolve Aggregation Column
        agg_col = None
        if agg_col_key:
            norm_agg = self._normalize_key(agg_col_key)
            actual_agg_col = table_map.get(norm_agg) or table_map.get(f"{norm_agg}_id")
            if actual_agg_col:
                agg_col = getattr(table.c, actual_agg_col)
        
        # Resolve Group By Column (fuzzy and _id suffix support)
        group_col = None
        if group_by_key:
            norm_gb = self._normalize_key(group_by_key)
            actual_group_col = (
                table_map.get(norm_gb)
                or table_map.get(f"{norm_gb}_id")
                or table_map.get(norm_gb.replace("_id", ""))
            )
            if not actual_group_col:
                for k, col in table_map.items():
                    if norm_gb in k or k in norm_gb:
                        actual_group_col = col
                        break
            if actual_group_col:
                group_col = getattr(table.c, actual_group_col)

        select_cols = []
        join_clause = None
        group_target = group_col
        if group_col is not None:
            gb_label = group_col.name.replace("_id", "").replace("_", " ").title()
            cand_parent = group_col.name[:-3] if group_col.name.endswith("_id") else None
            matched_parent_table = None
            if cand_parent:
                for pt in [cand_parent, f"master_{cand_parent}", f"{cand_parent}s"]:
                    norm_pt = self._normalize_key(pt)
                    for t_key, t_obj in self.metadata.tables.items():
                        if self._normalize_key(t_key) == norm_pt:
                            matched_parent_table = t_obj
                            break
                    if matched_parent_table is not None:
                        break

            if matched_parent_table is not None:
                p_pk = next((c for c in matched_parent_table.c if c.primary_key or c.name in ("id", f"{cand_parent}_id")), None)
                p_name = next((c for c in matched_parent_table.c if any(k in c.name.lower() for k in ("name", "title", "label"))), None)
                if p_pk is not None and p_name is not None:
                    select_cols.append(p_name.label(gb_label))
                    group_target = p_name
                    join_clause = (matched_parent_table, group_col == p_pk)
                else:
                    select_cols.append(group_col.label(gb_label))
            else:
                select_cols.append(group_col.label(gb_label))

        metric_label = "Total" if group_col is not None else "value"
        if agg_type == "count":
            select_cols.append(func.count(agg_col if agg_col is not None else text("*")).label(metric_label))
        elif agg_type == "sum" and agg_col is not None:
            select_cols.append(func.sum(agg_col).label(metric_label))
        elif agg_type == "avg" and agg_col is not None:
            select_cols.append(func.avg(agg_col).label("Average" if group_col is not None else "value"))
        elif agg_type == "min" and agg_col is not None:
            select_cols.append(func.min(agg_col).label("Min" if group_col is not None else "value"))
        elif agg_type == "max" and agg_col is not None:
            select_cols.append(func.max(agg_col).label("Max" if group_col is not None else "value"))
        else:
            select_cols.append(func.count(text("*")).label(metric_label))
            agg_type = "count"

        stmt = select(*select_cols).select_from(table)
        if join_clause:
            stmt = stmt.outerjoin(join_clause[0], join_clause[1])
        if group_target is not None:
            stmt = stmt.group_by(group_target)
            stmt = stmt.order_by(desc(text(metric_label)))
            
        return stmt, agg_type

    def _get_table(self, table_name: str) -> Table:
        if table_name in self.metadata.tables: return self.metadata.tables[table_name]
        norm_name = self._normalize_key(table_name)
        for t in self.metadata.tables.keys():
            if self._normalize_key(t) == norm_name:
                print(f"✅ [CRUD] Fuzzy Table Match: '{table_name}' -> '{t}'", flush=True)
                return self.metadata.tables[t]
        raise ValueError(f"Table '{table_name}' not found in database.")

    async def execute_create(self, table_name: str, data: Dict[str, Any]):
        table = self._get_table(table_name)
        stmt = insert(table).values(**data)
        query = str(stmt.compile(compile_kwargs={"literal_binds": True}, dialect=self.engine.dialect))
        print(f"🔍 [CRUD CREATE SQL] Executing: {query}", flush=True)
        return await execute_sql_write(query)

    async def execute_read(self, table_name: str, filters: Dict[str, Any] = None, limit: int = 10, relationships: List[Any] = None) -> Tuple[List[Dict[str, Any]], List[str]]:
        table = self._get_table(table_name)
        pk_cols = [c.name for c in table.primary_key.columns] if table.primary_key else ["id"]
        primary_pk = pk_cols[0] if pk_cols else "id"

        select_cols = [table]
        joins = []
        resolved_fk_labels: Dict[str, str] = {}

        if relationships:
            for rel in relationships:
                try:
                    # Cardinality Guard (Many-to-One vs One-to-Many):
                    # If rel.child_column is the PK of base_table, parent_table is actually
                    # a 1-to-many child detail collection (e.g. enquiry_detail.enquiry_id = enquiry_header.id).
                    # Never join 1-to-many child detail collections for a flat list query!
                    if rel.child_column.lower() in [pk.lower() for pk in pk_cols] and rel.parent_column.lower() not in ("id", "pk"):
                        print(f"🛡️ [CARDINALITY GUARD] Skipping 1-to-many child collection join {rel.parent_table} to preserve row count", flush=True)
                        continue

                    parent_table = self._get_table(rel.parent_table)
                    if hasattr(table.c, rel.child_column) and hasattr(parent_table.c, rel.parent_column):
                        child_col = getattr(table.c, rel.child_column)
                        parent_col = getattr(parent_table.c, rel.parent_column)
                        joins.append((parent_table, child_col == parent_col))

                        # Generic Display Column Auto-Discovery:
                        sel_cols = list(rel.selected_columns) if rel.selected_columns else []
                        if not sel_cols:
                            for c in parent_table.columns:
                                c_low = c.name.lower()
                                if any(kw in c_low for k in ["name", "title", "label", "status", "mobile", "phone", "stage"]) and not c_low.endswith("_id") and c_low != "id":
                                    sel_cols.append(c.name)
                                    if len(sel_cols) >= 2:
                                        break

                        for sel_col in sel_cols:
                            if hasattr(parent_table.c, sel_col):
                                label_key = f"{rel.child_column}__{sel_col}"
                                select_cols.append(getattr(parent_table.c, sel_col).label(label_key))
                                resolved_fk_labels[label_key] = (rel.child_column, sel_col)
                except Exception as e:
                    print(f"Skipping relationship {rel.child_table}->{rel.parent_table}: {e}", flush=True)
        stmt = select(*select_cols).select_from(table)
        for item in joins:
            try:
                if len(item) != 2: continue
                parent_table, join_cond = item
                stmt = stmt.outerjoin(parent_table, join_cond)
            except Exception as join_err:
                print(f"⚠️ [CRUD] Join error in {table_name}: {join_err}", flush=True)
                continue
        skipped_filters = []
        if filters:
            date_column = filters.pop("__date_column__", None)
            date_start = filters.pop("__date_start__", None)
            date_end = filters.pop("__date_end__", None)
            query_limit = filters.pop("__limit__", limit)
            query_order = filters.pop("__order__", None)
            stmt, skipped_filters = self._apply_filters(stmt, table, filters)
            col_obj = None
            if date_column:
                norm_date_col = self._normalize_key(date_column)
                for c in table.c:
                    if self._normalize_key(c.name) == norm_date_col:
                        col_obj = c
                        break
            if col_obj is not None and date_start and date_end:
                stmt = stmt.where(col_obj >= date_start)
                stmt = stmt.where(col_obj <= date_end)
                if not query_order: stmt = stmt.order_by(col_obj.desc())
            if query_order:
                order_col = col_obj
                if not order_col:
                    from sqlalchemy import inspect as sa_inspect
                    pk_cols = sa_inspect(self.engine).get_pk_constraint(table.name).get("constrained_columns", [])
                    if pk_cols: order_col = getattr(table.c, pk_cols[0])
                if order_col is not None:
                    if query_order == "desc": stmt = stmt.order_by(order_col.desc())
                    else: stmt = stmt.order_by(order_col.asc())
            stmt = stmt.limit(query_limit)
        else:
            stmt = stmt.limit(limit)

        # Handle Aggregation Branch
        if filters and "aggregate" in filters:
            agg_stmt, agg_type = self.apply_aggregation(table, filters)
            # Re-apply filters to the aggregation statement
            agg_stmt, _ = self._apply_filters(agg_stmt, table, filters)
            
            # Re-apply date filters if present
            if col_obj is not None and date_start and date_end:
                agg_stmt = agg_stmt.where(col_obj >= date_start)
                agg_stmt = agg_stmt.where(col_obj <= date_end)
            
            # Re-apply Ordering / Limit to aggregate results
            if filters.get("limit"):
                agg_stmt = agg_stmt.limit(filters["limit"])
            
            if filters.get("order_by") == "desc":
                agg_stmt = agg_stmt.order_by(desc(text("value")))
            elif filters.get("order_by") == "asc":
                agg_stmt = agg_stmt.order_by(asc(text("value")))

            stmt = agg_stmt

        query = str(stmt.compile(compile_kwargs={"literal_binds": True}, dialect=self.engine.dialect))
        print(f"🔍 [CRUD READ SQL] Executing Query: {query}", flush=True)
        rows = await execute_sql_query(query)
        if isinstance(rows, str) and "Error" in rows: raise Exception(rows)

        # Deduplicate records by primary key so each parent entity is guaranteed unique
        if isinstance(rows, list) and primary_pk:
            seen_pks = set()
            deduped_rows = []
            for r in rows:
                if isinstance(r, dict) and primary_pk in r:
                    pk_val = r[primary_pk]
                    if pk_val not in seen_pks:
                        seen_pks.add(pk_val)
                        deduped_rows.append(r)
                else:
                    deduped_rows.append(r)
            rows = deduped_rows

        # Generic FK Value & Label Resolution:
        if isinstance(rows, list):
            for row_dict in rows:
                for label_key, (child_col, sel_col) in resolved_fk_labels.items():
                    if label_key in row_dict:
                        val = row_dict.pop(label_key)
                        if val is not None:
                            # Primary descriptor (e.g. name, title, label, status) replaces foreign key
                            if any(k in sel_col.lower() for k in ["name", "title", "label", "status", "stage"]):
                                row_dict[child_col] = val
                            else:
                                # Additional attribute (e.g. mobile, phone, code) is added as its own column
                                row_dict[sel_col] = val
        return rows, skipped_filters

    async def execute_update(self, table_name: str, filters: Dict[str, Any], data: Dict[str, Any]):
        table = self._get_table(table_name)
        stmt = update(table)
        stmt, skipped = self._apply_filters(stmt, table, filters)
        stmt = stmt.values(**data)
        query = str(stmt.compile(compile_kwargs={"literal_binds": True}, dialect=self.engine.dialect))
        print(f"🔍 [CRUD UPDATE SQL] Executing: {query}", flush=True)
        return await execute_sql_write(query)

    async def execute_delete(self, table_name: str, filters: Dict[str, Any]):
        if not filters: raise ValueError("Mass delete without filters is blocked for safety.")
        table = self._get_table(table_name)
        stmt = delete(table)
        stmt, skipped = self._apply_filters(stmt, table, filters)
        query = str(stmt.compile(compile_kwargs={"literal_binds": True}, dialect=self.engine.dialect))
        print(f"🔍 [CRUD DELETE SQL] Executing: {query}", flush=True)
        return await execute_sql_write(query)

from app.services.audit_service import log_event

class CRUDService:
    @staticmethod
    def get_builder() -> CRUDBuilder:
        url = current_db_url.get()
        if not url: url = settings.DATABASE_URL
        sync_url = url
        if sync_url.startswith("postgresql+asyncpg://"): sync_url = sync_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
        elif sync_url.startswith("postgresql://"): sync_url = sync_url.replace("postgresql://", "postgresql+psycopg2://")
        elif sync_url.startswith("mysql+aiomysql://"): sync_url = sync_url.replace("mysql+aiomysql://", "mysql+pymysql://")
        elif sync_url.startswith("mysql://"): sync_url = sync_url.replace("mysql://", "mysql+pymysql://")
        return CRUDBuilder(sync_url)

    @staticmethod
    async def create_record(table_name: str, data: Dict[str, Any], user_id: Optional[str] = None, client_id: Optional[int] = None):
        try:
            builder = CRUDService.get_builder()
            record_id = await builder.execute_create(table_name, data)
            log_event(client_id=client_id, user_id=user_id, action="CREATE", entity=table_name, table_name=table_name, record_id=str(record_id), status="SUCCESS", details=data)
            return record_id
        except Exception as e:
            raise Exception(f"Failed to create record: {e}")

    @staticmethod
    async def read_records(table_name: str, filters: Optional[Dict[str, Any]] = None, limit: int = 1000, user_id: Optional[str] = None, client_id: Optional[int] = None, user_query: Optional[str] = None) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        try:
            builder = CRUDService.get_builder()
            start_time = time.time()
            
            if user_query and client_id:
                from app.services.date_filter_service import apply_date_filter
                filters, _, _ = apply_date_filter(user_query, table_name, client_id, filters)
            
            relationships = []
            if client_id:
                from app.core.database import async_session
                from app.models.allowed_relationship import AllowedRelationship
                from sqlmodel import select as sm_select
                async with async_session() as session:
                    stmt = sm_select(AllowedRelationship).where(AllowedRelationship.client_id == client_id, AllowedRelationship.child_table == table_name)
                    res = await session.execute(stmt)
                    relationships = res.scalars().all()
            
            # Execute read on client database
            records, skipped = await builder.execute_read(table_name, filters, limit, relationships=relationships)
            
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            # Logging Aggregation specifically
            if filters.get("aggregate"):
                log_event(
                    client_id=client_id,
                    user_id=user_id,
                    action="AGGREGATION_EXECUTED",
                    table_name=table_name,
                    details={
                        "aggregate": filters["aggregate"],
                        "column": filters.get("column"),
                        "group_by": filters.get("group_by"),
                        "limit": filters.get("limit"),
                        "execution_time_ms": execution_time_ms
                    }
                )
                if execution_time_ms > 2000:
                    print(f"⚠️ [PERFORMANCE] Slow aggregation detected on {table_name}: {execution_time_ms}ms")

            # Format result according to request structure
            if filters.get("aggregate") and not filters.get("group_by"):
                # Single value result
                val = records[0]["value"] if records and "value" in records[0] else 0
                return {
                    "aggregate": filters["aggregate"],
                    "value": val
                }
            elif filters.get("aggregate") and filters.get("group_by"):
                # Grouped result
                return {
                    "grouped_results": records
                }

            # Generic Column Projection & Cleaning:
            if isinstance(records, list) and records:
                records = CRUDService.project_clean_columns(records, user_query=user_query)

            # If there are skipped filters, return a diagnostic object instead of just a list
            if skipped:
                return {
                    "records": records,
                    "warnings": f"The following filter keys were not found and were ignored: {skipped}. Please check the database schema using tool_inspect_database to ensure correct column names."
                }
            return records
        except Exception as e:
            raise Exception(f"Failed to read records: {e}")

    @staticmethod
    def project_clean_columns(records: List[Dict[str, Any]], user_query: Optional[str] = None) -> List[Dict[str, Any]]:
        if not records or not isinstance(records, list) or not isinstance(records[0], dict):
            return records

        all_keys = list(records[0].keys())
        query_lower = (user_query or "").lower()

        # 1. Detect requested columns from user query projection clause
        # Patterns like: "showing customer name, mobile, and current stage", "with X and Y", "displaying X"
        requested_terms = []
        proj_match = re.search(r'\b(?:showing|displaying|with|including|columns?)\s+([a-zA-Z0-9_,\s]+)', query_lower)
        if proj_match:
            raw_clause = proj_match.group(1).strip()
            for stop in ["where", "order", "sort", "limit", "group", "having"]:
                if f" {stop} " in f" {raw_clause} ":
                    raw_clause = raw_clause.split(f" {stop} ")[0]
            raw_clause = re.sub(r'\b(?:and|as\s+well\s+as)\b', ',', raw_clause)
            requested_terms = [t.strip().lower() for t in raw_clause.split(',') if t.strip() and len(t.strip()) > 1]

        # 2. Identify Primary Identifier column(s) (e.g., number, code, name, no)
        primary_id_cols = []
        for k in all_keys:
            kl = k.lower()
            if any(id_word in kl for id_word in ["number", "code", "no", "name", "title"]) and kl not in ("id", "log_status", "status_id") and not kl.endswith("_id"):
                primary_id_cols.append(k)
                break
        if not primary_id_cols:
            for k in all_keys:
                if k.lower() in ("id", "code", "number", "name"):
                    primary_id_cols.append(k)
                    break

        # 3. Identify Primary Date column(s)
        primary_date_cols = []
        for k in all_keys:
            kl = k.lower()
            if any(dw in kl for dw in ["date", "created_at", "timestamp"]) and k not in primary_id_cols:
                primary_date_cols.append(k)
                break

        final_cols = []
        if requested_terms:
            # Add primary identifier and date first for context
            for c in primary_id_cols:
                if c not in final_cols:
                    final_cols.append(c)
            for c in primary_date_cols:
                if c not in final_cols:
                    final_cols.append(c)

            # Match each requested term to available keys in records
            for term in requested_terms:
                term_clean = re.sub(r'[^a-z0-9]', '', term)
                matched_key = None
                
                # Check exact match or normalized match
                for k in all_keys:
                    k_clean = re.sub(r'[^a-z0-9]', '', k.lower())
                    if term_clean == k_clean or k_clean.startswith(term_clean):
                        matched_key = k
                        break

                # Check token overlap / fuzzy match (e.g., "customer name" -> "customer_id", "current stage" -> "enquiry_status_id")
                if not matched_key:
                    term_words = [w for w in term.split() if w not in ("current", "the", "a", "an", "all", "is", "of")]
                    for k in all_keys:
                        kl = k.lower()
                        if any(w in kl for w in term_words):
                            matched_key = k
                            break

                if matched_key and matched_key not in final_cols:
                    final_cols.append(matched_key)
        else:
            # Default projection: exclude technical internal columns
            noisy_cols = {"id", "log_status", "created_by", "updated_by", "deleted_at", "deleted", "sync_status", "raw_data"}
            for k in all_keys:
                kl = k.lower()
                if kl in noisy_cols or kl.startswith("temp_") or kl.startswith("__"):
                    continue
                # If date column already present, omit redundant created_at timestamp
                if primary_date_cols and kl in ("created_at", "updated_at") and kl not in primary_date_cols:
                    continue
                final_cols.append(k)

            # Limit to reasonable width if there are still too many columns
            if len(final_cols) > 12:
                final_cols = final_cols[:12]

        if not final_cols:
            final_cols = all_keys

        # Format column names to clean, human-readable Title Case
        clean_records = []
        for r in records:
            clean_row = {}
            for col in final_cols:
                if col in r:
                    val = r[col]
                    # Format column header label
                    label = col.replace("_id", "").replace("_", " ").title()
                    if "status" in col.lower() or "stage" in col.lower():
                        label = "Stage" if "stage" in query_lower else "Status"
                    clean_row[label] = val
            clean_records.append(clean_row)

        return clean_records

    @staticmethod
    async def update_records(table_name: str, filters: Dict[str, Any], data: Dict[str, Any], user_id: Optional[str] = None, client_id: Optional[int] = None):
        try:
            builder = CRUDService.get_builder()
            return await builder.execute_update(table_name, filters, data)
        except Exception as e:
            raise Exception(f"Failed to update records: {e}")

    @staticmethod
    async def delete_records(table_name: str, filters: Dict[str, Any], user_id: Optional[str] = None, client_id: Optional[int] = None):
        try:
            builder = CRUDService.get_builder()
            return await builder.execute_delete(table_name, filters)
        except Exception as e:
            raise Exception(f"Failed to delete records: {e}")

    @staticmethod
    def get_table_columns(table_name: str) -> List[str]:
        try:
            builder = CRUDService.get_builder()
            table = builder._get_table(table_name)
            return [c.name for c in table.columns]
        except Exception:
            return []
