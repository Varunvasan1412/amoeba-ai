import asyncio
import httpx
import time

async def test_ollama_real_prompt():
    url = "http://host.docker.internal:11434/api/generate"
    
    # Simulating the actual system prompt from assistant_service.py
    context = "Page: Enquiry | Path: /enquiry | Module: CRM\nPage: Create Enquiry | Path: /enquiry/create"
    user_input = "how to create an enquiry"
    system_prompt = f"ERP Assistant. Brief answer based on context:\n{context}\nNav: [NAVIGATE: /path]"
    
    # ChatOllama uses /api/chat usually, but let's test /api/generate first for raw speed
    payload = {
        "model": "llama3.2:latest",
        "prompt": f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{system_prompt}<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n{user_input}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n",
        "stream": False,
        "options": {
            "num_predict": 128
        }
    }
    
    print(f"📡 Testing Ollama llama3.2 with REAL PROMPT at {url}...")
    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload)
            duration = time.time() - start_time
            if response.status_code == 200:
                print(f"✅ Success in {duration:.2f}s!")
                print(f"📄 Response: {response.json().get('response')}")
            else:
                print(f"❌ Failed with status {response.status_code}")
                print(f"📄 Error: {response.text}")
    except Exception as e:
        print(f"💥 Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_ollama_real_prompt())
