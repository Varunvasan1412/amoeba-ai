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


    class Config:
        env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
        extra = "ignore"

settings = Settings()
print(f"🔧 CONFIG: AI Provider: {settings.AI_PROVIDER}")
print(f"🔧 CONFIG: Google Key Loaded: {bool(settings.GOOGLE_API_KEY)}")
