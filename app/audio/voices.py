from app.config.settings import settings
from app.podcast.characters import (
    get_all_character_profiles,
    get_character_keys,
    get_character_profile,
)


CHARACTER_VOICES = {
    profile.key: {
        "provider": profile.default_tts_provider,
        "speaker": profile.default_voice,
        "sample_rate": settings.tts_sample_rate,
        "pause_after_ms": profile.pause_after_ms,
    }
    for profile in get_all_character_profiles()
}


def get_voice_config(character: str) -> dict:
    profile = get_character_profile(character)
    return {
        "provider": profile.default_tts_provider,
        "speaker": profile.default_voice,
        "sample_rate": settings.tts_sample_rate,
        "pause_after_ms": profile.pause_after_ms,
    }


def get_supported_characters() -> list[str]:
    return get_character_keys()
