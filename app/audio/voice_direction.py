"""Keep pacing explicit; words in a news story are not production instructions."""

from app.audio.models import DialogueLine


def apply_voice_direction(
    speaker: str,
    text: str,
    *,
    base_pause_after_ms: int,
) -> DialogueLine:
    return DialogueLine(speaker=speaker, text=text, pause_after_ms=base_pause_after_ms)
