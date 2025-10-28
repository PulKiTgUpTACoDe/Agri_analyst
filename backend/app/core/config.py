"""Centralized configuration using Pydantic settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from dotenv import load_dotenv
load_dotenv()


class Settings(BaseSettings):
    # API Keys
    GOV_API_KEY: str
    GOOGLE_API_KEY: str
    
    # Model Config
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_TEMPERATURE: float = 0.3
    GEMINI_MAX_TOKENS: int = 8192
    
    # API Endpoints
    daily_prices_endpoint: str = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
    variety_prices_endpoint: str = "https://api.data.gov.in/resource/35be999b-0208-4354-b557-f6ca9a5355de"
    crop_production_endpoint: str = "https://api.data.gov.in/resource/35be999b-0208-4354-b557-f6ca9a5355de"
    temperature_endpoint: str = "https://api.data.gov.in/resource/08d46edd-f960-43b9-912b-271e22836976"
    rainfall_endpoint: str = "https://api.data.gov.in/resource/8e0bd482-4aba-4d99-9cb9-ff124f6f1c2f"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
