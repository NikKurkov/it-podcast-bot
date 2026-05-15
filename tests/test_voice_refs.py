from pathlib import Path

from app.audio.inspection import AudioFileInfo
from app.audio.voice_refs import (
    _voice_reference_warnings,
    format_voice_reference_report,
    inspect_xtts_voice_reference,
)


def test_voice_reference_warnings_accept_good_audio() -> None:
    audio = AudioFileInfo(
        path="voice.wav",
        exists=True,
        duration_seconds=10.0,
        sample_rate=24000,
        channels=1,
        codec="pcm_s16le",
    )

    assert _voice_reference_warnings(audio) == []


def test_voice_reference_warnings_flag_short_audio() -> None:
    audio = AudioFileInfo(
        path="voice.wav",
        exists=True,
        duration_seconds=2.0,
        sample_rate=16000,
        channels=1,
        codec="pcm_s16le",
    )

    warnings = _voice_reference_warnings(audio)

    assert any("too short" in warning for warning in warnings)
    assert any("low sample rate" in warning for warning in warnings)


def test_inspect_xtts_voice_reference_reports_missing_file(tmp_path: Path) -> None:
    report = inspect_xtts_voice_reference("nika", tmp_path / "missing.wav")

    assert report.ok is False
    assert report.audio.exists is False
    assert "missing voice reference" in report.warnings


def test_format_voice_reference_report_includes_character_and_warning(tmp_path: Path) -> None:
    report = inspect_xtts_voice_reference("gleb", tmp_path / "missing.wav")

    output = format_voice_reference_report([report])

    assert "gleb" in output
    assert "missing voice reference" in output
