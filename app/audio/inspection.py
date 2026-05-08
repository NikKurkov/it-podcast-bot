import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class AudioFileInfo:
    path: str
    exists: bool
    size_bytes: int | None = None
    duration_seconds: float | None = None
    sample_rate: int | None = None
    channels: int | None = None
    codec: str | None = None


def inspect_audio_file(audio_path: Path) -> AudioFileInfo:
    if not audio_path.exists():
        return AudioFileInfo(path=str(audio_path), exists=False)
    if not shutil.which("ffprobe"):
        raise RuntimeError("ffprobe is not installed or not available in PATH.")

    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-show_streams",
            "-of",
            "json",
            str(audio_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    stream = _first_audio_stream(payload)
    return AudioFileInfo(
        path=str(audio_path),
        exists=True,
        size_bytes=audio_path.stat().st_size,
        duration_seconds=_safe_float(payload.get("format", {}).get("duration")),
        sample_rate=_safe_int(stream.get("sample_rate")),
        channels=_safe_int(stream.get("channels")),
        codec=stream.get("codec_name"),
    )


def write_audio_report(audio_paths: list[Path], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report = [asdict(inspect_audio_file(path)) for path in audio_paths]
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def format_audio_report(audio_paths: list[Path]) -> str:
    lines = []
    for info in [inspect_audio_file(path) for path in audio_paths]:
        if not info.exists:
            lines.append(f"{info.path}: missing")
            continue

        duration = _format_duration(info.duration_seconds)
        size = _format_size(info.size_bytes)
        stream = f"{info.codec or 'unknown'}, {info.sample_rate or '?'} Hz, {info.channels or '?'} ch"
        lines.append(f"{info.path}: {duration}, {size}, {stream}")
    return "\n".join(lines)


def _first_audio_stream(payload: dict) -> dict:
    for stream in payload.get("streams", []):
        if stream.get("codec_type") == "audio":
            return stream
    return {}


def _safe_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _format_duration(value: float | None) -> str:
    if value is None:
        return "unknown duration"
    minutes, seconds = divmod(int(round(value)), 60)
    return f"{minutes:02d}:{seconds:02d}"


def _format_size(value: int | None) -> str:
    if value is None:
        return "unknown size"
    if value < 1024:
        return f"{value} B"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KB"
    return f"{value / (1024 * 1024):.1f} MB"
