import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    # Database
    database_url: str = "postgresql+asyncpg://user:password@localhost/linkedin_autopilot"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # JWT
    secret_key: str = "your-secret-key"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # File uploads
    max_upload_size: int = 10 * 1024 * 1024  # 10MB
    allowed_extensions: set = {".pdf", ".doc", ".docx"}

    # Logging
    log_level: str = "INFO"

settings = Settings()