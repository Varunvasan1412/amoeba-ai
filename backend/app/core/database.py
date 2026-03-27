from typing import AsyncGenerator
from sqlmodel import SQLModel, create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models.user import User # Ensure models are imported for metadata
from app.models.client_config import ClientConfig
from app.models.chat import ChatMessage
from app.models.chat_session import ChatSession
from app.models.chat_memory import ChatMemory
from app.models.navigation import NavigationItem
from app.models.semantic_metadata import SemanticMetadata # [NEW] v2 Semantic Layer
from app.models.allowed_relationship import AllowedRelationship # [NEW] v3 Governance Layer
from app.models.approved_join_path import ApprovedJoinPath # [NEW] v3 Governance Layer
from app.models.conversation_state import ConversationState # [NEW] v3 CRUD Layer
from app.models.field_metadata import FieldMetadata # [NEW] v4 Field Metadata Layer
from app.models.ai_settings import AISettings # [NEW] v6 AI Infrastructure Layer
from app.models.document import Document, DocumentChunk # [NEW] Document Knowledge Layer
import asyncio

# 1. Create the Link
# pool_pre_ping=True helps prevent "closed connection" errors
engine = create_async_engine(
    settings.DATABASE_URL, 
    echo=False,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=10
)

# 2. Session Factory
async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# 3. Dependency
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session

# 4. Init DB
async def init_db():
    async with engine.begin() as conn:
        # Create tables
        await conn.run_sync(SQLModel.metadata.create_all)
        
    # Wait for tables to be ready
    await asyncio.sleep(1)
    print("✅ Database initialized successfully")

async def test_connection():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            print("🐘 Database connection verified.")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")

async def wait_for_db(retries=10):
    while retries > 0:
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                print("✅ Database is UP.")
                return True
        except Exception as e:
            retries -= 1
            print(f"⚠️ Database connection failed. Retrying in 2s... ({retries} left)")
            print(f"Error: {e}")
            await asyncio.sleep(2)
    
    if retries == 0:
        print("❌ Could not connect to Database after multiple retries.")
