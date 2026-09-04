import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import os
from dotenv import load_dotenv

load_dotenv('/app/.env')
url = os.getenv('DATABASE_URL', 'postgresql+asyncpg://user:password@db:5432/amoeba')
print(f"USING DATABASE: {url}")

async def main():
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT db_connection_url FROM clientconfig WHERE api_key = 'am_live_wWLKiZjrdt5C5e4kZRQYKXICzN6EyZAWfVcmiPY7Kfc'"))
        url_in_db = res.scalar()
        print(f"URL IN DB: {url_in_db}")
        
        # update the url password if it is 'empty'
        if url_in_db and 'empty@' in url_in_db:
            new_url = url_in_db.replace('empty@', '1Q2w3e4r@#123@')
            await conn.execute(text("UPDATE clientconfig SET db_connection_url = :url WHERE api_key = 'am_live_wWLKiZjrdt5C5e4kZRQYKXICzN6EyZAWfVcmiPY7Kfc'"), {"url": new_url})
            await conn.commit()
            print(f"UPDATED URL TO: {new_url}")

asyncio.run(main())
