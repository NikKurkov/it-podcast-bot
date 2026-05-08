from app.config.settings import settings
from app.podcast.characters import (
    get_all_character_profiles,
    get_character_keys,
    get_character_profile,
)

_PROSODY_BY_CHARACTER = {
    "mark": {
        "speaker": "eugene",
        "tempo": 0.97,
        "pitch_semitones": -0.6,
        "volume_db": 0.0,
        "pause_after_ms": 560,
    },
    "gleb": {
        "speaker": "aidar",
        "tempo": 0.91,
        "pitch_semitones": -2.1,
        "volume_db": -0.4,
        "pause_after_ms": 720,
    },
    "nika": {
        "speaker": "baya",
        "tempo": 1.08,
        "pitch_semitones": 1.2,
        "volume_db": 0.7,
        "pause_after_ms": 380,
    },
    "artem": {
        "speaker": "aidar",
        "tempo": 0.88,
        "pitch_semitones": -0.9,
        "volume_db": -0.2,
        "pause_after_ms": 760,
    },
}


CHARACTER_VOICES = {
    profile.key: {
        "provider": profile.default_tts_provider,
        "speaker": _PROSODY_BY_CHARACTER.get(profile.key, {}).get("speaker", profile.default_voice),
        "sample_rate": settings.tts_sample_rate,
        "pause_after_ms": _PROSODY_BY_CHARACTER.get(profile.key, {}).get(
            "pause_after_ms",
            profile.pause_after_ms,
        ),
        "tempo": _PROSODY_BY_CHARACTER.get(profile.key, {}).get("tempo", 1.0),
        "pitch_semitones": _PROSODY_BY_CHARACTER.get(profile.key, {}).get("pitch_semitones", 0.0),
        "volume_db": _PROSODY_BY_CHARACTER.get(profile.key, {}).get("volume_db", 0.0),
    }
    for profile in get_all_character_profiles()
}


def get_voice_config(character: str) -> dict:
    profile = get_character_profile(character)
    prosody = _PROSODY_BY_CHARACTER.get(profile.key, {})
    return {
        "provider": profile.default_tts_provider,
        "speaker": prosody.get("speaker", profile.default_voice),
        "sample_rate": settings.tts_sample_rate,
        "pause_after_ms": prosody.get("pause_after_ms", profile.pause_after_ms),
        "tempo": prosody.get("tempo", 1.0),
        "pitch_semitones": prosody.get("pitch_semitones", 0.0),
        "volume_db": prosody.get("volume_db", 0.0),
    }


def get_supported_characters() -> list[str]:
    return get_character_keys()
