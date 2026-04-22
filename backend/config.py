"""
Configuration settings for VKS AI Platform
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # App
    APP_NAME: str = os.getenv("APP_NAME", "VKS AI Platform")
    APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "vks-secret-key-change-in-production-2024")
    
    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # MongoDB
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    MONGODB_DB: str = os.getenv("MONGODB_DB", "vks_ai_platform")
    
    # Ollama
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "qwen3:30b-a3b")
    
    # Admin
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "vks@2024")
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))
    
    # API Key
    API_KEY_PREFIX: str = "vks-"
    API_KEY_LENGTH: int = 48


settings = Settings()
