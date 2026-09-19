import time
from sqlalchemy import create_engine, inspect
from typing import Dict, List, Any

_schema_cache = {}

def discover_full_schema(connection_url: str) -> Dict[str, Any]:
    """
    Enhanced discovery for v2.
    Returns table columns AND foreign key relationships for safe joins.
    Results are cached for 10 minutes to dramatically speed up UI navigation.
    """
    current_time = time.time()
    if connection_url in _schema_cache and current_time - _schema_cache[connection_url]['time'] < 600:
        return _schema_cache[connection_url]['data']
        
    try:
        engine = create_engine(connection_url)
        inspector = inspect(engine)
        
        schema_data = {}
        
        for table_name in inspector.get_table_names():
            # Get Columns and Types
            columns = []
            for col in inspector.get_columns(table_name):
                col_type = str(col["type"])
                columns.append({"name": col["name"], "type": col_type})
            
            # Get Foreign Keys
            fks = []
            for fk in inspector.get_foreign_keys(table_name):
                fks.append({
                    "constrained_columns": fk["constrained_columns"],
                    "referred_table": fk["referred_table"],
                    "referred_columns": fk["referred_columns"]
                })
            
            # Get Primary Keys
            try:
                pk_constraint = inspector.get_pk_constraint(table_name)
                primary_keys = pk_constraint.get("constrained_columns", [])
            except Exception:
                primary_keys = []
            
            schema_data[table_name] = {
                "columns": columns,
                "primary_keys": primary_keys,
                "foreign_keys": fks
            }
            
        _schema_cache[connection_url] = {'time': time.time(), 'data': schema_data}
        return schema_data
    except Exception as e:
        print(f"❌ Enhanced Discovery Failed: {e}")
        raise e
