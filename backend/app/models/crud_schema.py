from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class CrudOperation(BaseModel):
    action: str = Field(..., description="The action to perform: CREATE, UPDATE, DELETE")
    table: str = Field(..., description="The physical database table name")
    record_id: Optional[Any] = Field(None, description="The primary key of the record (required for UPDATE and DELETE)")
    fields: Optional[Dict[str, Any]] = Field(None, description="A dictionary of physical column names mapping to their new values (required for CREATE and UPDATE)")

    class Config:
        json_schema_extra = {
            "example": {
                "action": "UPDATE",
                "table": "enquiries",
                "record_id": 123,
                "fields": {
                    "amount": 50000.0,
                    "status": 1
                }
            }
        }
