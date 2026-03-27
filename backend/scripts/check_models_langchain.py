
import asyncio
from langchain_google_genai import ChatGoogleGenerativeAI
from app.core.config import settings
import os

async def test_models():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ NO API KEY")
        return

    # List of common model strings to try
    models = [
        "gemini-1.5-flash",
        "gemini-1.5-flash-latest",
        "gemini-1.5-pro",
        "gemini-pro"
    ]

    for model_name in models:
        print(f"Testing model: {model_name}...")
        try:
            llm = ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key)
            res = await llm.ainvoke("Hi")
            print(f" ✅ SUCCESS: {model_name}")
            return # Stop at first working one
        except Exception as e:
            print(f" ❌ FAILED: {model_name}. Error: {str(e)[:100]}")

if __name__ == "__main__":
    asyncio.run(test_models())
