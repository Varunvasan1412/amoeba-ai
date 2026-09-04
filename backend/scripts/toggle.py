import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    engine = create_async_engine('postgresql+asyncpg://postgres:postgres@localhost:5432/amoeba_ai')
    async with engine.connect() as conn:
        await conn.execute(text("UPDATE clientconfig SET schema_rag_enabled = TRUE WHERE api_key = 'am_live_wWLKiZjrdt5C5e4kZRQYKXICzN6EyZAWfVcmiPY7Kfc'"))
        await conn.commit()
    print("Toggle is now ON for your API key!")

asyncio.run(main())
