from app.core.database import engine
from sqlmodel import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.navigation import NavigationItem

async def add_navigation_item_db(label: str, path: str, icon: str = "Circle"):
    """
    Adds a navigation item to the database (Async).
    """
    try:
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            # Check for duplicates
            result = await session.execute(select(NavigationItem).where(NavigationItem.label == label))
            existing = result.scalars().first()
            
            if existing:
                return f"Navigation item '{label}' already exists."
                
            item = NavigationItem(label=label, path=path, icon=icon)
            session.add(item)
            await session.commit()
            return f"Successfully added navigation link: {label} -> {path}"
    except Exception as e:
        return f"Error adding navigation item: {e}"

async def delete_navigation_item_db(label: str):
    """
    Deletes a navigation item from the database.
    """
    try:
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            # Check if exists
            result = await session.execute(select(NavigationItem).where(NavigationItem.label == label))
            item = result.scalars().first()
            
            if not item:
                return f"Navigation item '{label}' not found."
            
            await session.delete(item)
            await session.commit()
            return f"Successfully removed navigation link: {label}"
    except Exception as e:
        return f"Error deleting navigation item: {e}"
