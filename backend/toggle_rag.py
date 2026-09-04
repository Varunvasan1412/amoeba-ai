import asyncio
from app.core.database import async_session
from app.models.client_config import ClientConfig
from sqlalchemy import update

async def main():
    async with async_session() as session:
        await session.execute(update(ClientConfig).values(schema_rag_enabled=True))
        await session.commit()
        print('Updated ALL clients to True')

if __name__ == "__main__":
    asyncio.run(main())
