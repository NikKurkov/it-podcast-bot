from pathlib import Path

from app.audio.assembler import assemble_podcast
from app.audio.models import RenderedLine


def test_assemble_podcast_adds_final_pause(tmp_path: Path, monkeypatch) -> None:
    audio_path = tmp_path / "line.wav"
    audio_path.write_bytes(b"fake wav")
    created_silences = []
    commands = []

    monkeypatch.setattr("app.audio.assembler.shutil.which", lambda name: "/usr/bin/ffmpeg")

    def fake_create_silence(output_path: Path, duration_ms: int, sample_rate: int = 48000) -> None:
        created_silences.append((output_path.name, duration_ms))
        output_path.write_bytes(b"silence")

    def fake_run(command, check, stdout, stderr):
        commands.append(command)
        Path(command[-1]).write_bytes(b"assembled")

    monkeypatch.setattr("app.audio.assembler._create_silence", fake_create_silence)
    monkeypatch.setattr("app.audio.assembler.subprocess.run", fake_run)

    output_path = assemble_podcast(
        [RenderedLine(speaker="mark", text="Пока.", audio_path=audio_path)],
        tmp_path / "out.wav",
        final_pause_ms=900,
    )

    assert output_path.exists()
    assert ("silence_final.wav", 900) in created_silences
    assert commands


def test_assemble_podcast_adds_transition_stinger(tmp_path: Path, monkeypatch) -> None:
    first_path = tmp_path / "first.wav"
    second_path = tmp_path / "second.wav"
    first_path.write_bytes(b"first")
    second_path.write_bytes(b"second")
    created_silences = []
    created_stingers = []

    monkeypatch.setattr("app.audio.assembler.shutil.which", lambda name: "/usr/bin/ffmpeg")

    def fake_create_silence(output_path: Path, duration_ms: int, sample_rate: int = 48000) -> None:
        created_silences.append((output_path.name, duration_ms))
        output_path.write_bytes(b"silence")

    def fake_create_transition_stinger(output_path: Path, sample_rate: int = 48000) -> None:
        created_stingers.append(output_path.name)
        output_path.write_bytes(b"stinger")

    def fake_run(command, check, stdout, stderr):
        Path(command[-1]).write_bytes(b"assembled")

    monkeypatch.setattr("app.audio.assembler._create_silence", fake_create_silence)
    monkeypatch.setattr(
        "app.audio.assembler._create_transition_stinger", fake_create_transition_stinger
    )
    monkeypatch.setattr("app.audio.assembler.subprocess.run", fake_run)

    assemble_podcast(
        [
            RenderedLine(
                speaker="mark", text="Теперь к новости про GitHub.", audio_path=first_path
            ),
            RenderedLine(speaker="nika", text="GitHub обновил API.", audio_path=second_path),
        ],
        tmp_path / "out.wav",
        pauses_ms=[1350, 500],
        transition_after={0},
    )

    assert created_stingers == ["transition_stinger.wav"]
    assert ("transition_pre_000.wav", 350) in created_silences
    assert ("transition_post_000.wav", 1350) in created_silences


def test_assembler_reuses_identical_silences(tmp_path, monkeypatch):
    import wave
    from array import array
    import subprocess
    import shutil
    import pytest

    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg is required for real assembly")
    source = tmp_path / "voice.wav"
    with wave.open(str(source), "wb") as audio:
        audio.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
        audio.writeframes(array("h", [1000] * 4800).tobytes())
    runs = []
    real_run = subprocess.run

    def run(command, **kwargs):
        runs.append(command)
        return real_run(command, **kwargs)

    monkeypatch.setattr("app.audio.assembler.subprocess.run", run)
    output = assemble_podcast(
        [RenderedLine(speaker="mark", text="Тестовая реплика.", audio_path=source)] * 8,
        tmp_path / "episode.wav",
        pauses_ms=[500] * 8,
        final_pause_ms=500,
    )
    with wave.open(str(output)) as audio:
        assert abs(audio.getnframes() / audio.getframerate() - 4.8) < 0.01
    assert len(runs) == 2  # one reusable silence and one final concatenation
