from langchain_core.tools import tool
from app.services.crud_service import CRUDService
import json
from typing import Dict, Any, Optional

@tool
async def tool_create_erp_record(table_name: str, data_json: str):
    """
    Creates a new record in the ERP database.
    Args:
        table_name (str): The name of the table to insert into.
        data_json (str): A JSON string of key-value pairs representing the record.
    Example: tool_create_erp_record(table_name="customers", data_json='{"name": "John Doe", "email": "john@example.com"}')
    """
    try:
        data = json.loads(data_json)
        return await CRUDService.create_record(table_name, data)
    except Exception as e:
        return f"Error: {e}"

@tool
async def tool_read_erp_records(table_name: str, filters_json: Optional[str] = None, limit: int = 100):
    """
    Reads records from the ERP database with optional filters.
    Args:
        table_name (str): The name of the table to read from.
        filters_json (str, optional): A JSON string of key-value pairs for filtering (WHERE clause).
        limit (int): Maximum number of records to return.
    Example: tool_read_erp_records(table_name="invoices", filters_json='{"status": "paid"}', limit=10)
    """
    try:
        filters = json.loads(filters_json) if filters_json else None
        return await CRUDService.read_records(table_name, filters, limit)
    except Exception as e:
        return f"Error: {e}"

@tool
async def tool_update_erp_records(table_name: str, filters_json: str, update_data_json: str):
    """
    Updates existing records in the ERP database.
    REQUIRED: filters_json to prevent global updates.
    Args:
        table_name (str): The name of the table to update.
        filters_json (str): A JSON string of key-value pairs to identify records to update.
        update_data_json (str): A JSON string of key-value pairs representing the new values.
    Example: tool_update_erp_records(table_name="products", filters_json='{"id": 5}', update_data_json='{"price": 29.99}')
    """
    try:
        filters = json.loads(filters_json)
        update_data = json.loads(update_data_json)
        return await CRUDService.update_records(table_name, filters, update_data)
    except Exception as e:
        return f"Error: {e}"

@tool
async def tool_delete_erp_records(table_name: str, filters_json: str):
    """
    Deletes records from the ERP database.
    REQUIRED: filters_json for safety.
    Args:
        table_name (str): The name of the table to delete from.
        filters_json (str): A JSON string of key-value pairs to identify records to delete.
    Example: tool_delete_erp_records(table_name="leads", filters_json='{"status": "junk"}')
    """
    try:
        filters = json.loads(filters_json)
        return await CRUDService.delete_records(table_name, filters)
    except Exception as e:
        return f"Error: {e}"
