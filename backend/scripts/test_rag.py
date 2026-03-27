
import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.services.rag_service import rag_engine

async def test_rag():
    print("🚀 Starting RAG Verification Debug...")
    
    try:
        # 1. Initialize
        await rag_engine.initialize()
        
        # 2. Test Navigation Retrieval
        print("\n--- TEST 1: Navigation Retrieval ('Navigate to sales') ---")
        context = await rag_engine.retrieve_context("Navigate to sales")
        print(f"Context Length: {len(context)}")
        if "[NAVIGATION]" in context:
            print("✅ PASS: Navigation found")
        else:
            print(f"❌ FAIL: Navigation NOT found. Context: {context}")

        # 3. Test Schema Retrieval ('users')
        print("\n--- TEST 2: Schema Retrieval ('Show users') ---")
        context = await rag_engine.retrieve_context("Show users")
        if "users" in context.lower():
             print("✅ PASS: Schema found (keyword 'users')")
        else:
             print(f"❌ FAIL: Schema NOT found. Context: {context}")
        
        # 4. Test Reports Retrieval ('report')
        print("\n--- TEST 3: Report Retrieval ('sales report') ---")
        context = await rag_engine.retrieve_context("sales report")
        if "[REPORTS]" in context:
            print("✅ PASS: Reports found")
        else:
            # Maybe just config issue, but report_definitions.json was created.
            print(f"❌ FAIL: Reports NOT found. Context: {context}")

        # 5. Test Rules Retrieval ('delete')
        print("\n--- TEST 4: Rules Retrieval ('delete invoice') ---")
        context = await rag_engine.retrieve_context("delete invoice")
        if "[BUSINESS RULES]" in context:
            print("✅ PASS: Rules found")
        else:
            print(f"❌ FAIL: Rules NOT found. Context: {context}")
            
    except Exception as e:
        print(f"💥 EXCEPTION: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_rag())
