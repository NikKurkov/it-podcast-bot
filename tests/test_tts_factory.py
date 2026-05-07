import pytest

from app.audio.providers.piper import PiperTTSProvider
from app.audio.providers.silero import SileroTTSProvider
from app.audio.providers.xtts import XTTSTTSProvider
from app.audio.tts import get_tts_provider


def test_get_tts_provider_silero() -> None:
    assert isinstance(get_tts_provider("silero"), SileroTTSProvider)


def test_get_tts_provider_piper() -> None:
    assert isinstance(get_tts_provider("piper"), PiperTTSProvider)


def test_get_tts_provider_xtts() -> None:
    assert isinstance(get_tts_provider("xtts"), XTTSTTSProvider)


def test_get_tts_provider_unknown_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Unknown TTS provider"):
        get_tts_provider("unknown")
