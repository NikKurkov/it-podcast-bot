CHARACTER_VOICES = {
    "boris": {
        "provider": "silero",
        "speaker": "aidar",
        "sample_rate": 48000,
        "pause_after_ms": 700,
    },
    "lena": {
        "provider": "silero",
        "speaker": "xenia",
        "sample_rate": 48000,
        "pause_after_ms": 450,
    },
    "max": {
        "provider": "silero",
        "speaker": "eugene",
        "sample_rate": 48000,
        "pause_after_ms": 550,
    },
    "ilya": {
        "provider": "silero",
        "speaker": "aidar",
        "sample_rate": 48000,
        "pause_after_ms": 800,
    },
}


def get_voice_config(character: str) -> dict:
    key = character.strip().lower()
    if key not in CHARACTER_VOICES:
        supported = ", ".join(get_supported_characters())
        raise ValueError(f"Unknown character: {character}. Supported characters: {supported}")

    return CHARACTER_VOICES[key].copy()


def get_supported_characters() -> list[str]:
    return sorted(CHARACTER_VOICES)
