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
            actual_agg_col = table_map.get(self._normalize_key(agg_col_key))
            if actual_agg_col:
                agg_col = getattr(table.c, actual_agg_col)
        
        # Resolve Group By Column
        group_col = None
        if group_by_key:
            actual_group_col = table_map.get(self._normalize_key(group_by_key))
            if actual_group_col:
                group_col = getattr(table.c, actual_group_col)

        select_cols = []
        if group_col is not None:
            select_cols.append(group_col)

        if agg_type == "count":
            select_cols.append(func.count(agg_col if agg_col is not None else text("*")).label("value"))
        elif agg_type == "sum" and agg_col is not None:
            select_cols.append(func.sum(agg_col).label("value"))
        elif agg_type == "avg" and agg_col is not None:
            select_cols.append(func.avg(agg_col).label("value"))
        elif agg_type == "min" and agg_col is not None:
            select_cols.append(func.min(agg_col).label("value"))
        elif agg_type == "max" and agg_col is not None:
            select_cols.append(func.max(agg_col).label("value"))
        else:
            # Fallback for count if no col provided
            select_cols.append(func.count(text("*")).label("value"))
            agg_type = "count"

        stmt = select(*select_cols).select_from(table)
        
        if group_col is not None:
            stmt = stmt.group_by(group_col)
            
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
        select_cols = [table]
        joins = []
        if relationships:
            for rel in relationships:
                try:
                    parent_table = self._get_table(rel.parent_table)
                    if hasattr(table.c, rel.child_column) and hasattr(parent_table.c, rel.parent_column):
                        child_col = getattr(table.c, rel.child_column)
                        parent_col = getattr(parent_table.c, rel.parent_column)
                        joins.append((parent_table, child_col == parent_col))
                        for sel_col in rel.selected_columns:
                            if hasattr(parent_table.c, sel_col):
                                select_cols.append(getattr(parent_table.c, sel_col).label(f"{rel.child_column}_{sel_col}"))
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
        if relationships and isinstance(rows, list):
            for row_dict in rows:
                for rel in relationships:
                    if len(rel.selected_columns) > 0:
                        sel_col = rel.selected_columns[0]
                        label_key = f"{rel.child_column}_{sel_col}"
                        actual_label_key = next((k for k in row_dict.keys() if k.lower() == label_key.lower()), None)
                        if actual_label_key is not None:
                            val = row_dict.pop(actual_label_key)
                            actual_child_key = next((k for k in row_dict.keys() if k.lower() == rel.child_column.lower()), None)
                            if actual_child_key is not None: row_dict[actual_child_key] = val if val is not None else row_dict[actual_child_key]
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
            
            # FORCED CLIENT_ID ENFORCEMENT
            if client_id:
                if filters is None: filters = {}
                filters["client_id"] = client_id

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
