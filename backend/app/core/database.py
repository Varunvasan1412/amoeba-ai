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
from app.models.audit_log import AuditLog # [NEW] Audit Trail Layer
from app.models.table_health import TableHealth # [NEW] Table Repair Tracking Layer
from app.models.rbac import Role, Permission, RolePermissionLink # [NEW] RBAC Models
from app.models.login_audit import LoginAudit # [NEW] Login Audit Trail


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
        # Enable pgvector extension before creating tables
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        
        # Create tables (Handles new tables only)
        await conn.run_sync(SQLModel.metadata.create_all)
        
        # Manual Migrations for existing tables (Handles column updates)
        # Using database-agnostic checks where possible
        print("🛠️ Checking for schema updates...")
        
        # 1. Update 'users' table
        try:
            # Check for email column in users
            res = await conn.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'email'"
            ))
            if not res.fetchone():
                await conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(255) UNIQUE"))
            
            # Check for is_platform_user
            res = await conn.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'is_platform_user'"
            ))
            if not res.fetchone():
                await conn.execute(text("ALTER TABLE users ADD COLUMN is_platform_user BOOLEAN DEFAULT FALSE"))
            
            # Check for client_id
            res = await conn.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'client_id'"
            ))
            if not res.fetchone():
                await conn.execute(text("ALTER TABLE users ADD COLUMN client_id INTEGER"))
        except Exception as e:
            logger.warning(f"Users migration notice: {e}")

        # 2. Update 'clientconfig' table
        try:
            # Check for company_code
            res = await conn.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'clientconfig' AND column_name = 'company_code'"
            ))
            if not res.fetchone():
                await conn.execute(text("ALTER TABLE clientconfig ADD COLUMN company_code VARCHAR(255) UNIQUE"))
            
            # Check for created_at
            res = await conn.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'clientconfig' AND column_name = 'created_at'"
            ))
            if not res.fetchone():
                now = __import__("datetime").datetime.utcnow().isoformat()
                await conn.execute(text(f"ALTER TABLE clientconfig ADD COLUMN created_at VARCHAR(255) DEFAULT '{now}'"))
            
            # Ensure no NULLs in existing rows
            now = __import__("datetime").datetime.utcnow().isoformat()
            await conn.execute(text(f"UPDATE clientconfig SET created_at = '{now}' WHERE created_at IS NULL"))
            
            # Check for total_tokens_used
            res = await conn.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'clientconfig' AND column_name = 'total_tokens_used'"
            ))
            if not res.fetchone():
                await conn.execute(text("ALTER TABLE clientconfig ADD COLUMN total_tokens_used INTEGER DEFAULT 0"))
        except Exception as e:
            logger.warning(f"ClientConfig migration notice: {e}")

        # 3. Update 'field_metadata' table
        try:
            res = await conn.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'field_metadata' AND column_name = 'is_primary_date'"
            ))
            if not res.fetchone():
                await conn.execute(text("ALTER TABLE field_metadata ADD COLUMN is_primary_date BOOLEAN DEFAULT FALSE"))
                print("  ✅ Added 'is_primary_date' to field_metadata")
        except Exception as e:
            logger.warning(f"FieldMetadata migration notice: {e}")

        # 4. Update 'navigationitem' table (pgvector)
        try:
            res = await conn.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'navigationitem' AND column_name = 'embedding'"
            ))
            if not res.fetchone():
                await conn.execute(text("ALTER TABLE navigationitem ADD COLUMN embedding vector(1536)"))
                print("  ✅ Added 'embedding' vector column to navigationitem")
        except Exception as e:
            print(f"NavigationItem migration notice: {e}")

    # Seed RBAC Data
    from app.services.rbac_service import seed_rbac_data
    await seed_rbac_data()
        
    # Wait for tables to be ready
    await asyncio.sleep(1)

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
