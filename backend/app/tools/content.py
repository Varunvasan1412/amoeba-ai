import httpx
from app.core.config import settings

def search_unsplash_image(query: str) -> str:
    """
    Searches Unsplash for an image matching the query.
    Returns a URL.
    """
    print(f"📷 SEARCHING UNSPLASH API FOR: {query}")
    
    if not settings.UNSPLASH_ACCESS_KEY:
        print("⚠️ No Unsplash Key found. Falling back to LoremFlickr for relevant images")
        # LoremFlickr allows /width/height/keyword
        return f"https://loremflickr.com/800/600/{query}"

    try:
        url = "https://api.unsplash.com/search/photos"
        params = {
            "query": query,
            "client_id": settings.UNSPLASH_ACCESS_KEY,
            "per_page": 1,
            "orientation": "landscape"
        }
        
        # Use sync httpx for now since this tool is defined as sync in llm_service
        response = httpx.get(url, params=params, timeout=10.0)
        
        if response.status_code == 200:
            data = response.json()
            if data["results"]:
                # Get the regular sized image
                return data["results"][0]["urls"]["regular"]
            else:
                return f"https://loremflickr.com/800/600/{query}"
        else:
            print(f"❌ Unsplash API Error: {response.status_code} - {response.text}")
            return f"https://loremflickr.com/800/600/{query}"
            
    except Exception as e:
        print(f"❌ Unsplash Exception: {e}")
        return f"https://loremflickr.com/800/600/{query}"
