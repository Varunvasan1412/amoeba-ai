from app.models.user import User
import logging

logger = logging.getLogger(__name__)

def mask_api_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 4:
        return "********"
    return "********" + key[-4:]

def sanitize_client_data(client_dict: dict, current_user: User) -> dict:
    """
    FEATURE 3 — API KEY VISIBILITY PROTECTION
    Masks the API key if the current user is not a platform admin.
    """
    if not current_user.is_platform_user:
        if "api_key" in client_dict:
            client_dict["api_key"] = mask_api_key(client_dict["api_key"])
    
    return client_dict
