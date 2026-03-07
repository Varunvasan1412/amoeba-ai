
import os
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
import asyncio

async def test():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("NO API KEY")
        return
    
    genai.configure(api_key=api_key)
    print("Listing models with genai.list_models()...")
    
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                model_name = m.name # This includes the version prefix usually like models/gemini-1.5-flash
                print(f"Trying {model_name}...")
                try:
                    # Strip 'models/' prefix if it's there because LangChain adds it sometimes?
                    # Actually, let's try exactly what it says.
                    name_to_try = model_name.replace("models/", "")
                    llm = ChatGoogleGenerativeAI(model=name_to_try, google_api_key=api_key)
                    await llm.ainvoke("Hi")
                    print(f"✅ SUCCESS with {name_to_try}")
                    # return 
                except Exception as e:
                    print(f"❌ Failed {name_to_try}: {str(e)[:100]}")
    except Exception as e:
        print(f"Error listing: {e}")

if __name__ == "__main__":
    asyncio.run(test())
