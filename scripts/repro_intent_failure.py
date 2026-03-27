import asyncio
import sys
import os

# Add backend to sys.path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.models.semantic_metadata import SemanticMetadata
from app.models.navigation import NavigationItem
from app.services.entity_selector import EntitySelector
from app.services.intent_service import normalize_entity_name

async def test_entity_resolution():
    # Let's mock the session
    class MockSession:
        def __init__(self, sem_data, nav_data):
            self.sem_data = sem_data
            self.nav_data = nav_data
            self.call_count = 0

        async def execute(self, stmt):
            self.call_count += 1
            # First call is SemanticMetadata, Second is NavigationItem
            data = self.sem_data if self.call_count == 1 else self.nav_data
            
            class Result:
                def __init__(self, data):
                    self._data = data
                def scalars(self):
                    return self
                def all(self):
                    return self._data
            return Result(data)

    mock_sem = [
        SemanticMetadata(
            client_id=1,
            table_name="mst_enquiry",
            column_name="", 
            label="Enquiry",
            synonyms=["ticket", "support request"] # Removed 'inquiry' to test normalization
        )
    ]
    mock_nav = [
        NavigationItem(
            client_id=1,
            label="Sales",
            path="/sales",
            table_name="mst_sales"
        )
    ]

    available_tables = ["mst_enquiry", "mst_sales", "other_table"]
    
    # Test 1: Resolve 'inquiry' (normalization)
    print("\nTest 1: Resolve 'inquiry' (normalization)")
    mock_session = MockSession(mock_sem, mock_nav)
    matches = await EntitySelector.resolve_ambiguous_entity("inquiry", 1, mock_session, available_tables)
    print(f"Matches for 'inquiry': {matches}")
    
    # Test 2: Resolve 'soles' (normalization/typo)
    print("\nTest 2: Resolve 'soles' (normalization/typo)")
    mock_session = MockSession(mock_sem, mock_nav)
    matches = await EntitySelector.resolve_ambiguous_entity("soles", 1, mock_session, available_tables)
    print(f"Matches for 'soles': {matches}")

    # Test 3: Resolve 'solas' (fuzzy - not in normalization)
    print("\nTest 3: Resolve 'solas' (fuzzy)")
    mock_session = MockSession(mock_sem, mock_nav)
    matches = await EntitySelector.resolve_ambiguous_entity("solas", 1, mock_session, available_tables)
    print(f"Matches for 'solas': {matches}")

if __name__ == "__main__":
    asyncio.run(test_entity_resolution())
