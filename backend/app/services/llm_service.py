from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from app.core.config import settings
from functools import lru_cache
import os

@lru_cache()
def get_brain():
    provider = settings.AI_PROVIDER.upper()
    
    # --- DEBUGGING BLOCK ---
    print(f"\n🧠 INITIALIZING BRAIN: {provider}")
    if provider == "GEMINI":
        key = settings.GOOGLE_API_KEY
        if key:
            print(f"🔑 Key Found: {key[:5]}...{key[-4:]}") # Prints first/last chars
        else:
            print("❌ ERROR: GOOGLE_API_KEY is Empty/None!")
    # -----------------------

    try:
        if provider == "GEMINI":
            if not settings.GOOGLE_API_KEY:
                return None
            return ChatGoogleGenerativeAI(
                model="gemini-1.5-flash", # Let's try Flash again, it's the standard
                google_api_key=settings.GOOGLE_API_KEY,
                temperature=0.7
            )

        elif provider == "GPT4":
            if not settings.OPENAI_API_KEY:
                return None
            return ChatOpenAI(
                model="gpt-4-turbo",
                api_key=settings.OPENAI_API_KEY,
                temperature=0.7
            )

        elif provider == "OLLAMA":
            print("🦙 Using Local Llama 3...")
            return ChatOllama(
                model="llama3", 
                base_url="http://host.docker.internal:11434",
                temperature=0.7
            )
            
    except Exception as e:
        print(f"💥 CRASH initializing brain: {e}")
        return None

    return None

def get_response(user_input: str):
    llm = get_brain()
    
    if not llm:
        return "System Error: AI Brain failed to initialize. Check server logs."

    try:
        response = llm.invoke(user_input)
        return response.content
    except Exception as e:
        print(f"Invoke Error: {e}")
        return f"I'm having trouble connecting to {settings.AI_PROVIDER}. Error: {str(e)}"