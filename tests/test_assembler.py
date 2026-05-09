from pathlib import Path

from app.audio.assembler import assemble_podcast
from app.audio.models import RenderedLine


def test_assemble_podcast_adds_final_pause(tmp_path: Path, monkeypatch) -> None:
    audio_path = tmp_path / "line.wav"
    audio_path.write_bytes(b"fake wav")
    created_silences = []
    commands = []

    monkeypatch.setattr("app.audio.assembler.shutil.which", lambda name: "/usr/bin/ffmpeg")

    def fake_create_silence(output_path: Path, duration_ms: int) -> None:
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
