
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import OperationalError
import secrets
import time

# --- Schema Cache (TTL-based) ---
_schema_cache: dict = {}  # { connection_url: (timestamp, schema_info) }
_SCHEMA_CACHE_TTL = 300  # 5 minutes

def generate_api_key(prefix: str = "am_live_") -> str:
    """Generates a secure, URL-safe API key."""
    return prefix + secrets.token_urlsafe(32)

def generate_company_code(client_name: str) -> str:
    """Generates a clean company code from the name."""
    # Remove non-alphanumeric chars
    clean_name = "".join(e for e in client_name if e.isalnum()).upper()
    # Take first 4-8 chars and add a short random hex
    base = clean_name[:6] if len(clean_name) >= 6 else clean_name
    return f"{base}-{secrets.token_hex(2).upper()}"

def build_connection_url(db_type: str, user: str, password: str, host: str, port: int, db_name: str) -> str:
    """Constructs a SQLAlchemy connection URL safely."""
    # Basic validation
    if db_type not in ["mysql", "postgresql", "mssql"]:
        raise ValueError(f"Unsupported database type: {db_type}")
    
    # URL Encoding for safety (simplified for now, ideally use make_url or quote_plus)
    from urllib.parse import quote_plus
    encoded_user = quote_plus(user)
    encoded_password = quote_plus(password)
    
    if db_type == "mysql":
        driver = "mysql+pymysql"
    elif db_type == "postgresql":
        driver = "postgresql+psycopg2" # or asyncpg if needed, but this is usually for sync checks
    else:
        driver = db_type

    return f"{driver}://{encoded_user}:{encoded_password}@{host}:{port}/{db_name}"

def test_db_connection(connection_url: str) -> bool:
    """Tests connectivity to the database."""
    try:
        # Use only connect_timeout — read/write timeouts can kill the auth handshake
        test_engine = create_engine(
            connection_url,
            connect_args={"connect_timeout": 10},
        )
        with test_engine.connect() as conn:
            pass  # Connection opened successfully
        test_engine.dispose()
        return True
    except Exception as e:
        import traceback
        print(f"❌ Connection Test Failed: {e}\n{traceback.format_exc()}")
        return False
        
def discover_tables(connection_url: str):
    """Connects to the DB and returns table metadata. Uses a 5-minute TTL cache."""
    global _schema_cache
    
    # Check cache first
    if connection_url in _schema_cache:
        cached_time, cached_data = _schema_cache[connection_url]
        if time.time() - cached_time < _SCHEMA_CACHE_TTL:
            return cached_data
    
    try:
        # Create engine with explicit timeout
        engine = create_engine(connection_url, connect_args={"connect_timeout": 10})
        inspector = inspect(engine)
        
        schema_info = []
        for table_name in inspector.get_table_names():
            columns = []
            for col in inspector.get_columns(table_name):
                columns.append(col["name"])
            
            schema_info.append({
                "name": table_name,
                "columns": columns
            })
        
        # Store in cache
        _schema_cache[connection_url] = (time.time(), schema_info)
        
        return schema_info
    except Exception as e:
        print(f"❌ Discovery Failed: {e}")
        raise e

def invalidate_schema_cache(connection_url: str = None):
    """Invalidates schema cache. If no URL, clears all."""
    global _schema_cache
    if connection_url:
        _schema_cache.pop(connection_url, None)
    else:
        _schema_cache.clear()

