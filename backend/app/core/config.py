from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Amoeba AI"
    AI_PROVIDER: str = "GEMINI"
    GOOGLE_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    DEEPSEEK_API_KEY: Optional[str] = None
    
    # NEW: Database Config
    DATABASE_URL: str = "postgresql+asyncpg://user:password@db:5432/amoeba"

    class Config:
        env_file = ".env"

settings = Settings()