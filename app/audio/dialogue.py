import re

from app.audio.models import DialogueLine
from app.audio.voices import get_supported_characters, get_voice_config

_SPEAKER_RE = re.compile(r"^(?P<speaker>[a-zA-Z_][\w-]*)\s*[:：]\s*(?P<text>.*)$")
_ROUND_ROBIN_SPEAKERS = ["boris", "lena", "max", "ilya"]


def script_to_dialogue_lines(script_text: str) -> list[DialogueLine]:
    explicit_lines = _parse_explicit_dialogue(script_text)
    if explicit_lines:
        return explicit_lines

    paragraphs = _markdown_to_paragraphs(script_text)
    lines = []
    for index, paragraph in enumerate(paragraphs):
        speaker = _ROUND_ROBIN_SPEAKERS[index % len(_ROUND_ROBIN_SPEAKERS)]
        voice_config = get_voice_config(speaker)
        lines.append(
            DialogueLine(
                speaker=speaker,
                text=paragraph,
                pause_after_ms=voice_config.get("pause_after_ms", 500),
            ),
        )
    return lines


def _parse_explicit_dialogue(script_text: str) -> list[DialogueLine]:
    supported = set(get_supported_characters())
    lines: list[DialogueLine] = []
    current_speaker: str | None = None
    current_text: list[str] = []

    for raw_line in script_text.splitlines():
        line = raw_line.strip()
        if not line:
            _flush_dialogue_line(lines, current_speaker, current_text)
            current_speaker = None
            current_text = []
            continue

        match = _SPEAKER_RE.match(line)
        if match and match.group("speaker").lower() in supported:
            _flush_dialogue_line(lines, current_speaker, current_text)
            current_speaker = match.group("speaker").lower()
            current_text = [match.group("text").strip()]
            continue

        if current_speaker:
            current_text.append(line)

    _flush_dialogue_line(lines, current_speaker, current_text)
    return lines


def _flush_dialogue_line(
    lines: list[DialogueLine],
    speaker: str | None,
    text_parts: list[str],
) -> None:
    if not speaker:
        return

    text = _clean_speech_text(" ".join(text_parts))
    if not text:
        return

    voice_config = get_voice_config(speaker)
    lines.append(
        DialogueLine(
            speaker=speaker,
            text=text,
            pause_after_ms=voice_config.get("pause_after_ms", 500),
        ),
    )


def _markdown_to_paragraphs(markdown: str) -> list[str]:
    paragraphs = []
    current_parts = []

    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line or line == "---" or line.startswith("```"):
            _flush_paragraph(paragraphs, current_parts)
            current_parts = []
            continue
        if line.startswith("#"):
            _flush_paragraph(paragraphs, current_parts)
            current_parts = []
            continue
        if re.fullmatch(r"\[.*?]", line):
            continue

        line = re.sub(r"^\s*[-*]\s+", "", line)
        line = re.sub(r"^\d+\.\s+", "", line)
        current_parts.append(line)

    _flush_paragraph(paragraphs, current_parts)
    return paragraphs


def _flush_paragraph(paragraphs: list[str], text_parts: list[str]) -> None:
    text = _clean_speech_text(" ".join(text_parts))
    if text:
        paragraphs.append(text)


def _clean_speech_text(text: str) -> str:
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
