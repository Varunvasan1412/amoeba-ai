
import os
import time
from langchain_google_genai import ChatGoogleGenerativeAI
from app.core.config import settings

# Manual list of likely free-tier models
CANDIDATES = [
    "gemini-2.0-flash-lite-preview-02-05", # Newest lightweight
    "gemini-1.5-flash",        # Standard workhorse
    "gemini-1.5-flash-8b",     # Ultra-light
    "gemini-1.5-pro",          # Standard Pro
    "gemini-1.0-pro"           # Legacy
]

api_key = settings.GOOGLE_API_KEY
if not api_key:
    # Fallback to reading env directly if settings fails (e.g. context issues)
    import dotenv
    dotenv.load_dotenv("backend/.env")
    api_key = os.getenv("GOOGLE_API_KEY")

print(f"🔑 Testing Key: {api_key[:5]}...{api_key[-5:] if api_key else 'None'}\n")

for model in CANDIDATES:
    print(f"👉 Testing Model: {model} ...", end=" ", flush=True)
    try:
        llm = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=0,
            max_retries=0 # Fail fast
        )
        
        start = time.time()
        response = llm.invoke("Hi")
        duration = time.time() - start
        
        print(f"✅ SUCCESS ({duration:.2f}s)")
        print(f"   Output: {response.content}")
        
        # Determine strict winner? No, lets just list them all.
        
    except Exception as e:
        error_str = str(e)
        if "404" in error_str:
            print("❌ 404 NOT FOUND (Model doesn't exist)")
        elif "429" in error_str:
             print("❌ 429 RATE LIMIT (Quota exceeded)")
        else:
             print(f"❌ ERROR: {error_str[:100]}...")
    
    time.sleep(1) # Be nice to the API
