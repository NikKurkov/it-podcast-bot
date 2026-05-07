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
    telegram_channels_file: str = Field(default="config/channels.txt", alias="TELEGRAM_CHANNELS_FILE")
    telegram_proxy_url: str | None = Field(default=None, alias="TELEGRAM_PROXY_URL")
    exclude_keywords_file: str = Field(default="config/exclude_keywords.txt", alias="EXCLUDE_KEYWORDS_FILE")
    llm_base_url: str = Field(default="http://localhost:11434/v1", alias="LLM_BASE_URL")
    llm_api_key: str = Field(default="ollama", alias="LLM_API_KEY")
    llm_model: str = Field(default="qwen2.5:7b-instruct", alias="LLM_MODEL")
    llm_fast_model: str = Field(default="qwen2.5:3b-instruct", alias="LLM_FAST_MODEL")
    llm_final_model: str = Field(default="qwen2.5:7b-instruct", alias="LLM_FINAL_MODEL")
    tts_voice: str = Field(default="ru", alias="TTS_VOICE")
    tts_speed: int = Field(default=160, alias="TTS_SPEED")
    tts_provider: str = Field(default="silero", alias="TTS_PROVIDER")
    tts_output_dir: str = Field(default="data/audio", alias="TTS_OUTPUT_DIR")
    tts_sample_rate: int = Field(default=48000, alias="TTS_SAMPLE_RATE")
    tts_device: str = Field(default="cpu", alias="TTS_DEVICE")
    audio_background_music: bool = Field(default=False, alias="AUDIO_BACKGROUND_MUSIC")
    audio_background_music_volume: float = Field(default=0.16, alias="AUDIO_BACKGROUND_MUSIC_VOLUME")
    audio_background_music_path: str | None = Field(default=None, alias="AUDIO_BACKGROUND_MUSIC_PATH")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
