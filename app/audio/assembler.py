import shutil
import subprocess
import tempfile
from pathlib import Path

from app.audio.models import RenderedLine


def assemble_podcast(
    rendered_lines: list[RenderedLine],
    output_path: Path,
    pauses_ms: list[int] | None = None,
    final_pause_ms: int = 900,
) -> Path:
    if not rendered_lines:
        raise ValueError("No rendered lines to assemble.")
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is not installed or not available in PATH.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    normalized_pauses = pauses_ms or [500] * len(rendered_lines)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        concat_items = []
        for index, rendered_line in enumerate(rendered_lines):
            concat_items.append(rendered_line.audio_path)
            pause_ms = normalized_pauses[index] if index < len(normalized_pauses) else 500
            if pause_ms > 0 and index < len(rendered_lines) - 1:
                silence_path = tmp_path / f"silence_{index:03d}.wav"
                _create_silence(silence_path, pause_ms)
                concat_items.append(silence_path)
        if final_pause_ms > 0:
            final_silence_path = tmp_path / "silence_final.wav"
            _create_silence(final_silence_path, final_pause_ms)
            concat_items.append(final_silence_path)

        concat_file = tmp_path / "concat.txt"
        concat_file.write_text(
            "\n".join(f"file '{_escape_concat_path(path)}'" for path in concat_items) + "\n",
            encoding="utf-8",
        )

        temp_wav = output_path if output_path.suffix.lower() == ".wav" else tmp_path / "podcast.wav"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c",
                "copy",
                str(temp_wav),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        if output_path.suffix.lower() != ".wav":
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(temp_wav), str(output_path)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    return output_path


def _create_silence(output_path: Path, duration_ms: int) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=48000:cl=mono",
            "-t",
            f"{duration_ms / 1000:.3f}",
            str(output_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _escape_concat_path(path: Path) -> str:
    return str(path.resolve()).replace("'", "'\\''")
