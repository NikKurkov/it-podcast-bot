from pathlib import Path

import pytest

from app.audio.music import get_audio_duration_seconds, mix_background_music


def test_mix_background_music_rejects_missing_voice_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        mix_background_music(tmp_path / "missing.wav", tmp_path / "out.wav")


def test_get_audio_duration_requires_existing_audio(tmp_path) -> None:
    with pytest.raises(Exception):
        get_audio_duration_seconds(Path(tmp_path / "missing.wav"))


def test_silent_music_does_not_reduce_voice_volume(tmp_path):
    import shutil
    import wave
    from array import array
    from math import sqrt

    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg is required for real mixing")
    for name, amplitude in (("voice", 1000), ("music", 0)):
        with wave.open(str(tmp_path / f"{name}.wav"), "wb") as audio:
            audio.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
            audio.writeframes(array("h", [amplitude] * 48000).tobytes())
    output = mix_background_music(
        tmp_path / "voice.wav",
        tmp_path / "out.wav",
        tmp_path / "music.wav",
        music_volume=0,
    )
    with wave.open(str(output)) as audio:
        samples = array("h", audio.readframes(audio.getnframes()))
    rms = sqrt(sum(sample * sample for sample in samples) / len(samples))
    assert 950 <= rms <= 1050


def test_missing_selected_music_is_not_silently_replaced(tmp_path):
    voice = tmp_path / "voice.wav"
    voice.write_bytes(b"existing voice")
    selected = tmp_path / "selected.wav"
    with pytest.raises(FileNotFoundError, match="Music"):
        mix_background_music(voice, tmp_path / "out.wav", selected)
    assert not selected.exists()
