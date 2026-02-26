import sys
import os
import asyncio
from unittest.mock import MagicMock

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# MOCK Dependencies
sys.modules["app.tools.reporting"] = MagicMock()
sys.modules["app.tools.reporting"].export_sql_to_excel.return_value = "/app/static/reports/test.xlsx"

sys.modules["app.tools.dates"] = MagicMock()
def mock_dates(query):
    if "today" in query or "daily" in query:
        return "2023-10-27", "2023-10-27"
    return None, None
sys.modules["app.tools.dates"].normalize_date_range.side_effect = mock_dates

sys.modules["app.tools.filenames"] = MagicMock()
sys.modules["app.tools.filenames"].generate_deterministic_filename.return_value = "test_report.xlsx"

# Mock Config
mock_config = MagicMock()
mock_config.settings.PUBLIC_BASE_URL = "http://localhost:8000"
sys.modules["app.core.config"] = mock_config
sys.modules["pydantic_settings"] = MagicMock()

from app.services.report_registry_service import registry
from app.services.fastpath_service import execute_fastpath

async def test_per_client_isolation():
    print("--- TESTING PER-CLIENT ISOLATION ---")

    # 1. Setup Registries
    # Client A has "Daily Production"
    client_a_reports = [{
      "id": "daily_production",
      "display_name": "Daily Production (Client A)",
      "keywords": ["daily production"],
      "sql_template": "SELECT * FROM prod_log",
      "required_params": [], # Simplify for test
      "export_formats": ["xlsx"]
    }]
    registry.register_reports("client_a", client_a_reports)
    
    # Client B has NOTHING
    registry.register_reports("client_b", [])

    # 2. Test Client A (Should Succeed)
    print("\n[Step 1] Client A: 'generate daily production'")
    text_a, actions_a = await execute_fastpath("generate daily production", {"client_id": "client_a"})
    
    if "Export Complete" in text_a:
        print(f"[PASS] Client A Success: {text_a}")
    else:
        print(f"[FAIL] Client A Failed: {text_a}")
        sys.exit(1)

    # 3. Test Client B (Should Fail - No Report)
    print("\n[Step 2] Client B: 'generate daily production'")
    # Should fall through to LLM (return None) or Export Intent Block (return Error)
    # "daily production" triggers "production" -> "export/report" keywords?
    # No, my regex is "export|...|report". "daily production" has neither.
    # So for Client B, it should return None (fallthrough to LLM).
    # Wait, the prompt said: "If export intent detected ... reject".
    # Since "daily production" doesn't have "report" keyword, it's ambiguous if it's export intent for generic detector.
    # Let's try "generate daily production report" for Client B.
    
    text_b, actions_b = await execute_fastpath("generate daily production report", {"client_id": "client_b"})
    
    if "not registered" in text_b:
        print(f"[PASS] Client B Rejected (Unregistered): {text_b}")
    else:
        print(f"[FAIL] Client B NOT Rejected properly. Got: {text_b}")
        sys.exit(1)
        
    print("\n✅ PER-CLIENT ISOLATION PASSED")

if __name__ == "__main__":
    asyncio.run(test_per_client_isolation())
