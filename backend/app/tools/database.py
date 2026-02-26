from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import re
from app.core.context import current_db_url

async def execute_sql_query(query: str):
    """
    Executes a read-only SQL query against the database.
    WARNING: This is a high-risk tool. In production, this needs strict sandboxing.
    """
    # 1. Safety Check (Very basic)
    forbidden = ["DELETE", "DROP", "UPDATE", "INSERT", "ALTER", "TRUNCATE"]
    if any(cmd in query.upper() for cmd in forbidden):
        return "Error: Read-only mode active. queries containing MODIFY/DELETE commands are blocked."

    db_url = current_db_url.get()
    if not db_url:
        return "Error: No Client Database Connection found in context. Please provide an API Key."

    # 2. Dynamic Connection
    # In production, cache these engines! Don't create one per query.
    try:
        engine = create_async_engine(db_url)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with async_session() as session:
            result = await session.execute(text(query))
            rows = result.fetchall()
            # Convert to list of dicts
            data = [dict(row._mapping) for row in rows]
            
        await engine.dispose() # Cleanup
        return data

    except Exception as e:
        return f"Database Error: {e}"

async def get_database_schema():
    """
    Reflects the database to return a list of tables and their columns.
    Used by the AI to 'see' the user's database structure.
    """
    db_url = current_db_url.get()
    if not db_url: return "Error: No Client Connection."

    try:
        from sqlalchemy import inspect
        engine = create_async_engine(db_url)
        
        # Async Inspection is tricky in newer SQLAlchemy. 
        # We run a sync function in a thread or use run_sync.
        def _get_schema(connection):
            inspector = inspect(connection)
            schema_info = {}
            for table_name in inspector.get_table_names():
                columns = []
                for col in inspector.get_columns(table_name):
                    columns.append(f"{col['name']} ({col['type']})")
                schema_info[table_name] = columns
            return schema_info

        async with engine.connect() as conn:
            schema = await conn.run_sync(_get_schema)
            
        await engine.dispose()
        return str(schema)
    except Exception as e:
        return f"Schema Error: {e}"

async def execute_ddl(query: str):
    """
    Executes DDL (Data Definition Language) - CREATE TABLE, etc.
    Enabled for 'Advanced Data Ops'.
    """
    forbidden = ["DROP DATABASE"] # We still block dropping the WHOLE database
    if any(cmd in query.upper() for cmd in forbidden):
        return f"Error: Destructive command 'DROP DATABASE' is blocked."

    db_url = current_db_url.get()
    if not db_url: return "Error: No Client Connection."

    try:
        engine = create_async_engine(db_url)
        async with engine.begin() as conn: # DDL requires commit
            await conn.execute(text(query))
            
        await engine.dispose()
        return "✅ DDL Executed Successfully (Table Created/Modified)."
    except Exception as e:
        return f"DDL Error: {e}"

def validate_write_safety(query: str) -> str:
    """
    Ensures UPDATE/DELETE queries have a WHERE clause to prevent mass modification.
    Returns None if safe, or an error string if unsafe.
    """
    q = query.strip().upper()
    
    # 1. Check if it's UPDATE or DELETE
    is_update = q.startswith("UPDATE")
    is_delete = q.startswith("DELETE")
    
    if not (is_update or is_delete):
        return None # INSERT is generally safe (add only)
        
    # 2. Check for WHERE clause
    if "WHERE" not in q:
        return f"SAFETY BLOCK: Your { 'UPDATE' if is_update else 'DELETE'} query is missing a WHERE clause. This would modify ALL rows. Please add a specific condition."
        
    # 3. Check for specific condition (heuristic)
    # We want to avoid "WHERE 1=1" or empty logic, but simple existence check is 90% of the battle.
    # regex for empty where?
    return None

async def execute_sql_write(query: str):
    """
    Executes INSERT/UPDATE/DELETE queries.
    DANGEROUS: Filters out DROP/TRUNCATE/ALTER to prevent catastrophic data loss.
    """
    # 1. Safety Check
    # We allow INSERT, UPDATE, DELETE.
    # We BLOCK structural destruction.
    forbidden = ["DROP TABLE", "TRUNCATE", "ALTER TABLE", "DROP DATABASE"]
    if any(cmd in query.upper() for cmd in forbidden):
        return f"Error: Destructive commands ({forbidden}) are blocked for safety."

    # 2. SCOPE VALIDATION (New)
    safety_error = validate_write_safety(query)
    if safety_error:
        return safety_error

    db_url = current_db_url.get()
    if not db_url: return "Error: No Client Connection."

    try:
        engine = create_async_engine(db_url)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with async_session() as session:
            await session.execute(text(query))
            await session.commit()
            
        await engine.dispose()
        return "✅ SQL Executed Successfully."
    except Exception as e:
        return f"SQL Write Error: {e}"
