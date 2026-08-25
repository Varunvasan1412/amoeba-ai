from pydantic_settings import BaseSettings
from typing import Optional
import os
from dotenv import load_dotenv

# Explicitly find and load .env
def load_env_file():
    # Candidates for .env location
    candidates = [
        os.path.join(os.getcwd(), ".env"),                      # Root (relative to current working dir)
        os.path.join(os.getcwd(), "backend", ".env"),           # Backend folder (relative)
        "/app/.env",                                            # Docker internal path
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env") # Three levels up from this file
    ]
    
    for path in candidates:
        if os.path.exists(path):
            print(f"🔧 CONFIG: Loading .env from {path}")
            load_dotenv(path, override=True)
            return True
    print("⚠️ CONFIG: No .env file found in candidates.")
    return False

load_env_file()

class Settings(BaseSettings):
    PROJECT_NAME: str = "Amoeba AI"

    # ----------------------------
    # AI / LLM CONFIG
    # ----------------------------
    AI_PROVIDER: str = "GEMINI"
    GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY")
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    DEEPSEEK_API_KEY: Optional[str] = os.getenv("DEEPSEEK_API_KEY")
    UNSPLASH_ACCESS_KEY: Optional[str] = os.getenv("UNSPLASH_ACCESS_KEY")

    # Local / Self-hosted LLM
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")

    def get_ollama_url(self) -> str:
        """Helper to return the best URL for Ollama."""
        # If we are on Windows/Mac, host.docker.internal usually works.
        # But if we're not in Docker, it won't.
        return self.OLLAMA_BASE_URL

    # ----------------------------
    # DATABASE
    # ----------------------------
    DATABASE_URL: str = "postgresql+asyncpg://user:password@db:5432/amoeba"

    # ----------------------------
    # PUBLIC URL CONFIG (IMPORTANT)
    # ----------------------------
    # Used for generating downloadable file URLs (Excel, PDFs, etc.)
    # DO NOT hardcode localhost anywhere else in the codebase.

    # Change this to your production URL
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    # ----------------------------
    # AUTHENTICATION
    # ----------------------------
    SECRET_KEY: str = "your-secret-key-here" # Change this in production
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 1 week

    # ----------------------------
    # RATE LIMITING
    # ----------------------------
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
    REDIS_URL: Optional[str] = os.getenv("REDIS_URL", None)
    
    # Defaults in format "requests per time-unit"
    RATE_LIMIT_LOGIN: str = os.getenv("RATE_LIMIT_LOGIN", "5 per minute")
    RATE_LIMIT_CHAT: str = os.getenv("RATE_LIMIT_CHAT", "60 per minute")
    RATE_LIMIT_REPORT: str = os.getenv("RATE_LIMIT_REPORT", "30 per minute")
    RATE_LIMIT_EXPORT: str = os.getenv("RATE_LIMIT_EXPORT", "10 per minute")
    RATE_LIMIT_UPLOAD: str = os.getenv("RATE_LIMIT_UPLOAD", "5 per minute")
    RATE_LIMIT_HEALTH: str = os.getenv("RATE_LIMIT_HEALTH", "20 per minute")
    RATE_LIMIT_GLOBAL: str = os.getenv("RATE_LIMIT_GLOBAL", "100 per minute")


    class Config:
        env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
        extra = "ignore"

settings = Settings()
print(f"🔧 CONFIG: AI Provider: {settings.AI_PROVIDER}")
print(f"🔧 CONFIG: Google Key Loaded: {bool(settings.GOOGLE_API_KEY)}")
