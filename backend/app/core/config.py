from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    GOOGLE_API_KEY: str
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/agri_data"

    class Config:
        env_file = ".env"

settings = Settings()
