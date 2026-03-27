from typing import List, Optional, Dict
from sqlmodel import select, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.navigation import NavigationItem

class RouteContextService:
    @staticmethod
    async def get_modules(client_id: int, session: AsyncSession) -> List[str]:
        """Fetch all unique modules for a client."""
        statement = select(distinct(NavigationItem.module)).where(NavigationItem.client_id == client_id)
        result = await session.execute(statement)
        return list(result.scalars().all())

    @staticmethod
    async def get_pages(client_id: int, module: str, session: AsyncSession) -> List[Dict[str, str]]:
        """Fetch all pages within a specific module."""
        statement = select(NavigationItem).where(
            NavigationItem.client_id == client_id,
            NavigationItem.module == module
        )
        result = await session.execute(statement)
        items = result.scalars().all()
        return [{"label": item.label, "table_name": item.table_name} for item in items]

    @staticmethod
    async def resolve_table(client_id: int, module: str, page_label: str, session: AsyncSession) -> Optional[str]:
        """Resolve a table name from a module and page label."""
        statement = select(NavigationItem.table_name).where(
            NavigationItem.client_id == client_id,
            NavigationItem.module == module,
            NavigationItem.label == page_label
        )
        result = await session.execute(statement)
        return result.scalar_one_or_none()
