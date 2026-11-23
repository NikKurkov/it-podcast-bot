"""Keep pacing explicit; words in a news story are not production instructions."""

from app.audio.models import DialogueLine


def apply_voice_direction(
    speaker: str,
    text: str,
    *,
    base_pause_after_ms: int,
) -> DialogueLine:
    pause = min(base_pause_after_ms, 300) if len(text) <= 65 else base_pause_after_ms
    return DialogueLine(speaker=speaker, text=text, pause_after_ms=pause)
