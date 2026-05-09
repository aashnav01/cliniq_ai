import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Groq Configuration
    groq_api_key: str = os.getenv("GROQ_API_KEY", "").strip()
    groq_model: str = "llama-3.3-70b-versatile"  # Updated: mixtral-8x7b-32768 was deprecated

    # Database
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./cliniq.db").strip()

    # Redis
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
