from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from dotenv import load_dotenv
load_dotenv()

class Settings(BaseSettings):
    GOV_API_KEY: str
    GOOGLE_API_KEY: str
    CORS_ORIGINS: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_TEMPERATURE: float = 0.3
    GEMINI_MAX_TOKENS: int = 8192
    LOG_LEVEL: str = "INFO"
    CACHE_MAX_SIZE: int = 500
    CACHE_DEFAULT_TTL: int = 3600

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore")

@lru_cache
def get_settings() -> Settings:
    return Settings()
