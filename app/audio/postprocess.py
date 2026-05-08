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
    mic_preset: str = "studio_neutral",
) -> Path:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is not installed or not available in PATH.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    input_sample_rate = _get_audio_sample_rate(input_path)
    filters = _build_voice_filters(
        input_sample_rate=input_sample_rate,
        output_sample_rate=sample_rate,
        tempo=tempo,
        pitch_semitones=pitch_semitones,
        volume_db=volume_db,
        mic_preset=mic_preset,
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


def _build_voice_filters(
    *,
    input_sample_rate: int,
    output_sample_rate: int,
    tempo: float = 1.0,
    pitch_semitones: float = 0.0,
    volume_db: float = 0.0,
    mic_preset: str = "studio_neutral",
) -> list[str]:
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
                f"asetrate={input_sample_rate}*{pitch_factor:.6f}",
                f"aresample={output_sample_rate}",
            ],
        )

    filters.extend(_atempo_filters(tempo_after_pitch))
    filters.extend(_mic_preset_filters(mic_preset))
    if not math.isclose(volume_db, 0.0, abs_tol=0.01):
        filters.append(f"volume={volume_db:.2f}dB")

    filters.extend(
        [
            "loudnorm=I=-18:TP=-2:LRA=11",
            "afade=t=in:st=0:d=0.012",
        ],
    )
    return filters


def _get_audio_sample_rate(audio_path: Path) -> int:
    if not shutil.which("ffprobe"):
        raise RuntimeError("ffprobe is not installed or not available in PATH.")

    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=sample_rate",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        return int(result.stdout.strip())
    except ValueError as exc:
        raise RuntimeError(f"Could not detect audio sample rate for {audio_path}") from exc


def _mic_preset_filters(preset: str) -> list[str]:
    presets = {
        "studio_neutral": [
            "highpass=f=75",
            "lowpass=f=14500",
            "equalizer=f=3200:t=q:w=1.0:g=0.8",
            "acompressor=threshold=-20dB:ratio=1.45:attack=8:release=120:makeup=1.5",
        ],
        "home_dynamic": [
            "highpass=f=95",
            "lowpass=f=12500",
            "equalizer=f=220:t=q:w=0.9:g=-1.0",
            "equalizer=f=2600:t=q:w=1.1:g=1.4",
            "acompressor=threshold=-21dB:ratio=1.65:attack=6:release=100:makeup=1.8",
        ],
        "bright_usb": [
            "highpass=f=105",
            "lowpass=f=13200",
            "equalizer=f=180:t=q:w=0.9:g=-0.8",
            "equalizer=f=4200:t=q:w=1.0:g=1.6",
            "acompressor=threshold=-22dB:ratio=1.55:attack=5:release=95:makeup=2.0",
        ],
        "warm_close": [
            "highpass=f=65",
            "lowpass=f=11800",
            "equalizer=f=180:t=q:w=0.8:g=1.1",
            "equalizer=f=3600:t=q:w=1.2:g=-0.5",
            "acompressor=threshold=-19dB:ratio=1.5:attack=10:release=140:makeup=1.4",
        ],
    }
    if preset not in presets:
        raise ValueError(
            f"Unknown mic preset: {preset}. Supported presets: {', '.join(sorted(presets))}",
        )

    return presets[preset]


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
