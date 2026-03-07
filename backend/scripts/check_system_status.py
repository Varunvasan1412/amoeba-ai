import asyncio
from sqlmodel import select
from app.core.database import engine
from app.models.report_registry import ReportRegistry
from app.models.client_config import ClientConfig
from app.models.semantic_metadata import SemanticMetadata
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

async def check_status():
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        # Check Clients
        clients = (await session.execute(select(ClientConfig))).scalars().all()
        print(f"Total Clients Configured: {len(clients)}")
        for c in clients:
            print(f" - Client: {c.client_name} (ID: {c.id}), ERP Connected: {'Yes' if c.db_connection_url else 'No'}")
        
        # Check Semantics
        semantics = (await session.execute(select(SemanticMetadata))).scalars().all()
        print(f"Total Semantic Mappings: {len(semantics)}")
        
        # Check Reports
        reports = (await session.execute(select(ReportRegistry))).scalars().all()
        print(f"Total Reports (Data Views): {len(reports)}")
        for r in reports:
            base_t = r.builder_definition.get("base_table", "Unknown") if r.builder_definition else "Static"
            print(f" - Report: {r.display_name} (Base Table: {base_t})")

if __name__ == "__main__":
    asyncio.run(check_status())
