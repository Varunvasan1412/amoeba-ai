import asyncio
from sqlmodel import select
from app.core.database import async_session
from app.models.client_config import ClientConfig
from app.models.ai_settings import AISettings
import uuid

async def seed():
    async with async_session() as session:
        # Check if client exists
        res = await session.execute(select(ClientConfig))
        if res.scalars().first():
            print("Database already seeded with clients.")
            return

        print("Seeding initial production ClientConfig...")
        new_client = ClientConfig(
            api_key=str(uuid.uuid4()),
            client_name="Amoeba Live Server",
            company_code="AMB-LIVE",
            is_active=True
        )
        session.add(new_client)
        await session.commit()
        await session.refresh(new_client)

        print("Seeding initial AI Settings (OpenAI / gpt-5.6-luna)...")
        new_ai = AISettings(
            client_id=new_client.id,
            provider="OPENAI",
            model="gpt-5.6-luna"
        )
        session.add(new_ai)
        await session.commit()

        print("Done! You can now test the chat widget.")
        print(f"Your Production API Key for this widget is: {new_client.api_key}")

if __name__ == '__main__':
    asyncio.run(seed())
