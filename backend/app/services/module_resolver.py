from app.models.navigation import NavigationItem
from sqlmodel import select

async def resolve_module_for_table(table_name: str, client_id: int, session):    
    if not table_name:
        return None
        
    stmt = select(NavigationItem).where(
        NavigationItem.client_id == client_id,
        NavigationItem.table_name == table_name
    )
    res = await session.execute(stmt)
    item = res.scalars().first()

    return item.module if item else None
