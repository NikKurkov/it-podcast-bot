import re
import unicodedata
from dataclasses import replace

from app.audio.models import DialogueLine
from app.audio.spoken_numbers import normalize_spoken_dates
from app.audio.voice_direction import apply_voice_direction
from app.audio.voices import get_supported_characters, get_voice_config
from app.podcast.characters import get_character_keys, resolve_character_key

_SPEAKER_RE = re.compile(r"^(?P<speaker>[\wА-Яа-яЁё-]+)\s*[:：]\s*(?P<text>.*)$")
_ROUND_ROBIN_SPEAKERS = get_character_keys()
_MAX_LINE_CHARS = 450
_MAX_TTS_LINE_CHARS = 170
_MIN_TTS_CHUNK_CHARS = 45


def script_to_dialogue_lines(
    script_text: str, *, split_for_tts: bool = True
) -> list[DialogueLine]:
    explicit_lines = _parse_explicit_dialogue(script_text, split_for_tts=split_for_tts)
    if explicit_lines:
        return explicit_lines

    paragraphs = _markdown_to_paragraphs(script_text)
    lines = []
    speaker_index = 0
    for paragraph in paragraphs:
        for chunk in _split_long_text(paragraph, max_chars=_MAX_LINE_CHARS):
            speaker = _ROUND_ROBIN_SPEAKERS[speaker_index % len(_ROUND_ROBIN_SPEAKERS)]
            speaker_index += 1
            voice_config = get_voice_config(speaker)
            lines.append(
                apply_voice_direction(
                    speaker,
                    chunk,
                    base_pause_after_ms=voice_config.get("pause_after_ms", 500),
                ),
            )
    return lines


def _parse_explicit_dialogue(script_text: str, *, split_for_tts: bool) -> list[DialogueLine]:
    supported = set(get_supported_characters())
    lines: list[DialogueLine] = []
    current_speaker: str | None = None
    current_text: list[str] = []

    for raw_line in script_text.splitlines():
        line = raw_line.strip()
        if not line:
            _flush_dialogue_line(lines, current_speaker, current_text, split_for_tts=split_for_tts)
            current_speaker = None
            current_text = []
            continue

        match = _SPEAKER_RE.match(line)
        if match and _is_supported_speaker(match.group("speaker"), supported):
            _flush_dialogue_line(lines, current_speaker, current_text, split_for_tts=split_for_tts)
            current_speaker = resolve_character_key(match.group("speaker"))
            current_text = [match.group("text").strip()]
            continue

        if current_speaker:
            current_text.append(line)

    _flush_dialogue_line(lines, current_speaker, current_text, split_for_tts=split_for_tts)
    return lines


def _flush_dialogue_line(
    lines: list[DialogueLine],
    speaker: str | None,
    text_parts: list[str],
    *,
    split_for_tts: bool,
) -> None:
    if not speaker:
        return

    text = _clean_speech_text(" ".join(text_parts), normalize_dates=split_for_tts)
    if not text:
        return

    voice_config = get_voice_config(speaker)
    line = apply_voice_direction(
        speaker=speaker, text=text, base_pause_after_ms=voice_config.get("pause_after_ms", 500)
    )
    lines.extend(split_speech_line(line) if split_for_tts else [line])


def split_speech_line(line: DialogueLine) -> list[DialogueLine]:
    chunks = _split_long_text(line.text, max_chars=_MAX_TTS_LINE_CHARS)
    result = []
    for index, chunk in enumerate(chunks):
        pause_after_ms = line.pause_after_ms
        if index < len(chunks) - 1:
            # A provider-size boundary is not a new speaker turn.
            pause_after_ms = min(
                pause_after_ms, 160 if chunk.endswith((".", "?", "!", "…")) else 60
            )
        result.append(replace(line, text=chunk, pause_after_ms=pause_after_ms))
    return result


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
        if _is_service_line(line):
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


def _clean_speech_text(text: str, *, normalize_dates: bool = True) -> str:
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"(?<![\w+#])[@#]\w+", "", text)
    text = "".join(char for char in text if unicodedata.category(char) not in {"Cc", "Cf", "So"})
    if normalize_dates:
        text = normalize_spoken_dates(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _is_service_line(line: str) -> bool:
    lowered = line.lower()
    return lowered.startswith(("generated at:", "editor note:", "source:"))


def _is_supported_speaker(value: str, supported: set[str]) -> bool:
    try:
        return resolve_character_key(value) in supported
    except ValueError:
        return False


def _split_long_text(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    chunks = []
    current = ""
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if not sentence:
            continue
        if len(sentence) > max_chars:
            if current:
                chunks.append(current)
            chunks.extend(_split_by_words(sentence, max_chars))
            current = ""
            continue
        if current and len(current) + 1 + len(sentence) > max_chars:
            chunks.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()

    if current:
        chunks.append(current)
    return _merge_short_tail_chunks(chunks, max_chars=max_chars)


def _split_by_words(text: str, max_chars: int) -> list[str]:
    chunks = []
    remaining = text.split()
    while remaining:
        size = 0
        end = 0
        clause_end = 0
        for index, word in enumerate(remaining, start=1):
            size += len(word) + (1 if end else 0)
            if end and size > max_chars:
                break
            end = index
            if size >= _MIN_TTS_CHUNK_CHARS and word.endswith((",", ";", ":", "—")):
                clause_end = index
        if end < len(remaining) and clause_end:
            if len(" ".join(remaining[clause_end:])) >= _MIN_TTS_CHUNK_CHARS:
                end = clause_end
        chunks.append(" ".join(remaining[:end]))
        remaining = remaining[end:]
    return _merge_short_tail_chunks(chunks, max_chars=max_chars)


def _merge_short_tail_chunks(chunks: list[str], max_chars: int) -> list[str]:
    if len(chunks) < 2:
        return chunks
    tail = chunks[-1].strip()
    previous = chunks[-2].strip()
    if len(tail) >= _MIN_TTS_CHUNK_CHARS or previous.endswith((",", ";", ":", "—")):
        return chunks
    joined = f"{previous} {tail}".strip()
    if len(joined) <= max_chars:
        return [*chunks[:-2], joined]
    # Rebalance complete words instead of exceeding the provider-size boundary.
    words = previous.split()
    while len(tail) < _MIN_TTS_CHUNK_CHARS and len(words) > 1:
        candidate = words[-1] + " " + tail
        if len(candidate) > max_chars:
            break
        tail = candidate
        words.pop()
    return [*chunks[:-2], " ".join(words), tail]
