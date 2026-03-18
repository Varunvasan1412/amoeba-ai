import asyncio
import sys
import os

# Add backend to sys.path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, create_engine, text
from app.models.semantic_metadata import SemanticMetadata
from app.models.client_config import ClientConfig
from app.services.entity_selector import EntitySelector

# Mocking database setup for reproduction
DATABASE_URL = "sqlite:///repro.db"
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

def setup_repro():
    SQLModel.metadata.create_all(engine)
    
    with SessionLocal() as session:
        # Create a test client
        client = ClientConfig(
            client_name="Test Client",
            api_key="test_key",
            db_connection_url="sqlite:///repro_client.db"
        )
        session.add(client)
        session.commit()
        session.refresh(client)
        
        # Create semantic metadata with synonyms for a table
        sem = SemanticMetadata(
            client_id=client.id,
            table_name="mst_enquiry",
            column_name="", # Table level
            label="Enquiry",
            synonyms=["inquiry", "ticket", "support request"]
        )
        session.add(sem)
        session.commit()
        return client.id

async def test_entity_resolution(client_id):
    # EntitySelector.resolve_ambiguous_entity expects an AsyncSession
    # but we'll try to pass a sync one if we can or mock it.
    # Actually, let's keep it async but use a mock session if needed.
    # Wait, EntitySelector.resolve_ambiguous_entity uses await session.execute(stmt)
    # So we MUST use AsyncSession or mock it.
    
    # Let's mock the session
    class MockSession:
        def __init__(self, data):
            self.data = data
        async def execute(self, stmt):
            class Result:
                def __init__(self, data):
                    self._data = data
                def scalars(self):
                    return self
                def all(self):
                    return self._data
            return Result(self.data)

    mock_session = MockSession([
        SemanticMetadata(
            client_id=client_id,
            table_name="mst_enquiry",
            column_name="", 
            label="Enquiry",
            synonyms=["inquiry", "ticket", "support request"]
        )
    ])

    available_tables = ["mst_enquiry", "other_table"]
    
    # Test 1: Resolve 'enquiry' (exact label)
    print("\nTest 1: Resolve 'enquiry' (exact label)")
    matches = await EntitySelector.resolve_ambiguous_entity("enquiry", client_id, mock_session, available_tables)
    print(f"Matches for 'enquiry': {matches}")
    
    # Test 2: Resolve 'inquiry' (synonym)
    print("\nTest 2: Resolve 'inquiry' (synonym)")
    matches = await EntitySelector.resolve_ambiguous_entity("inquiry", client_id, mock_session, available_tables)
    print(f"Matches for 'inquiry': {matches}")

if __name__ == "__main__":
    # We can skip setup_repro if we mock the session
    asyncio.run(test_entity_resolution(1))
