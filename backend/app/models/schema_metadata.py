from typing import Optional
from sqlmodel import SQLModel, Field, Column
from pgvector.sqlalchemy import Vector

class SchemaMetadata(SQLModel, table=True):
    __tablename__ = "schema_metadata"

    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(index=True)
    table_name: str = Field(index=True)
    
    # Text representation of the table schema (e.g. "Table: users\nColumns: id(int), name(varchar)...")
    schema_definition: str
    
    # 1536 is standard for text-embedding-3-small
    embedding: Optional[list[float]] = Field(default=None, sa_column=Column(Vector(1536)))
