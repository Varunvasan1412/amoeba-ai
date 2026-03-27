
import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load from backend directory
load_dotenv("backend/.env")

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("❌ GOOGLE_API_KEY not found in .env")
else:
    print(f"🔑 API Key found (starts with: {api_key[:5]}...)")
    genai.configure(api_key=api_key)
    
    print("
Listing available models...")
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f" - {m.name}")
    except Exception as e:
        print(f"❌ Error listing models: {e}")
