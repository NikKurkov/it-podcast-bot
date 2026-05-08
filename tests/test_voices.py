import pytest

from app.audio.voices import get_supported_characters, get_voice_config


def test_get_supported_characters_returns_expected_characters() -> None:
    assert get_supported_characters() == ["mark", "gleb", "nika", "artem"]


def test_get_voice_config_returns_mark_voice() -> None:
    config = get_voice_config("mark")

    assert config["provider"] == "silero"
    assert config["speaker"] == "eugene"


def test_get_voice_config_returns_nika_voice() -> None:
    config = get_voice_config("nika")

    assert config["speaker"] == "baya"
    assert config["tempo"] > 1.0


def test_get_voice_config_returns_gleb_voice() -> None:
    config = get_voice_config("gleb")

    assert config["speaker"] == "aidar"
    assert config["tempo"] > 1.0
    assert config["pitch_semitones"] < 0
    assert config["mic_preset"] == "home_dynamic"


def test_get_voice_config_returns_artem_provider() -> None:
    assert get_voice_config("artem")["provider"] == "silero"


def test_get_voice_config_unknown_character_raises_clear_error() -> None:
    with pytest.raises(ValueError, match="Unknown character"):
        get_voice_config("unknown")


def test_get_voice_config_can_switch_to_xtts(monkeypatch) -> None:
    from app.audio import voices

    monkeypatch.setattr(voices.settings, "tts_provider", "xtts")
    monkeypatch.setattr(voices.settings, "xtts_gleb_voice", "data/voices/custom_gleb.wav")

    config = get_voice_config("gleb")

    assert config["provider"] == "xtts"
    assert config["speaker"] == "data/voices/custom_gleb.wav"


def test_get_voice_config_accepts_provider_override(monkeypatch) -> None:
    from app.audio import voices

    monkeypatch.setattr(voices.settings, "tts_provider", "silero")
    monkeypatch.setattr(voices.settings, "xtts_mark_voice", "data/voices/custom_mark.wav")

    config = get_voice_config("mark", provider_name="xtts")

    assert config["provider"] == "xtts"
    assert config["speaker"] == "data/voices/custom_mark.wav"


def test_get_voice_config_xtts_falls_back_to_character_key(monkeypatch) -> None:
    from app.audio import voices

    monkeypatch.setattr(voices.settings, "tts_provider", "silero")
    monkeypatch.setattr(voices.settings, "xtts_nika_voice", None)

    config = get_voice_config("nika", provider_name="xtts")

    assert config["provider"] == "xtts"
    assert config["speaker"] == "nika"
