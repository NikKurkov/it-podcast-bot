from app.config.settings import settings
from app.podcast.characters import (
    get_all_character_profiles,
    get_character_keys,
    get_character_profile,
)

_PROSODY_BY_CHARACTER = {
    "mark": {
        "speaker": "eugene",
        "tempo": 0.99,
        "pitch_semitones": -0.3,
        "volume_db": 0.0,
        "pause_after_ms": 520,
        "mic_preset": "studio_neutral",
    },
    "gleb": {
        "speaker": "aidar",
        "tempo": 1.03,
        "pitch_semitones": -0.7,
        "volume_db": 0.3,
        "pause_after_ms": 520,
        "mic_preset": "home_dynamic",
    },
    "nika": {
        "speaker": "baya",
        "tempo": 1.08,
        "pitch_semitones": 1.2,
        "volume_db": 0.7,
        "pause_after_ms": 380,
        "mic_preset": "bright_usb",
    },
    "artem": {
        "speaker": "aidar",
        "tempo": 0.88,
        "pitch_semitones": -0.9,
        "volume_db": -0.2,
        "pause_after_ms": 760,
        "mic_preset": "warm_close",
    },
}


def _provider_for_character() -> str:
    provider = settings.tts_provider.strip().lower()
    if provider in {"silero", "xtts"}:
        return provider
    return "silero"


def _speaker_for_character(character_key: str, silero_speaker: str) -> str:
    if _provider_for_character() != "xtts":
        return silero_speaker

    explicit_paths = {
        "mark": settings.xtts_mark_voice,
        "gleb": settings.xtts_gleb_voice,
        "nika": settings.xtts_nika_voice,
        "artem": settings.xtts_artem_voice,
    }
    return explicit_paths.get(character_key) or character_key


CHARACTER_VOICES = {
    profile.key: {
        "provider": _provider_for_character(),
        "speaker": _speaker_for_character(
            profile.key,
            _PROSODY_BY_CHARACTER.get(profile.key, {}).get("speaker", profile.default_voice),
        ),
        "sample_rate": settings.tts_sample_rate,
        "pause_after_ms": _PROSODY_BY_CHARACTER.get(profile.key, {}).get(
            "pause_after_ms",
            profile.pause_after_ms,
        ),
        "tempo": _PROSODY_BY_CHARACTER.get(profile.key, {}).get("tempo", 1.0),
        "pitch_semitones": _PROSODY_BY_CHARACTER.get(profile.key, {}).get("pitch_semitones", 0.0),
        "volume_db": _PROSODY_BY_CHARACTER.get(profile.key, {}).get("volume_db", 0.0),
        "mic_preset": _PROSODY_BY_CHARACTER.get(profile.key, {}).get(
            "mic_preset",
            "studio_neutral",
        ),
    }
    for profile in get_all_character_profiles()
}


def get_voice_config(character: str) -> dict:
    profile = get_character_profile(character)
    prosody = _PROSODY_BY_CHARACTER.get(profile.key, {})
    silero_speaker = prosody.get("speaker", profile.default_voice)
    return {
        "provider": _provider_for_character(),
        "speaker": _speaker_for_character(profile.key, silero_speaker),
        "sample_rate": settings.tts_sample_rate,
        "pause_after_ms": prosody.get("pause_after_ms", profile.pause_after_ms),
        "tempo": prosody.get("tempo", 1.0),
        "pitch_semitones": prosody.get("pitch_semitones", 0.0),
        "volume_db": prosody.get("volume_db", 0.0),
        "mic_preset": prosody.get("mic_preset", "studio_neutral"),
    }


def get_supported_characters() -> list[str]:
    return get_character_keys()
