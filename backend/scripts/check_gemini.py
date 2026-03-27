
import os
import time
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

# Load env from backend/.env
env_path = os.path.join(os.path.dirname(__file__), "../.env")
load_dotenv(env_path)

api_key = os.getenv("GOOGLE_API_KEY")

print(f"🔑 API Key Loaded: {'Yes' if api_key else 'No'}")
print("🚀 Initializing ChatGoogleGenerativeAI (gemini-2.0-flash-lite)...")

try:
    llm = ChatGoogleGenerativeAI(
        model="gemini-flash-latest", 
        google_api_key=api_key,
        temperature=0,
        max_retries=1
    )
    
    start = time.time()
    print("⏳ Invoking LLM (gemini-flash-latest)...")
    response = llm.invoke([HumanMessage(content="Hi")])
    duration = time.time() - start
    
    print(f"✅ Response Received in {duration:.2f}s")
    print(f"💬 Content: {response.content}")

except Exception as e:
    print(f"❌ Error caught.")
    with open("gemini_error.txt", "w") as f:
        f.write(str(e))
