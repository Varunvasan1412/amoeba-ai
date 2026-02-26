
import asyncio
import os
import sys
import time

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.services.llm_service import get_response
from app.services.rag_service import rag_engine

async def test_performance():
    print("🚀 Starting Performance Test...")
    
    # Init RAG
    t0 = time.time()
    await rag_engine.initialize()
    print(f"✅ RAG Init took: {time.time() - t0:.2f}s")
    
    user_input = "navigate to purchase order"
    print(f"\n👤 User Input: {user_input}")
    
    t1 = time.time()
    print("⏳ Sending to LLM...")
    try:
        text, actions = await get_response(user_input, history=[])
        duration = time.time() - t1
        
        print(f"✅ Response received in {duration:.2f}s")
        print(f"📄 Text: {text}")
        print(f"⚡ Actions: {actions}")
        
        if duration > 10:
            print("⚠️ SLOW RESPONSE: Model loading or network latency.")
        else:
            print("🚀 FAST RESPONSE.")
            
    except Exception as e:
        print(f"💥 CRASH: {e}")

if __name__ == "__main__":
    asyncio.run(test_performance())
