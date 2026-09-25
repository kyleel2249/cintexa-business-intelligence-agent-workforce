"""CINTEXA BI configuration loaded from environment."""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "CINTEXA Business Intelligence"
    app_env: str = "development"
    debug: bool = True
    secret_key: str = "change-me-to-a-long-random-string"
    api_prefix: str = "/bi"

    database_url: str = "sqlite+aiosqlite:///./cintexa_bi.db"
    redis_url: str = "redis://localhost:6379/0"

    access_token_expire_minutes: int = 60
    algorithm: str = "HS256"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    # OpenRouter (sk-or-v1-…) — OpenAI-compatible; model ids are provider/model
    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-4o"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-20241022"

    serper_api_key: str = ""
    tavily_api_key: str = ""

    cors_origins: str = "http://localhost:3000,http://localhost:8000,https://cintexa-business-intelligence-agent-workforce.pages.dev"
    rate_limit_per_minute: int = 60
    organisation_isolation: bool = True

    enable_human_approval: bool = True
    enable_web_research: bool = True
    enable_forecasting: bool = True
    max_agent_retries: int = 3
    default_confidence_threshold: float = 0.6

    log_level: str = "INFO"
    structured_logs: bool = True

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
