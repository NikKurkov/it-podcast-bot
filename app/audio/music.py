import shutil
import subprocess
from pathlib import Path


def generate_chill_background_music(
    output_path: Path,
    duration_seconds: float,
    sample_rate: int = 48000,
) -> Path:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is not installed or not available in PATH.")
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fade_out_start = max(duration_seconds - 3.0, 0.0)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=110:duration={duration_seconds:.3f}:sample_rate={sample_rate}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=164.81:duration={duration_seconds:.3f}:sample_rate={sample_rate}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=220:duration={duration_seconds:.3f}:sample_rate={sample_rate}",
            "-filter_complex",
            (
                "[0:a]volume=0.018[a0];"
                "[1:a]volume=0.012[a1];"
                "[2:a]volume=0.006[a2];"
                "[a0][a1][a2]amix=inputs=3:normalize=0,"
                "lowpass=f=900,"
                "afade=t=in:st=0:d=3,"
                f"afade=t=out:st={fade_out_start:.3f}:d=3[music]"
            ),
            "-map",
            "[music]",
            str(output_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return output_path


def mix_background_music(
    voice_path: Path,
    output_path: Path,
    music_path: Path | None = None,
    music_volume: float = 0.16,
    sample_rate: int = 48000,
) -> Path:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is not installed or not available in PATH.")
    if not voice_path.exists():
        raise FileNotFoundError(f"Voice audio does not exist: {voice_path}")
    if music_volume < 0:
        raise ValueError("music_volume must be non-negative.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with_music_path = music_path or output_path.with_name(f"{output_path.stem}_music_bed.wav")
    if not with_music_path.exists():
        duration = get_audio_duration_seconds(voice_path)
        generate_chill_background_music(
            with_music_path,
            duration_seconds=duration,
            sample_rate=sample_rate,
        )

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(voice_path),
            "-stream_loop",
            "-1",
            "-i",
            str(with_music_path),
            "-filter_complex",
            (
                f"[1:a]volume={music_volume:.4f}[music];"
                "[0:a][music]amix=inputs=2:duration=first:dropout_transition=0,"
                "alimiter=limit=0.95[aout]"
            ),
            "-map",
            "[aout]",
            str(output_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return output_path


def get_audio_duration_seconds(audio_path: Path) -> float:
    if not shutil.which("ffprobe"):
        raise RuntimeError("ffprobe is not installed or not available in PATH.")

    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())
