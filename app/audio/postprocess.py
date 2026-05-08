import math
import shutil
import subprocess
from pathlib import Path


def process_voice_audio(
    input_path: Path,
    output_path: Path,
    *,
    sample_rate: int,
    tempo: float = 1.0,
    pitch_semitones: float = 0.0,
    volume_db: float = 0.0,
) -> Path:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is not installed or not available in PATH.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pitch_factor = 2 ** (pitch_semitones / 12)
    tempo_after_pitch = tempo / pitch_factor
    filters = [
        "silenceremove=start_periods=1:start_duration=0.04:start_threshold=-45dB",
        "areverse",
        "silenceremove=start_periods=1:start_duration=0.08:start_threshold=-45dB",
        "areverse",
    ]

    if not math.isclose(pitch_factor, 1.0, abs_tol=0.001):
        filters.extend(
            [
                f"asetrate={sample_rate}*{pitch_factor:.6f}",
                f"aresample={sample_rate}",
            ],
        )

    filters.extend(_atempo_filters(tempo_after_pitch))
    if not math.isclose(volume_db, 0.0, abs_tol=0.01):
        filters.append(f"volume={volume_db:.2f}dB")

    filters.extend(
        [
            "loudnorm=I=-18:TP=-2:LRA=11",
            "afade=t=in:st=0:d=0.012",
        ],
    )

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-af",
            ",".join(filters),
            "-ar",
            str(sample_rate),
            "-ac",
            "1",
            str(output_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return output_path


def _atempo_filters(value: float) -> list[str]:
    if value <= 0:
        raise ValueError("tempo must be greater than zero")

    filters = []
    remaining = value
    while remaining > 2.0:
        filters.append("atempo=2.000000")
        remaining /= 2.0
    while remaining < 0.5:
        filters.append("atempo=0.500000")
        remaining /= 0.5
    filters.append(f"atempo={remaining:.6f}")
    return filters
