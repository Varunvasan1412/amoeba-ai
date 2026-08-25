from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import re
from app.core.context import current_db_url

def _get_async_url(db_url: str) -> str:
    """Ensures the URL uses an async driver."""
    if not db_url: return db_url
    if db_url.startswith("postgresql+psycopg2://"):
        return db_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
    if db_url.startswith("postgresql://"):
        return db_url.replace("postgresql://", "postgresql+asyncpg://")
    if db_url.startswith("mysql+pymysql://"):
        return db_url.replace("mysql+pymysql://", "mysql+aiomysql://")
    if db_url.startswith("mysql://"):
        return db_url.replace("mysql://", "mysql+aiomysql://")
    return db_url

def _get_sync_url(db_url: str) -> str:
    """Ensures the URL uses a sync driver."""
    if not db_url: return db_url
    if db_url.startswith("postgresql+asyncpg://"):
        return db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    if db_url.startswith("postgresql://"):
        return db_url.replace("postgresql://", "postgresql+psycopg2://")
    if db_url.startswith("mysql+aiomysql://"):
        return db_url.replace("mysql+aiomysql://", "mysql+pymysql://")
    if db_url.startswith("mysql://"):
        return db_url.replace("mysql://", "mysql+pymysql://")
    return db_url

async def execute_sql_query(query: str):
    """Executes a read-only SQL query against the database via direct driver."""
    # 1. Safety Check
    forbidden = ["DELETE", "DROP", "UPDATE", "INSERT", "ALTER", "TRUNCATE"]
    pattern = r"\b(" + "|".join(forbidden) + r")\b"
    if re.search(pattern, query, re.IGNORECASE):
        return "Error: Read-only mode active. queries containing MODIFY/DELETE commands are blocked."

    db_url = current_db_url.get()
    if not db_url: return "Error: No Client Database Connection."

    try:
        from sqlalchemy.engine import make_url
        url_obj = make_url(db_url)
        
        if "mysql" in db_url.lower():
            import aiomysql
            conn = await aiomysql.connect(
                host=url_obj.host, port=url_obj.port or 3306,
                user=url_obj.username, password=url_obj.password, db=url_obj.database
            )
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query)
                data = await cur.fetchall()
            conn.close()
            return data
        else:
            # PostgreSQL fallback
            import asyncpg
            conn = await asyncpg.connect(
                user=url_obj.username, password=url_obj.password,
                database=url_obj.database, host=url_obj.host, port=url_obj.port or 5432
            )
            data = [dict(r) for r in await conn.fetch(query)]
            await conn.close()
            return data

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Database Error: {e}"


async def get_database_schema():
    """
    Reflects the database to return a list of tables and their columns.
    Used by the AI to 'see' the user's database structure.
    """
    db_url = current_db_url.get()
    if not db_url:
        from app.core.config import settings
        db_url = settings.DATABASE_URL
        
    try:
        if "mysql" in db_url.lower():
            import aiomysql
            from sqlalchemy.engine import make_url
            url_obj = make_url(db_url)
            print(f"DEBUG: Connecting to MySQL HOST='{url_obj.host}' PORT='{url_obj.port}' DB='{url_obj.database}'", flush=True)
            
            schema_info = {}
            conn = await aiomysql.connect(
                host=url_obj.host, 
                port=url_obj.port or 3306,
                user=url_obj.username, 
                password=url_obj.password, 
                db=url_obj.database
            )
            async with conn.cursor() as cur:
                await cur.execute("SHOW TABLES")
                tables = await cur.fetchall()
                for (table_name,) in tables:
                    columns = []
                    try:
                        await cur.execute(f"DESCRIBE `{table_name}`")
                        cols = await cur.fetchall()
                        for col_row in cols:
                            # col_row is (Field, Type, Null, Key, Default, Extra)
                            columns.append(f"{col_row[0]} ({col_row[1]})")
                        schema_info[table_name] = columns
                    except Exception as col_err:
                        print(f"⚠️ Error describing {table_name}: {col_err}")
            conn.close()
            return schema_info
            
        else:
            # Non-MySQL: Standard SQLAlchemy Async Path
            async_url = _get_async_url(db_url)
            engine = create_async_engine(async_url)
            async with engine.connect() as conn:
                def _get_pg_schema(sync_conn):
                    from sqlalchemy import inspect
                    inspector = inspect(sync_conn)
                    pg_schema = {}
                    for t in inspector.get_table_names():
                        pg_schema[t] = [f"{c['name']} ({c['type']})" for c in inspector.get_columns(t)]
                    return pg_schema
                schema_info = await conn.run_sync(_get_pg_schema)
            await engine.dispose()
            return schema_info
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Schema Error: {e}"

async def execute_ddl(query: str):
    """
    Executes DDL (Data Definition Language) - CREATE TABLE, etc.
    Enabled for 'Advanced Data Ops'.
    """
    forbidden = ["DROP DATABASE"] # We still block dropping the WHOLE database
    pattern = r"\b(" + "|".join(forbidden).replace(" ", r"\s+") + r")\b"
    if re.search(pattern, query, re.IGNORECASE):
        return f"Error: Destructive command 'DROP DATABASE' is blocked."

    db_url = current_db_url.get()
    if not db_url: return "Error: No Client Connection."

    try:
        # STEP 6: Fix Table Creation Logic
        # If it's a CREATE TABLE query for MySQL, ensure AUTO_INCREMENT and UNIQUE are present
        if "CREATE TABLE" in query.upper() and "mysql" in db_url.lower():
            # 1. AUTO_INCREMENT Enforcement
            if "PRIMARY KEY" in query.upper() and "AUTO_INCREMENT" not in query.upper():
                query = re.sub(
                    r"(id|ID)\s+(INT|INTEGER|BIGINT)\s+PRIMARY\s+KEY", 
                    r"\1 \2 PRIMARY KEY AUTO_INCREMENT", 
                    query, 
                    flags=re.IGNORECASE
                )
            
            # 2. UNIQUE Constraint Enforcement for Master Tables
            # If table starts with master_, ensure name/code/sortname are UNIQUE if present
            table_match = re.search(r"CREATE\s+TABLE\s+(\w+)", query, flags=re.IGNORECASE)
            if table_match and table_match.group(1).lower().startswith("master_"):
                # We inject UNIQUE(name), UNIQUE(code) etc if they are being defined but not marked UNIQUE
                # Simple heuristic: look for columns like 'name VARCHAR(255)' and append UNIQUE
                # To be safer, we can just append a UNIQUE INDEX at the end of the CREATE TABLE
                common_fields = ["name", "code", "sortname", "part_number"]
                for field in common_fields:
                    # If field is in query but 'UNIQUE' (for this field) is not
                    if re.search(fr"\b{field}\b", query, flags=re.IGNORECASE) and not re.search(fr"UNIQUE\s*\(\s*{field}\s*\)", query, flags=re.IGNORECASE) and "UNIQUE" not in re.search(fr"\b{field}\b.*?[,)]", query, flags=re.IGNORECASE | re.DOTALL).group(0).upper():
                        # Append to the end of column list (before the last ')')
                        query = re.sub(r"\)\s*$", fr", UNIQUE({field}))", query.strip())
                print(f"DEBUG: Modified DDL with Uniqueness: {query}", flush=True)

        from sqlalchemy.engine import make_url
        url_obj = make_url(db_url)
        
        if "mysql" in db_url.lower():
            import aiomysql
            conn = await aiomysql.connect(
                host=url_obj.host, port=url_obj.port or 3306,
                user=url_obj.username, password=url_obj.password, db=url_obj.database
            )
            async with conn.cursor() as cur:
                await cur.execute(query)
                await conn.commit()
            conn.close()
        else:
            import asyncpg
            conn = await asyncpg.connect(
                user=url_obj.username, password=url_obj.password,
                database=url_obj.database, host=url_obj.host, port=url_obj.port or 5432
            )
            await conn.execute(query)
            await conn.close()
            
        return "✅ DDL Executed Successfully (Table Created/Modified with AUTO_INCREMENT enforcement)."
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
    """Executes INSERT/UPDATE/DELETE queries via direct driver with safety checks."""
    # 1. Safety Check
    forbidden = ["DROP TABLE", "TRUNCATE", "ALTER TABLE", "DROP DATABASE"]
    pattern = r"\b(" + "|".join(forbidden).replace(" ", r"\s+") + r")\b"
    if re.search(pattern, query, re.IGNORECASE):
        return f"Error: Destructive commands ({forbidden}) are blocked for safety."

    # 2. SCOPE VALIDATION (Ensures WHERE clause for UPDATE/DELETE)
    safety_error = validate_write_safety(query)
    if safety_error: return safety_error

    db_url = current_db_url.get()
    if not db_url: return "Error: No Client Connection."

    try:
        from sqlalchemy.engine import make_url
        url_obj = make_url(db_url)
        
        if "mysql" in db_url.lower():
            import aiomysql
            conn = await aiomysql.connect(
                host=url_obj.host, port=url_obj.port or 3306,
                user=url_obj.username, password=url_obj.password, db=url_obj.database
            )
            async with conn.cursor() as cur:
                await cur.execute(query)
                await conn.commit()
                rowcount = cur.rowcount
            conn.close()
            return rowcount
        else:
            import asyncpg
            conn = await asyncpg.connect(
                user=url_obj.username, password=url_obj.password,
                database=url_obj.database, host=url_obj.host, port=url_obj.port or 5432
            )
            result = await conn.execute(query)
            await conn.close()
            # asyncpg.execute returns a command tag like 'UPDATE 1', 'INSERT 0 1'
            if isinstance(result, str) and " " in result:
                try:
                    return int(result.split(" ")[-1])
                except Exception:
                    return result
            return result
            
    except Exception as e:
        return f"SQL Write Error: {e}"
