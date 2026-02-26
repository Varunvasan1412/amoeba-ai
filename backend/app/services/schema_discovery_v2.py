from sqlalchemy import create_engine, inspect
from typing import Dict, List, Any

def discover_full_schema(connection_url: str) -> Dict[str, Any]:
    """
    Enhanced discovery for v2.
    Returns table columns AND foreign key relationships for safe joins.
    """
    try:
        engine = create_engine(connection_url)
        inspector = inspect(engine)
        
        schema_data = {}
        
        for table_name in inspector.get_table_names():
            # Get Columns
            columns = []
            for col in inspector.get_columns(table_name):
                columns.append(col["name"])
            
            # Get Foreign Keys
            fks = []
            for fk in inspector.get_foreign_keys(table_name):
                fks.append({
                    "constrained_columns": fk["constrained_columns"],
                    "referred_table": fk["referred_table"],
                    "referred_columns": fk["referred_columns"]
                })
            
            schema_data[table_name] = {
                "columns": columns,
                "foreign_keys": fks
            }
            
        return schema_data
    except Exception as e:
        print(f"❌ Enhanced Discovery Failed: {e}")
        raise e
