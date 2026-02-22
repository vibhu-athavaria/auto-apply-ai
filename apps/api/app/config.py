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

    # LLM Configuration
    openai_api_key: str = ""
    llm_model: str = "gpt-4"
    llm_max_tokens: int = 4000
    llm_temperature: float = 0.7

    # LLM Cost Tracking (per 1K tokens)
    # GPT-4 pricing as of 2024
    llm_prompt_cost_per_1k: float = 0.03
    llm_completion_cost_per_1k: float = 0.06

    # Redis TTL for LLM cache (7 days)
    llm_cache_ttl: int = 60 * 60 * 24 * 7

settings = Settings()