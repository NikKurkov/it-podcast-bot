import pytest

from app.audio.voices import get_supported_characters, get_voice_config


def test_get_supported_characters_returns_expected_characters() -> None:
    assert get_supported_characters() == ["mark", "gleb", "nika", "artem"]


def test_get_voice_config_returns_mark_voice() -> None:
    config = get_voice_config("mark")

    assert config["provider"] == "silero"
    assert config["speaker"] == "eugene"


def test_get_voice_config_returns_nika_voice() -> None:
    assert get_voice_config("nika")["speaker"] == "xenia"


def test_get_voice_config_returns_gleb_voice() -> None:
    assert get_voice_config("gleb")["speaker"] == "aidar"


def test_get_voice_config_returns_artem_provider() -> None:
    assert get_voice_config("artem")["provider"] == "silero"


def test_get_voice_config_unknown_character_raises_clear_error() -> None:
    with pytest.raises(ValueError, match="Unknown character"):
        get_voice_config("unknown")
