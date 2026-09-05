from sqlmodel import SQLModel, Field
from typing import Optional

class SemanticMapping(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(index=True)
    ui_label: str = Field(index=True)
    database_table: str = Field(index=True)
    source_file: Optional[str] = Field(default=None)
    ui_columns: Optional[str] = Field(default=None)
