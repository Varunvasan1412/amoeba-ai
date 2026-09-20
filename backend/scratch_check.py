import asyncio
from sqlalchemy import select, text
from app.core.database import async_session

async def check():
    async with async_session() as session:
        res = await session.execute(text("SELECT id, client_name, db_connection_url FROM clientconfig WHERE id=4;"))
        row = res.fetchone()
        print(row)

asyncio.run(check())
