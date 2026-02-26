from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Amoeba AI"

    # ----------------------------
    # AI / LLM CONFIG
    # ----------------------------
    AI_PROVIDER: str = "GEMINI"
    GOOGLE_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    DEEPSEEK_API_KEY: Optional[str] = None
    UNSPLASH_ACCESS_KEY: Optional[str] = None

    # Local / Self-hosted LLM
    OLLAMA_BASE_URL: str = "http://host.docker.internal:11434"
    OLLAMA_MODEL: str = "llama3.2"

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
        env_file = ".env"
        extra = "ignore"

settings = Settings()
