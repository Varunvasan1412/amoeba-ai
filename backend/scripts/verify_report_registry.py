import sys
import os
import asyncio
from unittest.mock import MagicMock

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# MOCK Dependencies
sys.modules["app.tools.reporting"] = MagicMock()
# We need `app.tools.reporting.export_sql_to_excel` to return a dummy path
sys.modules["app.tools.reporting"].export_sql_to_excel.return_value = "/app/static/reports/test.xlsx"

sys.modules["app.tools.dates"] = MagicMock()
# Mock normalize_date_range to return dates when "yesterday" etc is present
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

from app.services.fastpath_service import execute_fastpath

async def test_report_registry():
    print("--- TESTING REPORT REGISTRY (STATEFUL) ---")
    
    # 1. Trigger Missing Param
    print("\n[Step 1] 'generate daily production report' (Missing Date)")
    # Mock date failure for this step
    # We rely on normalize_date_range NOT returning dates for this string unless "today" is in it.
    # "daily" might trigger it in our mock?
    # Let's adjust mock logic: "daily" triggers date?
    # Our current mock: if "today" or "daily" in query -> returns date.
    # So "generate daily production" matches "daily". fastpath automatically executes.
    # We want to TEST missing param.
    # So let's try "generate production report" (no "daily"). registry matches on keyword "production report".
    
    text, actions = await execute_fastpath("generate production report", {})
    
    if "Please provide a date range" in text:
        print(f"[PASS] Prompted for date: {text}")
    else:
        print(f"[FAIL] Expected prompt, got: {text}")
        sys.exit(1)

    # Check for SET_PENDING_REPORT
    context = {}
    for a in actions:
        if a["type"] == "SET_PENDING_REPORT":
            context["pending_report"] = a["payload"]
            
    if "pending_report" not in context:
        print("[FAIL] No SET_PENDING_REPORT action.")
        sys.exit(1)
        
    print(f"[PASS] Context captured: {context['pending_report']['display_name']}")

    # 2. Provide Date (Stateful)
    print("\n[Step 2] 'today' (With Context)")
    text_2, actions_2 = await execute_fastpath("today", context)
    
    if "Export Complete" in text_2:
        print(f"[PASS] Generated Report from Context: {text_2}")
    else:
        print(f"[FAIL] Expected export, got: {text_2}")
        sys.exit(1)

    # 3. Unregistered Report (Safety)
    print("\n[Step 3] 'generate monthly wastage report' (Unregistered)")
    text_fail, actions_fail = await execute_fastpath("generate monthly wastage report", {})
    
    if "not registered" in text_fail:
        print(f" [PASS] Correctly rejected unregistered report: {text_fail}")
    else:
        print(f" [FAIL] Expected rejection, got: {text_fail}")
        sys.exit(1)
        
    print("\n✅ REPORT REGISTRY TESTS PASSED")

if __name__ == "__main__":
    asyncio.run(test_report_registry())
