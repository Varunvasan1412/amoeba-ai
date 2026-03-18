from typing import Optional

def detect_greeting(text: str) -> Optional[str]:
    """
    Detects if the user input is a greeting and returns a template response.
    Returns None if no greeting is detected.
    """
    greetings = ["hi", "hello", "hey", "good morning", "good evening", "thanks", "thank you", "how are you", "who are you", "how's it going"]
    text_lower = text.lower().strip().replace("?", "").replace("!", "")
    
    # Check for exact matches or starting with greeting
    for g in greetings:
        if text_lower == g or text_lower.startswith(g + " "):
            return "Hello! I'm functioning properly and ready to assist you. How can I help with your ERP today?"
            
    return None
