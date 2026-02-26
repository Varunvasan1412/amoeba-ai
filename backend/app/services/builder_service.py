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
    """
    # 1. Fetch Client Config
    client_config = (await session.execute(select(ClientConfig).where(ClientConfig.id == client_id))).scalars().first()
    if not client_config:
        raise HTTPException(status_code=404, detail="Client not found")
        
    import asyncio
    loop = asyncio.get_event_loop()
    sync_url = client_config.db_connection_url.replace("+asyncpg", "")
    
    # 2. Extract Validated Semantic Map (Label -> Metadata) for ALL tables
    # We load all metadata for the client to resolve labels from any joined table.
    stmt = select(SemanticMetadata).where(SemanticMetadata.client_id == client_id)
    metadata = (await session.execute(stmt)).scalars().all()
    
    label_map = {}
    for m in metadata:
        label_map[m.label] = m
        if m.synonyms:
            for syn in m.synonyms:
                label_map[syn] = m

    # 3. Get Relationship Graph & Validate Join Chain
    base_table_name = request["base_table"]
    requested_joins = request.get("joins", [])
    
    
    # Max Depth Validation - REMOVED for v2 Governance
    # The validate_join_path function now handles cycle detection and authorized paths.
    # if len(requested_joins) > 3:
    #    raise HTTPException(status_code=400, detail="Join depth limited to 3 tables.")

    requests_joins_clean = [j for j in requested_joins if j]

    graph = await get_relationship_graph(session, client_id)
    join_steps = await validate_join_path(session, client_id, graph, base_table_name, requested_joins)

    def _generate_dialect_sql():
        from sqlalchemy import create_engine, MetaData, Table, select, func, text
        
        engine = create_engine(sync_url)
        try:
            metadata_obj = MetaData()
            
            # Reflect Required Tables
            tables = {}
            required_tables = [base_table_name] + requested_joins
            
            for t_name in required_tables:
                try:
                    tables[t_name] = Table(t_name, metadata_obj, autoload_with=engine)
                except Exception:
                    raise HTTPException(status_code=400, detail=f"Table '{t_name}' not found in database.")

            # Base Select Statement
            sa_cols = []
            requested_labels = request.get("columns", [])
            if not requested_labels:
                raise HTTPException(status_code=400, detail="No columns selected.")

            # Resolve Column Objects
            for label in requested_labels:
                if label not in label_map:
                    raise HTTPException(status_code=400, detail=f"Column label '{label}' not found in semantics.")
                
                meta = label_map[label]
                target_table = meta.table_name
                col_name = meta.column_name
                
                # Security: Ensure column belongs to a table in the validated join chain
                if target_table not in tables:
                     raise HTTPException(status_code=400, detail=f"Column '{label}' belongs to '{target_table}', which is not in the join chain.")
                
                if col_name not in tables[target_table].columns:
                     raise HTTPException(status_code=400, detail=f"Column '{col_name}' not found in table metadata for '{target_table}'.")
                     
                sa_cols.append(tables[target_table].columns[col_name].label(label))

            # Build FROM with JOINs
            from_clause = tables[base_table_name]
            for step in join_steps:
                left_t = tables[step["from_table"]]
                right_t = tables[step["to_table"]]
                on_clause = left_t.c[step["local_column"]] == right_t.c[step["remote_column"]]
                from_clause = from_clause.join(right_t, on_clause)

            stmt = select(*sa_cols).select_from(from_clause)

            # Build WHERE (Date Filter)
            date_filter = request.get("date_filter")
            if date_filter:
                label = date_filter.get("column")
                if label not in label_map:
                    raise HTTPException(status_code=400, detail=f"Date filter label '{label}' not found.")
                
                meta = label_map[label]
                target_table = meta.table_name
                col_name = meta.column_name
                
                if target_table not in tables:
                     raise HTTPException(status_code=400, detail=f"Date column table '{target_table}' not in join chain.")
                     
                col_obj = tables[target_table].columns[col_name]
                range_type = date_filter.get("range")
                
                # Logic for Today/Last 30 Days/Last 7 Days (MySQL vs Postgres)
                is_mysql = (engine.dialect.name == "mysql")

                if range_type == "last_30_days":
                    if is_mysql:
                        stmt = stmt.where(col_obj >= func.date_sub(func.current_date(), text("INTERVAL 30 DAY")))
                    else:
                        stmt = stmt.where(col_obj >= func.current_date() - text("INTERVAL '30 days'"))
                elif range_type == "last_7_days":
                    if is_mysql:
                        stmt = stmt.where(col_obj >= func.date_sub(func.current_date(), text("INTERVAL 7 DAY")))
                    else:
                        stmt = stmt.where(col_obj >= func.current_date() - text("INTERVAL '7 days'"))
                elif range_type == "today":
                    stmt = stmt.where(col_obj == func.current_date())
                elif range_type == "this_month":
                    stmt = stmt.where(func.extract('month', col_obj) == func.extract('month', func.current_date()))
                    stmt = stmt.where(func.extract('year', col_obj) == func.extract('year', func.current_date()))
                else:
                    raise HTTPException(status_code=400, detail=f"Unsupported date range: {range_type}")
            
            # Compile with Dialect specificity
            compiled = stmt.compile(dialect=engine.dialect, compile_kwargs={"literal_binds": True})
            return str(compiled)
            
        finally:
            engine.dispose()

    # Offload to loop
    sql = await loop.run_in_executor(None, _generate_dialect_sql)
    return sql

async def execute_safe_sql(session: AsyncSession, client_id: int, request: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Generates AND executes the safe SQL.
    Returns a list of dictionaries (rows).
    """
    # 1. Generate the Safe SQL (Re-use existing logic)
    sql_query = await generate_safe_sql(session, client_id, request)
    
    # 2. Limit the query for preview safety
    # In production, use LIMIT/OFFSET pagination. For now, hard disable huge fetches.
    limited_sql = f"{sql_query} LIMIT 50"
    
    # 3. Connect to Client DB and Execute
    # We must creating a temporary engine for the client's database
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text

    # Re-fetch config (or pass it down) - fetching is safer
    client_config = await session.get(ClientConfig, client_id)
    if not client_config:
        raise HTTPException(status_code=404, detail="Client not found")

    # Use async engine for execution
    # Note: db_connection_url should be async compatible (postgresql+asyncpg://...)
    # If using run_sync, we might need a sync engine, but let's try async first since we are in async context.
    # Actually, verify_data_preview used requests (asyncio loop).
    
    # We need to handle the case where the URL is sync (e.g. postgresql://) 
    # but we want to use async engine, or we use create_engine (sync) and run_sync/threadpool.
    # Given the previous Greenlet issues, let's use the SYNC engine with run_sync wrapper or just standard threadpool
    # checking what discover_tables does... it uses create_engine (sync).
    
    from sqlalchemy import create_engine
    
    # Ensure URL is sync for create_engine (remove +asyncpg if present)
    # This is a bit hacky, but robust for now.
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

    # Offload to threadpool to avoid blocking
    import asyncio
    loop = asyncio.get_event_loop()
    rows = await loop.run_in_executor(None, _run_query)
    
    return rows
