
import asyncio
import os
import sys
import pandas as pd
import time
import logging

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.services.llm_service import get_response, rag_engine
from app.services.fastpath_service import execute_fastpath
from app.core.context import current_db_url

# SIMULATED ROUTER (Mimics app/routers/chat.py)
async def get_response_via_router(user_input):
    # 1. Router Check
    fast_text, fast_actions = await execute_fastpath(user_input)
    if fast_text:
        return fast_text, fast_actions
        
    # 2. Fallback to Slow Path
    return await get_response(user_input)

def setup_mock_db():
    import sqlite3
    db_path = "test_fastpath.db"
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # Table from report_execution_templates.json: "sales_orders"
    cursor.execute("CREATE TABLE IF NOT EXISTS sales_orders (id INTEGER, total_amount REAL, status TEXT, order_date TEXT, customer_id INTEGER)")
    cursor.execute("INSERT INTO sales_orders VALUES (1, 100.0, 'finalized', '2023-01-01', 101)")
    cursor.execute("INSERT INTO sales_orders VALUES (2, 200.0, 'pending', '2023-01-02', 102)")
    conn.commit()
    conn.close()
    
    db_url = f"sqlite:///{os.path.abspath(db_path)}"
    current_db_url.set(db_url)
    return db_path

# MOCK Schema to avoid RAG init crash (due to missing aiosqlite)
async def mock_get_database_schema():
    return "Table: sales_orders, Columns: id, total_amount, status"

import app.services.rag_service as rag_svc
rag_svc.get_database_schema = mock_get_database_schema

# Mock Logger to verify "LLM CALLED"
class MockLogger(logging.Logger):
    def __init__(self, name):
        super().__init__(name)
        self.logs = []
    def info(self, msg, *args, **kwargs):
        self.logs.append(msg)
        print(f"LOG: {msg}")

async def test_fast_paths():
    print("🚀 Starting STRICT FAST-PATH Verification...")
    
    # 1. Setup
    db_path = setup_mock_db()
    
    # Inject Mock Logger
    mock_logger = MockLogger("uvicorn")
    import app.services.llm_service
    # We need to intercept where `logging.getLogger("uvicorn")` is called.
    # But getLogger returns a standard logger. 
    # Logic in service: logger = logging.getLogger("uvicorn"); logger.info(...)
    # We can patch logging.getLogger
    original_getLogger = logging.getLogger
    def side_effect_getLogger(name):
        if name == "uvicorn": return mock_logger
        return original_getLogger(name)
    logging.getLogger = side_effect_getLogger
    
    try:
        # TEST 1: EXPORT FAST-PATH
        print("\n🧪 TEST 1: 'Export Sales Summary' (Expect Fast-Path)")
        mock_logger.logs = []
        start = time.time()
        
        rsp, actions = await get_response_via_router("Export Sales Summary")
        
        duration = time.time() - start
        
        print(f"⏱️ Duration: {duration:.4f}s")
        print(f"📝 Response: {rsp}")
        
        if "LLM CALLED" in mock_logger.logs:
             print("❌ FAIL: LLM was called! Fast-Path violation.")
        else:
             print("✅ PASS: LLM was BYPASSED.")
             
        if "Tool generate_excel" in str(actions) or "TOOL_RESULT" in str(actions):
             print("✅ PASS: Export Tool Executed.")
        else:
             print("❌ FAIL: No export action.")

        # TEST 4: UNRESOLVED EXPORT INTENT (Control Flow Check)
        print("\n🧪 TEST 4: 'extract the production reports' (Expect Clarification/Fail safely, NO CRASH)")
        mock_logger.logs = []
        try:
             rsp, actions = await get_response_via_router("extract the production reports and convert to .xlsx")
             print(f"📝 Response: {rsp}")
             if "Available reports" in rsp or "Export Complete" in rsp:
                  print("✅ PASS: Handled safely (Clarification or Success), NO LLM Crash.")
             else:
                  print(f"⚠️ WARNING: Unexpected response: {rsp}")

             if "LLM CALLED" in mock_logger.logs:
                  print("❌ FAIL: LLM was called! Control Flow Violation.")
             else:
                  print("✅ PASS: LLM was BYPASSED.")
        except RuntimeError as e:
             if "FAST-PATH VIOLATION" in str(e):
                  print("❌ FAIL: CRASHED with FAST-PATH VIOLATION. Control flow fix failed.")
             else:
                  raise e

        print("\n🧪 TEST 2: 'Navigate to Sales' (Expect Fast-Path)")
        mock_logger.logs = []
        start = time.time()
        
        rsp, actions = await get_response_via_router("navigate to sales")
        
        duration = time.time() - start
        if "LLM CALLED" in mock_logger.logs:
             print("❌ FAIL: LLM was called! Fast-Path violation.")
        else:
             print("✅ PASS: LLM was BYPASSED.")
             
        # TEST 3: NORMAL CHAT (Expect LLM)
        print("\n🧪 TEST 3: 'Tell me a joke' (Expect LLM)")
        mock_logger.logs = []
        
        # We need to un-mock DB or ensure it doesn't crash LLM
        # LLM needs API Key. If not present, it will return error but SHOULD log "LLM CALLED".
        try:
            rsp, _ = await get_response_via_router("Tell me a joke")
            print(f"📝 Response: {rsp}")
            if "FAST-PATH VIOLATION" in str(rsp):
                 print("✅ PASS: LLM Crudely Crashed as expected: FAST-PATH VIOLATION Confirmed.")
            else:
                 print(f"❌ FAIL: Expected crash, got: {rsp}")
        except Exception as e:
             if "fast-path violation" in str(e).lower():
                  print("✅ PASS: LLM Crudely Crashed as expected (Exception).")
             else:
                  print(f"❌ FAIL: Unrelated Crash: {e}")
            
        # Check logs too, though 'get_response' catches exceptions so logs might show up
        if any("LLM CALLED" in log for log in mock_logger.logs):
             print("ℹ️ Info: Logger caught the 'LLM CALLED' critical log.")

    finally:
        # Cleanup
        logging.getLogger = original_getLogger
        if os.path.exists(db_path.replace("sqlite:///", "")):
            try:
                os.remove(db_path.replace("sqlite:///", ""))
            except: pass

if __name__ == "__main__":
    asyncio.run(test_fast_paths())
