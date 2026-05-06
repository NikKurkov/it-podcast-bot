from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    telegram_api_id: int = Field(default=0, alias="TELEGRAM_API_ID")
    telegram_api_hash: str = Field(default="", alias="TELEGRAM_API_HASH")
    telegram_session_name: str = Field(default="it_podcast_bot", alias="TELEGRAM_SESSION_NAME")
    database_url: str = Field(
        default="sqlite:///data/it_podcast_bot.sqlite3",
        alias="DATABASE_URL",
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    default_limit_per_channel: int = Field(default=20, alias="DEFAULT_LIMIT_PER_CHANNEL")
    telegram_channels: str | None = Field(default=None, alias="TELEGRAM_CHANNELS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
