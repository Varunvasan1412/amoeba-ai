from typing import AsyncGenerator
from sqlmodel import SQLModel, create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models.client_config import ClientConfig 
from app.models.chat import ChatMessage
from app.models.blog import Blog
from app.models.user import User
from app.models.navigation import NavigationItem
from app.models.report_registry import ReportRegistry
from app.models.audit_log import AuditLog # Ensure registration
from app.models.semantic_metadata import SemanticMetadata # [NEW] v2 Semantic Layer
from app.models.allowed_relationship import AllowedRelationship # [NEW] v2 Governance Layer
from app.models.conversation_state import ConversationState # [NEW] v3 CRUD Layer
import asyncio

# 1. Create the Link
# pool_pre_ping=True helps prevent "closed connection" errors
engine = create_async_engine(
    settings.DATABASE_URL, 
    echo=True, 
    future=True,
    pool_pre_ping=True
)

# 2. Function to get a "Session"
# This MUST be an async generator
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session

# 3. Function to create tables AND enable pgvector
async def init_db():
    retries = 5
    while retries > 0:
        try:
            async with engine.begin() as conn:
                # ENABLE PGVECTOR EXTENSION
                # await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                
                # Create normal tables
                await conn.run_sync(SQLModel.metadata.create_all)
            print("✅ Database initialized successfully")
            break
        except Exception as e:
            retries -= 1
            print(f"⚠️ Database connection failed. Retrying in 2s... ({retries} left)")
            print(f"Error: {e}")
            await asyncio.sleep(2)
    
    if retries == 0:
        print("❌ Could not connect to Database after multiple retries.")