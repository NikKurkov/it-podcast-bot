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
    transition_stinger: bool = True,
    transition_after: set[int] | None = None,
    sample_rate: int = 48000,
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
        silence_paths: dict[int, Path] = {}

        def add_silence(duration_ms: int, name: str) -> None:
            if duration_ms not in silence_paths:
                path = tmp_path / name
                _create_silence(path, duration_ms, sample_rate=sample_rate)
                silence_paths[duration_ms] = path
            concat_items.append(silence_paths[duration_ms])

        stinger_path = tmp_path / "transition_stinger.wav"
        for index, rendered_line in enumerate(rendered_lines):
            concat_items.append(rendered_line.audio_path)
            pause_ms = normalized_pauses[index] if index < len(normalized_pauses) else 500
            if (
                transition_stinger
                and index in (transition_after or set())
                and index < len(rendered_lines) - 1
            ):
                add_silence(350, f"transition_pre_{index:03d}.wav")
                if not stinger_path.exists():
                    _create_transition_stinger(stinger_path, sample_rate=sample_rate)
                concat_items.append(stinger_path)
                add_silence(max(700, pause_ms), f"transition_post_{index:03d}.wav")
                continue
            if pause_ms > 0 and index < len(rendered_lines) - 1:
                add_silence(pause_ms, f"silence_{index:03d}.wav")
        if final_pause_ms > 0:
            add_silence(final_pause_ms, "silence_final.wav")

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


def _create_silence(output_path: Path, duration_ms: int, sample_rate: int = 48000) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=r={sample_rate}:cl=mono",
            "-t",
            f"{duration_ms / 1000:.3f}",
            str(output_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _create_transition_stinger(
    output_path: Path,
    duration_ms: int = 420,
    sample_rate: int = 48000,
) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            (
                f"sine=frequency=740:duration=0.18:sample_rate={sample_rate},"
                "afade=t=in:st=0:d=0.03,afade=t=out:st=0.14:d=0.04,"
                "volume=0.04"
            ),
            "-f",
            "lavfi",
            "-i",
            (
                f"sine=frequency=980:duration=0.18:sample_rate={sample_rate},"
                "afade=t=in:st=0:d=0.03,afade=t=out:st=0.14:d=0.04,"
                "volume=0.025,adelay=120|120"
            ),
            "-filter_complex",
            f"[0:a][1:a]amix=inputs=2:duration=longest,apad=pad_dur={duration_ms / 1000:.3f}",
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
