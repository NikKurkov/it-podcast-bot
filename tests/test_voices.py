import pytest

from app.audio.voices import get_supported_characters, get_voice_config


def test_get_supported_characters_returns_expected_characters() -> None:
    assert get_supported_characters() == ["boris", "ilya", "lena", "max"]


def test_get_voice_config_returns_provider_and_speaker() -> None:
    config = get_voice_config("boris")

    assert config["provider"] == "silero"
    assert config["speaker"]


def test_get_voice_config_unknown_character_raises_clear_error() -> None:
    with pytest.raises(ValueError, match="Unknown character"):
        get_voice_config("unknown")
