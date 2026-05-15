from dataclasses import dataclass
from pathlib import Path

from app.audio.inspection import AudioFileInfo, inspect_audio_file
from app.config.settings import settings

MIN_REFERENCE_DURATION_SECONDS = 6.0
MAX_REFERENCE_DURATION_SECONDS = 20.0
RECOMMENDED_SAMPLE_RATE = 24000


@dataclass(frozen=True)
class VoiceReferenceReport:
    character: str
    path: Path
    audio: AudioFileInfo
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return self.audio.exists and not self.warnings


def inspect_xtts_voice_references() -> list[VoiceReferenceReport]:
    return [
        inspect_xtts_voice_reference(character, _voice_reference_path(character))
        for character in ("mark", "gleb", "nika", "artem")
    ]


def inspect_xtts_voice_reference(character: str, path: Path) -> VoiceReferenceReport:
    audio = inspect_audio_file(path)
    return VoiceReferenceReport(
        character=character,
        path=path,
        audio=audio,
        warnings=_voice_reference_warnings(audio),
    )


def format_voice_reference_report(reports: list[VoiceReferenceReport]) -> str:
    lines = ["XTTS voice references:"]
    for report in reports:
        status = "OK" if report.ok else "WARN" if report.audio.exists else "ERROR"
        detail = _format_audio_detail(report.audio)
        lines.append(f"  [{status}] {report.character}: {report.path} - {detail}")
        for warning in report.warnings:
            lines.append(f"       - {warning}")
    return "\n".join(lines)


def _voice_reference_path(character: str) -> Path:
    configured = getattr(settings, f"xtts_{character}_voice")
    if configured:
        return Path(configured)
    return Path(settings.xtts_voice_refs_dir) / f"{character}.wav"


def _voice_reference_warnings(audio: AudioFileInfo) -> list[str]:
    if not audio.exists:
        return ["missing voice reference"]

    warnings = []
    duration = audio.duration_seconds
    if duration is None:
        warnings.append("duration is unknown")
    elif duration < MIN_REFERENCE_DURATION_SECONDS:
        warnings.append(
            f"too short: {duration:.1f}s, recommended {MIN_REFERENCE_DURATION_SECONDS:.0f}-"
            f"{MAX_REFERENCE_DURATION_SECONDS:.0f}s",
        )
    elif duration > MAX_REFERENCE_DURATION_SECONDS:
        warnings.append(
            f"too long: {duration:.1f}s, recommended {MIN_REFERENCE_DURATION_SECONDS:.0f}-"
            f"{MAX_REFERENCE_DURATION_SECONDS:.0f}s",
        )

    if audio.channels and audio.channels > 2:
        warnings.append(f"unexpected channel count: {audio.channels}")
    if audio.sample_rate and audio.sample_rate < RECOMMENDED_SAMPLE_RATE:
        warnings.append(
            f"low sample rate: {audio.sample_rate} Hz, recommended at least {RECOMMENDED_SAMPLE_RATE} Hz",
        )
    return warnings


def _format_audio_detail(audio: AudioFileInfo) -> str:
    if not audio.exists:
        return "missing"
    duration = f"{audio.duration_seconds:.1f}s" if audio.duration_seconds is not None else "unknown duration"
    sample_rate = f"{audio.sample_rate} Hz" if audio.sample_rate else "unknown Hz"
    channels = f"{audio.channels} ch" if audio.channels else "unknown ch"
    codec = audio.codec or "unknown codec"
    return f"{duration}, {sample_rate}, {channels}, {codec}"
