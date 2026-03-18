import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.core.config import settings

async def cleanup():
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.connect() as conn:
        print("Cleaning up route with ID 7...")
        await conn.execute(text('DELETE FROM navigationitem WHERE id = 7'))
        await conn.commit()
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(cleanup())
