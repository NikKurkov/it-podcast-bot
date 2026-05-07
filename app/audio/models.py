from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DialogueLine:
    speaker: str
    text: str
    emotion: str | None = None
    pause_after_ms: int = 500


@dataclass(frozen=True)
class RenderedLine:
    speaker: str
    text: str
    audio_path: Path
    duration_ms: int | None = None


@dataclass(frozen=True)
class PodcastRenderResult:
    output_path: Path
    lines: list[RenderedLine]
