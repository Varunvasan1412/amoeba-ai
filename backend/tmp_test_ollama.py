import asyncio
import httpx
import time

async def test_ollama():
    url = "http://host.docker.internal:11434/api/generate"
    payload = {
        "model": "llama3",
        "prompt": "Say hello world briefly.",
        "stream": False
    }
    
    print(f"📡 Testing Ollama at {url}...")
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
    asyncio.run(test_ollama())
