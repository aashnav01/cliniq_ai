import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Gemini Configuration (primary LLM)
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "").strip()

    # Groq Configuration (Whisper STT only)
    groq_api_key: str = os.getenv("GROQ_API_KEY", "").strip()

    # MongoDB Atlas
    mongodb_uri: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017").strip()

    # Redis (optional)
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Application
    environment: str = os.getenv("ENVIRONMENT", "development")
    backend_url: str = os.getenv("BACKEND_URL", "http://localhost:8000")
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

    # Security
    secret_key: str = os.getenv("SECRET_KEY", "change-this-in-production-use-a-long-random-string")
    algorithm: str = "HS256"

    class Config:
        env_file = str(Path(__file__).resolve().parent.parent / ".env")
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "allow"


settings = Settings()
