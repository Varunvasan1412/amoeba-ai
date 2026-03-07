from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, MetaData, Table, insert, select, update, delete, text
from app.core.config import settings
from app.core.context import current_db_url

class CRUDBuilder:
    def __init__(self, connection_url: str):
        self.engine = create_engine(connection_url)
        self.metadata = MetaData()
        self.metadata.reflect(bind=self.engine)

    def _get_table(self, table_name: str) -> Table:
        if table_name not in self.metadata.tables:
            raise ValueError(f"Table '{table_name}' not found in database.")
        return self.metadata.tables[table_name]

    def execute_create(self, table_name: str, data: Dict[str, Any]):
        table = self._get_table(table_name)
        stmt = insert(table).values(**data)
        with self.engine.connect() as conn:
            result = conn.execute(stmt)
            conn.commit()
            return result.lastrowid or result.inserted_primary_key

    def execute_read(self, table_name: str, filters: Dict[str, Any] = None, limit: int = 10):
        table = self._get_table(table_name)
        stmt = select(table)
        if filters:
            for key, value in filters.items():
                if hasattr(table.c, key):
                    stmt = stmt.where(getattr(table.c, key) == value)
        
        stmt = stmt.limit(limit)
        with self.engine.connect() as conn:
            result = conn.execute(stmt)
            return [dict(row._mapping) for row in result.all()]

    def execute_update(self, table_name: str, filters: Dict[str, Any], data: Dict[str, Any]):
        table = self._get_table(table_name)
        stmt = update(table)
        for key, value in filters.items():
            if hasattr(table.c, key):
                stmt = stmt.where(getattr(table.c, key) == value)
        
        stmt = stmt.values(**data)
        with self.engine.connect() as conn:
            result = conn.execute(stmt)
            conn.commit()
            return result.rowcount

    def execute_delete(self, table_name: str, filters: Dict[str, Any]):
        if not filters:
            raise ValueError("Mass delete without filters is blocked for safety.")
            
        table = self._get_table(table_name)
        stmt = delete(table)
        for key, value in filters.items():
            if hasattr(table.c, key):
                stmt = stmt.where(getattr(table.c, key) == value)
        
        with self.engine.connect() as conn:
            result = conn.execute(stmt)
            conn.commit()
            return result.rowcount

class CRUDService:
    @staticmethod
    def get_builder() -> CRUDBuilder:
        url = current_db_url.get()
        if not url:
            # Fallback for LLM tools if context not set (unlikely in ws flow)
            url = settings.DATABASE_URL
        
        # Convert async driver to sync for CRUDBuilder (sqlalchemy core)
        sync_url = url.replace("+asyncpg", "+psycopg2") if "+asyncpg" in url else url
        return CRUDBuilder(sync_url)

    @staticmethod
    async def create_record(table_name: str, data: Dict[str, Any]):
        builder = CRUDService.get_builder()
        return builder.execute_create(table_name, data)

    @staticmethod
    async def read_records(table_name: str, filters: Optional[Dict[str, Any]] = None, limit: int = 100):
        builder = CRUDService.get_builder()
        return builder.execute_read(table_name, filters, limit)

    @staticmethod
    async def update_records(table_name: str, filters: Dict[str, Any], data: Dict[str, Any]):
        builder = CRUDService.get_builder()
        return builder.execute_update(table_name, filters, data)

    @staticmethod
    async def delete_records(table_name: str, filters: Dict[str, Any]):
        builder = CRUDService.get_builder()
        return builder.execute_delete(table_name, filters)
