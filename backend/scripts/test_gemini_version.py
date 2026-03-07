
import asyncio
import os
from langchain_google_genai import ChatGoogleGenerativeAI

async def test():
    api_key = os.getenv("GOOGLE_API_KEY")
    try:
        print("Testing models/gemini-1.5-flash...")
        llm = ChatGoogleGenerativeAI(model="models/gemini-1.5-flash", google_api_key=api_key)
        await llm.ainvoke("Hi")
        print("SUCCESS with models/gemini-1.5-flash")
    except Exception as e:
        print("FAILED: " + str(e))

    try:
        print("Testing gemini-pro...")
        llm = ChatGoogleGenerativeAI(model="gemini-pro", google_api_key=api_key)
        await llm.ainvoke("Hi")
        print("SUCCESS with gemini-pro")
    except Exception as e:
        print("FAILED: " + str(e))

if __name__ == "__main__":
    asyncio.run(test())
