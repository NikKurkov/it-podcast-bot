from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, FilePath, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    telegram_api_id: int = Field(default=0, alias="TELEGRAM_API_ID", repr=False)
    telegram_api_hash: str = Field(default="", alias="TELEGRAM_API_HASH", repr=False)
    telegram_session_name: str = Field(default="it_podcast_bot", alias="TELEGRAM_SESSION_NAME")
    database_url: str = Field(
        default="sqlite:///data/it_podcast_bot.sqlite3",
        alias="DATABASE_URL",
        repr=False,
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    default_limit_per_channel: int = Field(default=20, alias="DEFAULT_LIMIT_PER_CHANNEL")
    telegram_channels: str | None = Field(default=None, alias="TELEGRAM_CHANNELS")
    telegram_channels_file: str = Field(
        default="config/channels.txt", alias="TELEGRAM_CHANNELS_FILE"
    )
    telegram_proxy_url: str | None = Field(default=None, alias="TELEGRAM_PROXY_URL", repr=False)
    telegram_publish_channel_id: str | None = Field(
        default=None, alias="TELEGRAM_PUBLISH_CHANNEL_ID", repr=False
    )
    publish_telegram_on_final: bool = Field(default=False, alias="PUBLISH_TELEGRAM_ON_FINAL")
    podcast_title: str = Field(default="НикКаст", alias="PODCAST_TITLE")
    podcast_target_minutes: float = Field(default=12.0, gt=0, alias="PODCAST_TARGET_MINUTES")
    podcast_participants: str | None = Field(default=None, alias="PODCAST_PARTICIPANTS")
    podcast_script_words_per_minute: float = Field(
        default=125, gt=0, alias="PODCAST_SCRIPT_WORDS_PER_MINUTE"
    )
    podcast_editorial_brief: str = Field(
        default="Аудитория — люди, создающие, исследующие и эксплуатирующие цифровые системы. Выбирай новые проверяемые события, помогающие понять устройство, возможности, ограничения и последствия технологий. Бытовые советы, личные истории и реклама без нового технологического события не подходят.",
        alias="PODCAST_EDITORIAL_BRIEF",
    )
    research_enabled: bool = Field(default=True, alias="RESEARCH_ENABLED")
    podcast_cover_image: str | None = Field(
        default="assets/nikcast_cover_256.jpg",
        alias="PODCAST_COVER_IMAGE",
    )
    exclude_keywords_file: str = Field(
        default="config/exclude_keywords.txt", alias="EXCLUDE_KEYWORDS_FILE"
    )
    source_weights_file: str = Field(
        default="config/source_weights.txt", alias="SOURCE_WEIGHTS_FILE"
    )
    final_collect_limit: int = Field(default=0, ge=0, alias="FINAL_COLLECT_LIMIT")
    final_pool_limit: int = Field(default=250, alias="FINAL_POOL_LIMIT")
    final_top_posts: int = Field(default=5, alias="FINAL_TOP_POSTS")
    llm_base_url: str = Field(default="http://localhost:11434/v1", alias="LLM_BASE_URL", repr=False)
    llm_api_key: str = Field(default="ollama", alias="LLM_API_KEY", repr=False)
    llm_model: str = Field(default="qwen2.5:7b-instruct", alias="LLM_MODEL")
    llm_fast_model: str = Field(default="qwen2.5:3b-instruct", alias="LLM_FAST_MODEL")
    llm_final_model: str = Field(default="qwen2.5:7b-instruct", alias="LLM_FINAL_MODEL")
    llm_editorial_review_model: str | None = Field(default=None, alias="LLM_EDITORIAL_REVIEW_MODEL")
    llm_editorial_batch_size: int = Field(default=8, ge=1, alias="LLM_EDITORIAL_BATCH_SIZE")
    llm_factcheck_batch_size: int = Field(default=4, ge=1, alias="LLM_FACTCHECK_BATCH_SIZE")
    llm_scene_critic_enabled: bool = Field(default=False, alias="LLM_SCENE_CRITIC_ENABLED")
    llm_source_review_reasoning_effort: str | None = Field(
        default=None, alias="LLM_SOURCE_REVIEW_REASONING_EFFORT"
    )
    llm_factcheck_attempts: int = Field(default=2, ge=1, alias="LLM_FACTCHECK_ATTEMPTS")
    llm_episode_plan_enabled: bool = Field(default=False, alias="LLM_EPISODE_PLAN_ENABLED")
    llm_script_editor_enabled: bool = Field(default=True, alias="LLM_SCRIPT_EDITOR_ENABLED")
    llm_chunked_script_enabled: bool = Field(default=True, alias="LLM_CHUNKED_SCRIPT_ENABLED")
    llm_chunked_model: str = Field(default="qwen2.5:7b-instruct", alias="LLM_CHUNKED_MODEL")
    llm_script_chunk_size: int = Field(default=1, ge=1, alias="LLM_SCRIPT_CHUNK_SIZE")
    llm_script_temperature: float = Field(default=0.25, ge=0, le=2, alias="LLM_SCRIPT_TEMPERATURE")
    llm_reasoning_effort: str | None = Field(default=None, alias="LLM_REASONING_EFFORT")
    podcast_style_guide_file: str = Field(
        default="config/podcast_style.md", alias="PODCAST_STYLE_GUIDE_FILE"
    )
    llm_request_timeout_seconds: float = Field(
        default=360.0, gt=0, alias="LLM_REQUEST_TIMEOUT_SECONDS"
    )
    llm_release_before_tts: bool = Field(default=True, alias="LLM_RELEASE_BEFORE_TTS")
    local_llm_engine: Literal["ollama", "llamacpp"] = Field(
        default="ollama", alias="LOCAL_LLM_ENGINE"
    )
    llama_cpp_executable: str | None = Field(default=None, alias="LLAMA_CPP_EXECUTABLE")
    llama_cpp_model_path: str | None = Field(default=None, alias="LLAMA_CPP_MODEL_PATH")
    llama_cpp_chat_template_file: FilePath | None = Field(
        default=None, alias="LLAMA_CPP_CHAT_TEMPLATE_FILE"
    )
    llama_cpp_gpu_layers: int | None = Field(default=None, ge=0, alias="LLAMA_CPP_GPU_LAYERS")
    llama_cpp_threads: int | None = Field(default=None, ge=1, alias="LLAMA_CPP_THREADS")
    llama_cpp_backend_library: str | None = Field(default=None, alias="LLAMA_CPP_BACKEND_LIBRARY")
    llama_cpp_device: str = Field(default="auto", alias="LLAMA_CPP_DEVICE")
    llama_cpp_reasoning_budget: int = Field(default=1024, ge=0, alias="LLAMA_CPP_REASONING_BUDGET")
    llama_cpp_idle_sleep_seconds: int = Field(
        default=10, ge=1, le=60, alias="LLAMA_CPP_IDLE_SLEEP_SECONDS"
    )
    ollama_executable: str | None = Field(default=None, alias="OLLAMA_EXECUTABLE")
    ollama_memory_max_mb: int = Field(default=4096, ge=128, alias="OLLAMA_MEMORY_MAX_MB")
    ollama_swap_max_mb: int = Field(default=256, ge=0, alias="OLLAMA_SWAP_MAX_MB")
    ollama_prompt_cache_mb: int = Field(default=0, ge=0, alias="OLLAMA_PROMPT_CACHE_MB")
    ollama_context_checkpoints: int = Field(default=0, ge=0, alias="OLLAMA_CONTEXT_CHECKPOINTS")
    ollama_checkpoint_min_step: int = Field(default=8192, ge=0, alias="OLLAMA_CHECKPOINT_MIN_STEP")
    ollama_context_length: int = Field(default=8192, alias="OLLAMA_CONTEXT_LENGTH")
    tts_voice: str = Field(default="ru", alias="TTS_VOICE")
    tts_speed: int = Field(default=160, alias="TTS_SPEED")
    tts_provider: str = Field(default="silero", alias="TTS_PROVIDER")
    tts_cpu_threads: int = Field(default=4, ge=1, alias="TTS_CPU_THREADS")
    tts_auto_pronunciation: bool = Field(default=False, alias="TTS_AUTO_PRONUNCIATION")
    silero_model_id: str = Field(default="v5_6_ru", alias="SILERO_MODEL_ID")
    silero_model_path: str | None = Field(default=None, alias="SILERO_MODEL_PATH")
    tts_output_dir: str = Field(default="data/audio", alias="TTS_OUTPUT_DIR")
    tts_sample_rate: int = Field(default=48000, alias="TTS_SAMPLE_RATE")
    tts_device: str = Field(default="cpu", alias="TTS_DEVICE")
    xtts_model_name: str = Field(
        default="tts_models/multilingual/multi-dataset/xtts_v2",
        alias="XTTS_MODEL_NAME",
    )
    xtts_language: str = Field(default="ru", alias="XTTS_LANGUAGE")
    xtts_voice_refs_dir: str = Field(default="data/voices/xtts", alias="XTTS_VOICE_REFS_DIR")
    xtts_mark_voice: str | None = Field(default=None, alias="XTTS_MARK_VOICE")
    xtts_gleb_voice: str | None = Field(default=None, alias="XTTS_GLEB_VOICE")
    xtts_nika_voice: str | None = Field(default=None, alias="XTTS_NIKA_VOICE")
    xtts_artem_voice: str | None = Field(default=None, alias="XTTS_ARTEM_VOICE")
    audio_background_music: bool = Field(default=False, alias="AUDIO_BACKGROUND_MUSIC")
    audio_background_music_volume: float = Field(
        default=0.08, ge=0, alias="AUDIO_BACKGROUND_MUSIC_VOLUME"
    )
    audio_background_music_path: str | None = Field(
        default=None, alias="AUDIO_BACKGROUND_MUSIC_PATH"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("llama_cpp_chat_template_file", mode="before")
    @classmethod
    def expand_chat_template_path(cls, value):
        return Path(value).expanduser() if isinstance(value, (str, Path)) else value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
