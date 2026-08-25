from langchain_core.tools import tool
from app.services.crud_service import CRUDService
import json
from typing import Dict, Any, Optional, Union

@tool
async def tool_create_erp_record(table_name: str, data_json: Union[str, Dict[str, Any]], client_id: Optional[int] = None, session: Optional[Any] = None):
    """
    Creates a new record in the ERP database.
    Args:
        table_name (str): The name of the table to insert into.
        data_json (str | dict): A JSON string or dictionary of key-value pairs representing the record.
    Example: tool_create_erp_record(table_name="customers", data_json={"name": "John Doe", "email": "john@example.com"})
    """
    try:
        data = data_json if isinstance(data_json, dict) else json.loads(data_json)
        return await CRUDService.create_record(table_name, data, client_id=client_id)
    except Exception as e:
        return f"Error: {e}"

@tool
async def tool_read_erp_records(table_name: str, filters_json: Optional[Union[str, Dict[str, Any]]] = None, limit: int = 100, user_query: Optional[str] = None, client_id: Optional[int] = None, session: Optional[Any] = None):
    """
    Reads records from the ERP database with optional filters.
    Args:
        table_name (str): The name of the table to read from.
        filters_json (str | dict, optional): A JSON string or dict of key-value pairs for filtering. 
            Supports simple equality: {"status": "paid"}
            OR advanced operators: {"amount": {"op": ">", "value": 1000}, "name": {"op": "contains", "value": "tech"}}
            Operators: =, !=, >, <, >=, <=, like, ilike, contains, startswith, endswith, in, not_in, between, is_null, is_not_null.
        limit (int): Maximum number of records to return.
        user_query (str, optional): The raw natural language query from the user (used for Smart Filtering fallback).
    """
    try:
        print(f"🛠️ [CRUD DEBUG] READING table: {table_name}", flush=True)
        print(f"🛠️ [CRUD DEBUG] FILTERS_JSON: {filters_json}", flush=True)
        if filters_json:
            filters = filters_json if isinstance(filters_json, dict) else json.loads(filters_json)
        else:
            filters = None
        result = await CRUDService.read_records(table_name, filters, limit, client_id=client_id, user_query=user_query)
        
        # Handle diagnostic warnings for the AI
        if isinstance(result, dict) and "warnings" in result:
             def datetime_handler(x):
                 if hasattr(x, "isoformat"):
                     return x.isoformat()
                 raise TypeError("Unknown type")
             return f"RESULTS:\n{json.dumps(result['records'], indent=2, default=datetime_handler)}\n\nWARNING: {result['warnings']}"
        
        return result
    except Exception as e:
        return f"Error: {e}"

@tool
async def tool_update_erp_records(table_name: str, filters_json: Union[str, Dict[str, Any]], update_data_json: Union[str, Dict[str, Any]], client_id: Optional[int] = None, session: Optional[Any] = None):
    """
    Updates existing records in the ERP database.
    REQUIRED: filters_json to prevent global updates.
    Args:
        table_name (str): The name of the table to update.
        filters_json (str | dict): A JSON string or dict of key-value pairs to identify records. Supports operators like: {"id": {"op": "in", "value": [1,2,3]}}
        update_data_json (str | dict): A JSON string or dict of key-value pairs representing the new values.
    Example: tool_update_erp_records(table_name="products", filters_json={"category": "old"}, update_data_json={"status": "deprecated"})
    """
    try:
        filters = filters_json if isinstance(filters_json, dict) else json.loads(filters_json)
        update_data = update_data_json if isinstance(update_data_json, dict) else json.loads(update_data_json)
        return await CRUDService.update_records(table_name, filters, update_data, client_id=client_id)
    except Exception as e:
        return f"Error: {e}"

@tool
async def tool_delete_erp_records(table_name: str, filters_json: Union[str, Dict[str, Any]], client_id: Optional[int] = None, session: Optional[Any] = None):
    """
    Deletes records from the ERP database.
    REQUIRED: filters_json for safety.
    Args:
        table_name (str): The name of the table to delete from.
        filters_json (str | dict): A JSON string or dict of key-value pairs to identify records safely. Supports operators: {"deleted_at": {"op": "is_not_null"}}
    Example: tool_delete_erp_records(table_name="leads", filters_json={"status": {"op": "in", "value": ["junk", "spam"]}})
    """
    try:
        filters = filters_json if isinstance(filters_json, dict) else json.loads(filters_json)
        return await CRUDService.delete_records(table_name, filters, client_id=client_id)
    except Exception as e:
        return f"Error: {e}"
