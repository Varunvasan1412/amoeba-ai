import sys
import os
import asyncio
from unittest.mock import MagicMock

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# MOCK Dependencies
sys.modules["app.tools.reporting"] = MagicMock()
sys.modules["app.tools.dates"] = MagicMock()
sys.modules["app.tools.filenames"] = MagicMock()

# Mock Config
mock_config = MagicMock()
mock_config.settings.PUBLIC_BASE_URL = "http://localhost:8000"
sys.modules["app.core.config"] = mock_config
sys.modules["pydantic_settings"] = MagicMock()

from app.services.fastpath_service import execute_fastpath

async def run_diagnostic():
    print("--- DIAGNOSTIC RUN: AMBIGUITY OUTPUT ---")
    
    # 1. Simulate Ambiguity Trigger
    # user_input = "navigate to completed"
    print("Input: 'navigate to completed'")
    
    # Context empty initially
    text, actions = await execute_fastpath("navigate to completed", {})
    
    print("\n[RAW BACKEND RESPONSE TEXT]")
    print(repr(text))
    print("\n[RAW BACKEND ACTIONS]")
    print(actions)
    
    print("\n[ANALYSIS]")
    if "1) " in text and "2) " in text:
        print("✅ Backend IS sending numbers.")
    else:
        print("❌ Backend is NOT sending numbers.")

if __name__ == "__main__":
    asyncio.run(run_diagnostic())
