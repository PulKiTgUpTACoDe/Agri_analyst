"""Centralized configuration using Pydantic settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from dotenv import load_dotenv
load_dotenv()


class Settings(BaseSettings):
    # API Keys
    GOV_API_KEY: str
    GOOGLE_API_KEY: str
    
    # CORS Configuration
    CORS_ORIGINS: str = ""  
    
    # Model Config
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_TEMPERATURE: float = 0.3
    GEMINI_MAX_TOKENS: int = 8192
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    # Cache settings
    CACHE_MAX_SIZE: int = 500
    CACHE_DEFAULT_TTL: int = 3600  # 1 hour
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
