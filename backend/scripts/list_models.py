
import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load env from backend/.env
load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))

api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("❌ GOOGLE_API_KEY not found in .env")
    exit(1)

genai.configure(api_key=api_key)

print("🔍 Listing Available Models...")
try:
    models = genai.list_models()
    with open("temp_models.txt", "w") as f:
        for m in models:
            # Filter for generateContent supported models
            if 'generateContent' in m.supported_generation_methods:
                f.write(f"{m.name}\n")
                print(f"- {m.name}")
    print("✅ Saved to temp_models.txt")
except Exception as e:
    print(f"❌ Error: {e}")
