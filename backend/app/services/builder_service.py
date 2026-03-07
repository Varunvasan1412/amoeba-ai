from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
from fastapi import HTTPException
from sqlmodel import select
from app.models.semantic_metadata import SemanticMetadata
from app.services.schema_discovery_v2 import discover_full_schema
from app.models.client_config import ClientConfig
from datetime import datetime, timedelta


from app.services.relationship_service import get_relationship_graph, validate_join_path

async def generate_safe_sql(session: AsyncSession, client_id: int, request: Dict[str, Any]) -> str:
    """
    Generates deterministic SQL for reports. Supports SINGLE table and JOINED tables.
    Supports qualified labels (table:label) to avoid ambiguity.
    """
    print(f"DEBUG: Generating SQL for Client {client_id}. Request: {request}", flush=True)
    # 1. Fetch Client Config
    client_config = (await session.execute(select(ClientConfig).where(ClientConfig.id == client_id))).scalars().first()
    if not client_config:
        raise HTTPException(status_code=404, detail="Client not found")
        
    import asyncio
    loop = asyncio.get_event_loop()
    sync_url = client_config.db_connection_url.replace("+asyncpg", "")
    
    # 2. Extract Validated Semantic Map (Label -> Metadata) for ALL tables
    stmt = select(SemanticMetadata).where(SemanticMetadata.client_id == client_id)
    metadata_list = (await session.execute(stmt)).scalars().all()
    
    label_to_metas = {}
    for m in metadata_list:
        if m.label not in label_to_metas:
            label_to_metas[m.label] = []
        label_to_metas[m.label].append(m)
        if m.synonyms:
            for syn in m.synonyms:
                if syn not in label_to_metas:
                    label_to_metas[syn] = []
                label_to_metas[syn].append(m)

    # 3. Get Relationship Graph & Validate Join Chain
    base_table_name = request["base_table"]
    requested_joins = request.get("joins", [])
    
    requests_joins_clean = [j for j in requested_joins if j]
    # Handle list of strings or list of JoinDefinition dicts
    joined_table_names = []
    for j in requests_joins_clean:
        if isinstance(j, str): joined_table_names.append(j)
        else: joined_table_names.append(j["table"])

    required_tables_set_lower = set(t.lower() for t in ([base_table_name] + joined_table_names))

    graph = await get_relationship_graph(session, client_id)
    join_steps = await validate_join_path(session, client_id, graph, base_table_name, requested_joins)

    def _resolve_meta(label: str, table_hint: str = None) -> SemanticMetadata:
        if label not in label_to_metas:
            raise HTTPException(status_code=400, detail=f"Column label '{label}' not found in semantics.")
        
        options = label_to_metas[label]
        
        # Priority 1: Exact table hint match
        if table_hint:
            for opt in options:
                if opt.table_name.lower() == table_hint.lower():
                    return opt
        
        # Priority 2: Match any table in our active join set
        for opt in options:
            if opt.table_name.lower() in required_tables_set_lower:
                return opt
        
        return options[0]

    def _generate_dialect_sql():
        from sqlalchemy import create_engine, MetaData, Table, select, func, text, inspect
        
        engine = create_engine(sync_url)
        try:
            metadata_obj = MetaData()
            inspector = inspect(engine)
            db_tables = inspector.get_table_names()
            
            table_map = {} 
            requested_names = set([base_table_name] + joined_table_names)
            
            for t_name in requested_names:
                actual_name = next((t for t in db_tables if t.lower() == t_name.lower()), None)
                if actual_name is not None:
                    table_map[t_name.lower()] = Table(actual_name, metadata_obj, autoload_with=engine)
                else:
                    raise HTTPException(status_code=400, detail=f"Table '{t_name}' not found in database.")

            sa_cols = []
            requested_labels = request.get("columns", [])
            aggregations = request.get("aggregations", [])
            
            if len(requested_labels) == 0 and len(aggregations) == 0:
                raise HTTPException(status_code=400, detail="No columns or aggregations selected.")

            for label in requested_labels:
                # Check for qualified name format "table:label"
                target_table_hint = None
                actual_label = label
                if ":" in label:
                    parts = label.split(":", 1)
                    target_table_hint = parts[0]
                    actual_label = parts[1]

                meta = _resolve_meta(actual_label, target_table_hint)
                t_obj = table_map.get(meta.table_name.lower())
                if t_obj is None:
                     raise HTTPException(status_code=400, detail=f"Column '{actual_label}' table '{meta.table_name}' not in join chain.")
                
                col_name = meta.column_name
                if col_name not in t_obj.columns:
                     raise HTTPException(status_code=400, detail=f"Column '{col_name}' not found in table '{meta.table_name}'.")
                
                # Use actual label as alias
                sa_cols.append(t_obj.columns[col_name].label(actual_label))

            for agg in aggregations:
                col_label = agg["column"]
                func_name = str(agg["function"]).upper()
                res_label = agg.get("label", f"{func_name} of {col_label}")
                
                # Aggregations can also be qualified "table:label"
                target_table_hint = None
                actual_col_label = col_label
                if ":" in col_label:
                    parts = col_label.split(":", 1)
                    target_table_hint = parts[0]
                    actual_col_label = parts[1]

                meta = _resolve_meta(actual_col_label, target_table_hint)
                t_obj = table_map.get(meta.table_name.lower())
                if t_obj is None:
                     raise HTTPException(status_code=400, detail=f"Aggregated column '{actual_col_label}' table not in join chain.")
                
                col_obj = t_obj.columns[meta.column_name]
                if func_name == "SUM": sa_cols.append(func.sum(col_obj).label(res_label))
                elif func_name == "AVG": sa_cols.append(func.avg(col_obj).label(res_label))
                elif func_name == "COUNT": sa_cols.append(func.count(col_obj).label(res_label))
                elif func_name == "MIN": sa_cols.append(func.min(col_obj).label(res_label))
                elif func_name == "MAX": sa_cols.append(func.max(col_obj).label(res_label))
                else: raise HTTPException(status_code=400, detail=f"Unsupported aggregation: {func_name}")

            base_t_obj = table_map.get(base_table_name.lower())
            from_clause = base_t_obj
            
            # Branched Joins logic
            joined_tables = {base_table_name.lower(): base_t_obj}
            
            for step in join_steps:
                l_t = joined_tables.get(step["from_table"].lower())
                r_t = table_map.get(step["to_table"].lower())
                
                if l_t is not None and r_t is not None:
                    on_clause = l_t.c[step["local_column"]] == r_t.c[step["remote_column"]]
                    from_clause = from_clause.join(r_t, on_clause)
                    joined_tables[step["to_table"].lower()] = r_t

            stmt = select(*sa_cols).select_from(from_clause)

            date_filter = request.get("date_filter")
            if date_filter is not None:
                d_label = date_filter.get("column")
                target_table_hint = None
                actual_d_label = d_label
                if ":" in d_label:
                    parts = d_label.split(":", 1)
                    target_table_hint = parts[0]
                    actual_d_label = parts[1]

                d_meta = _resolve_meta(actual_d_label, target_table_hint)
                d_t_obj = table_map.get(d_meta.table_name.lower())
                if d_t_obj is not None:
                    d_col = d_t_obj.columns[d_meta.column_name]
                    r_type = date_filter.get("range")
                    is_mysql = (engine.dialect.name == "mysql")
                    if r_type == "last_30_days":
                        if is_mysql: stmt = stmt.where(d_col >= func.date_sub(func.current_date(), text("INTERVAL 30 DAY")))
                        else: stmt = stmt.where(d_col >= func.current_date() - text("INTERVAL '30 days'"))
                    elif r_type == "last_7_days":
                        if is_mysql: stmt = stmt.where(d_col >= func.date_sub(func.current_date(), text("INTERVAL 7 DAY")))
                        else: stmt = stmt.where(d_col >= func.current_date() - text("INTERVAL '7 days'"))
                    elif r_type == "today":
                        stmt = stmt.where(d_col == func.current_date())
                    elif r_type == "this_month":
                        if is_mysql:
                            stmt = stmt.where(func.month(d_col) == func.month(func.current_date()))
                            stmt = stmt.where(func.year(d_col) == func.year(func.current_date()))
                        else:
                            stmt = stmt.where(func.extract('month', d_col) == func.extract('month', func.current_date()))
                            stmt = stmt.where(func.extract('year', d_col) == func.extract('year', func.current_date()))

            if len(aggregations) > 0 and len(requested_labels) > 0:
                gb_cols = []
                for l in requested_labels:
                    target_table_hint = None
                    actual_l = l
                    if ":" in l:
                        parts = l.split(":", 1)
                        target_table_hint = parts[0]
                        actual_l = parts[1]

                    m = _resolve_meta(actual_l, target_table_hint)
                    t_o = table_map.get(m.table_name.lower())
                    if t_o is not None:
                        gb_cols.append(t_o.columns[m.column_name])
                if len(gb_cols) > 0:
                    stmt = stmt.group_by(*gb_cols)

            return str(stmt.compile(dialect=engine.dialect, compile_kwargs={"literal_binds": True}))
        finally:
            engine.dispose()

    sql = await loop.run_in_executor(None, _generate_dialect_sql)
    return sql

async def execute_safe_sql(session: AsyncSession, client_id: int, request: Dict[Any, Any]) -> List[Dict[Any, Any]]:
    sql_query = await generate_safe_sql(session, client_id, request)
    limited_sql = f"{sql_query} LIMIT 50"
    from sqlalchemy import create_engine
    client_config = await session.get(ClientConfig, client_id)
    if not client_config:
        raise HTTPException(status_code=404, detail="Client not found")
    sync_url = client_config.db_connection_url.replace("+asyncpg", "")
    def _run_query():
        engine = create_engine(sync_url)
        try:
             with engine.connect() as conn:
                 res = conn.execute(text(limited_sql))
                 columns = res.keys()
                 return [dict(zip(columns, row)) for row in res.fetchall()]
        finally:
             engine.dispose()
    import asyncio
    loop = asyncio.get_event_loop()
    rows = await loop.run_in_executor(None, _run_query)
    return rows
