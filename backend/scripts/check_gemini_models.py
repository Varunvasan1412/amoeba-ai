import os
import google.generativeai as genai

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("ERROR: GOOGLE_API_KEY not found in environment.")
else:
    genai.configure(api_key=api_key)
    print("Valid Models for generateContent:")
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f" - {m.name}")
    except Exception as e:
        print(f"Error: {e}")
