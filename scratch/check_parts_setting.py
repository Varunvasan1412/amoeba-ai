import asyncio
import os
import sys

# Setup environment for backend
sys.path.append(r"d:\AHATTRICKZ-PROJECT\amoeba-ai\backend")

from app.database import get_db_session
from sqlalchemy import text

async def check_semantic_mapping():
    async for session in get_db_session():
        # Look for semantic mapping of 'Product Parts Setting' or URL 'master/partssettinglist'
        stmt = text("""
            SELECT id, ui_label, database_table, source_file, ui_columns, base_query, required_joins 
            FROM semantic_mapping 
            WHERE client_id = 4 
              AND (ui_label ILIKE '%parts setting%' OR source_file ILIKE '%partssettinglist%')
        """)
        res = await session.execute(stmt)
        rows = res.fetchall()
        print(f"Found {len(rows)} mappings:")
        for r in rows:
            print(dict(r._mapping))
            
if __name__ == "__main__":
    asyncio.run(check_semantic_mapping())
