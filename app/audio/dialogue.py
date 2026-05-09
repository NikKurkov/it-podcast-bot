import re

from app.audio.models import DialogueLine
from app.audio.voice_direction import apply_voice_direction
from app.audio.voices import get_supported_characters, get_voice_config
from app.podcast.characters import get_character_keys, resolve_character_key

_SPEAKER_RE = re.compile(r"^(?P<speaker>[\wА-Яа-яЁё-]+)\s*[:：]\s*(?P<text>.*)$")
_ROUND_ROBIN_SPEAKERS = get_character_keys()
_MAX_LINE_CHARS = 450
_RU_MONTHS_FOR_TTS = {
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
}
_RU_ORDINAL_DAYS_FOR_TTS = {
    1: "первое",
    2: "второе",
    3: "третье",
    4: "четвёртое",
    5: "пятое",
    6: "шестое",
    7: "седьмое",
    8: "восьмое",
    9: "девятое",
    10: "десятое",
    11: "одиннадцатое",
    12: "двенадцатое",
    13: "тринадцатое",
    14: "четырнадцатое",
    15: "пятнадцатое",
    16: "шестнадцатое",
    17: "семнадцатое",
    18: "восемнадцатое",
    19: "девятнадцатое",
    20: "двадцатое",
    21: "двадцать первое",
    22: "двадцать второе",
    23: "двадцать третье",
    24: "двадцать четвёртое",
    25: "двадцать пятое",
    26: "двадцать шестое",
    27: "двадцать седьмое",
    28: "двадцать восьмое",
    29: "двадцать девятое",
    30: "тридцатое",
    31: "тридцать первое",
}


def script_to_dialogue_lines(script_text: str) -> list[DialogueLine]:
    explicit_lines = _parse_explicit_dialogue(script_text)
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
        if match and _is_supported_speaker(match.group("speaker"), supported):
            _flush_dialogue_line(lines, current_speaker, current_text)
            current_speaker = resolve_character_key(match.group("speaker"))
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
        apply_voice_direction(
            speaker=speaker,
            text=text,
            base_pause_after_ms=voice_config.get("pause_after_ms", 500),
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


def _clean_speech_text(text: str) -> str:
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[@#]\S+", "", text)
    text = re.sub(r"[^\w\sА-Яа-яЁё.,!?;:()«»\"'\\-]", " ", text)
    text = _normalize_russian_dates_for_tts(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _normalize_russian_dates_for_tts(text: str) -> str:
    month_pattern = "|".join(sorted(_RU_MONTHS_FOR_TTS, key=len, reverse=True))

    def replace_date(match: re.Match) -> str:
        day = int(match.group("day"))
        month = match.group("month")
        if day not in _RU_ORDINAL_DAYS_FOR_TTS:
            return match.group(0)
        return f"{_RU_ORDINAL_DAYS_FOR_TTS[day]} {month}"

    return re.sub(
        rf"\b(?P<day>0?[1-9]|[12]\d|3[01])\s+(?P<month>{month_pattern})\b",
        replace_date,
        text,
        flags=re.IGNORECASE,
    )


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
    return chunks


def _split_by_words(text: str, max_chars: int) -> list[str]:
    chunks = []
    current = ""
    for word in text.split():
        if current and len(current) + 1 + len(word) > max_chars:
            chunks.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        chunks.append(current)
    return chunks
