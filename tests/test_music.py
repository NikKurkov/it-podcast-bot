from pathlib import Path

import pytest

from app.audio.music import get_audio_duration_seconds, mix_background_music


def test_mix_background_music_rejects_missing_voice_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        mix_background_music(tmp_path / "missing.wav", tmp_path / "out.wav")


def test_get_audio_duration_requires_existing_audio(tmp_path) -> None:
    with pytest.raises(Exception):
        get_audio_duration_seconds(Path(tmp_path / "missing.wav"))
