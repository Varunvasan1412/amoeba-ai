import asyncio
from app.core.database import async_session
from sqlalchemy import text

async def check():
    async with async_session() as session:
        res = await session.execute(text("SELECT id, client_name, assistant_enabled, operations_enabled FROM clientconfig"))
        rows = res.fetchall()
        for r in rows:
            print(f"Client {r[0]}: {r[1]} | assistant={r[2]} | operations={r[3]}")

asyncio.run(check())
