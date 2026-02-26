
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import OperationalError
import secrets

def generate_api_key(prefix: str = "am_live_") -> str:
    """Generates a secure, URL-safe API key."""
    return prefix + secrets.token_urlsafe(32)

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
        # Create a temporary engine just for testing
        test_engine = create_engine(connection_url, connect_args={"connect_timeout": 5})
        with test_engine.connect() as conn:
            return True
    except Exception as e:
        import traceback
        error_msg = f"Connection Test Failed: {str(e)}\n{traceback.format_exc()}"
        print(f"❌ {error_msg}")
        # HACK: For debugging, we might want to raise this to see it in the API response
        raise ValueError(str(e)) 
        return False
        
def discover_tables(connection_url: str):
    """Connects to the DB and returns table metadata."""
    try:
        engine = create_engine(connection_url)
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
            
        return schema_info
    except Exception as e:
        print(f"❌ Discovery Failed: {e}")
        raise e
