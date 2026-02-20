import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Worker service configuration."""
    model_config = SettingsConfigDict(env_file=".env")

    # Database
    database_url: str = "postgresql+asyncpg://user:password@localhost/linkedin_autopilot"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # LinkedIn Automation Settings
    linkedin_session_cookie: str = ""  # li_at cookie value
    headless_browser: bool = True
    browser_timeout: int = 30000  # 30 seconds

    # Rate Limiting
    daily_search_limit: int = 50
    daily_application_limit: int = 20

    # Delay Settings (in seconds)
    min_action_delay: float = 1.0
    max_action_delay: float = 3.0
    min_navigation_delay: float = 2.0
    max_navigation_delay: float = 5.0
    min_search_delay: float = 3.0
    max_search_delay: float = 8.0

    # Retry Settings
    max_retries: int = 3
    base_backoff_delay: float = 1.0

    # Logging
    log_level: str = "INFO"


settings = Settings()
