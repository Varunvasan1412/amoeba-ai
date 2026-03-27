
import os
from google import genai

def list_models():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("NO API KEY")
        return
    
    client = genai.Client(api_key=api_key)
    print("Listing models with google-genai SDK...")
    try:
        for model in client.models.list():
            print(f" - {model.name}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_models()
