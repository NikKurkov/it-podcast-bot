import re
from dataclasses import dataclass

from app.audio.dialogue import script_to_dialogue_lines
from app.podcast.characters import get_character_keys, resolve_character_key

_SPEAKER_LINE_RE = re.compile(r"^(?P<speaker>[\wА-Яа-яЁё-]+)\s*[:：]\s*(?P<text>.*)$")
_CJK_RE = re.compile(r"[\u3400-\u9fff]")
_LEGACY_CHARACTERS = {
    "boris": "mark",
    "lena": "nika",
    "max": "artem",
    "ilya": "artem",
}
_BANNED_META_PHRASE_PATTERNS = {
    r"готов[аы]?\s+к\s+полноценному\s+сценарию",
    r"следующ(?:ий|ем)\s+этап(?:е)?",
    r"этот\s+черновик",
    r"черновик\s+можно\s+превратить",
    r"сценарий\s+можно",
}
_FORBIDDEN_STOCK_PHRASES = {
    "давайте восстановим цепочку событий",
    "на первый взгляд это обычный релиз, но дальше начинается самое интересное",
    "вопрос не в том, что произошло. вопрос",
    "это не революция. это старый паттерн",
    "звучит отлично. осталось понять",
    "я такое уже видел. тогда оно называлось иначе",
    "то есть если перевести с инженерного на человеческий",
    "подождите, а мне завтра на работе это поможет",
    "люблю новости, после которых",
    "главный вопрос не в том, можно ли это запустить",
    "технически проблема не в самой модели",
    "в продакшене это упирается",
    "если обещают магию, сначала ищем место",
}
_OVERUSED_PHRASES = {
    "давайте восстановим цепочку событий",
    "звучит отлично. осталось понять",
    "в продакшене это упирается",
    "люблю новости, после которых",
}
_GENERIC_FILLER_PHRASES = {
    "сегодня мы поговорим",
    "что же нас ждет",
    "что же нас ждёт",
    "давайте разберем",
    "давайте разберём",
    "давайте разберемся по порядку",
    "давайте разберёмся по порядку",
    "это интересно",
    "это действительно интересно",
    "сегодня мы узнали",
    "будем следить",
    "следите за новостями",
    "до встречи",
}
_QUALITY_RETRY_CODES = {"generic_filler", "missing_character", "speaker_streak"}
_BLOCKING_QUALITY_CODES = {"generic_filler"}


@dataclass(frozen=True)
class ScriptValidationIssue:
    severity: str
    message: str
    line_number: int | None = None
    code: str = "generic"


@dataclass(frozen=True)
class ScriptValidationResult:
    issues: list[ScriptValidationIssue]
    lines_count: int
    speakers: list[str]

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == "error" for issue in self.issues)

    @property
    def has_blocking_issues(self) -> bool:
        return any(
            issue.severity == "error"
            or issue.code in {"meta_phrase", "repeated_phrase"}
            or issue.code in _BLOCKING_QUALITY_CODES
            for issue in self.issues
        )

    @property
    def has_quality_retry_issues(self) -> bool:
        return any(issue.code in _QUALITY_RETRY_CODES for issue in self.issues)


def validate_dialogue_script(
    script_text: str,
    max_line_chars: int = 450,
    require_all_characters: bool = True,
) -> ScriptValidationResult:
    issues: list[ScriptValidationIssue] = []
    known_characters = set(get_character_keys())
    explicit_speakers = _collect_explicit_speakers(script_text, issues)
    dialogue_lines = script_to_dialogue_lines(script_text)
    speakers = [line.speaker for line in dialogue_lines]

    if not dialogue_lines:
        issues.append(ScriptValidationIssue("error", "Dialogue script has no speakable lines."))

    unknown_speakers = sorted(explicit_speakers - known_characters)
    for speaker in unknown_speakers:
        replacement = _LEGACY_CHARACTERS.get(speaker)
        hint = f" Use `{replacement}` instead." if replacement else ""
        issues.append(ScriptValidationIssue("error", f"Unknown dialogue speaker `{speaker}`.{hint}"))

    if require_all_characters:
        missing = [character for character in get_character_keys() if character not in set(speakers)]
        if missing:
            issues.append(
                ScriptValidationIssue(
                    "warning",
                    f"Dialogue does not use all characters. Missing: {', '.join(missing)}.",
                    code="missing_character",
                ),
            )

    for index, line in enumerate(dialogue_lines, start=1):
        if len(line.text) > max_line_chars:
            issues.append(
                ScriptValidationIssue(
                    "warning",
                    f"Line {index} is long for TTS: {len(line.text)} chars.",
                    code="long_line",
                ),
            )

    for speaker, streak in _speaker_streaks(speakers):
        if streak >= 4:
            issues.append(
                ScriptValidationIssue(
                    "warning",
                    f"Speaker `{speaker}` has {streak} consecutive lines.",
                    code="speaker_streak",
                ),
            )

    _append_banned_meta_phrase_issues(script_text, issues)
    _append_forbidden_stock_phrase_issues(script_text, issues)
    _append_repeated_phrase_issues(script_text, issues)
    _append_generic_filler_phrase_issues(script_text, issues)
    _append_unexpected_language_issues(script_text, issues)

    return ScriptValidationResult(
        issues=issues,
        lines_count=len(dialogue_lines),
        speakers=sorted(set(speakers), key=get_character_keys().index),
    )


def format_validation_report(result: ScriptValidationResult) -> str:
    if not result.issues:
        return "Dialogue script validation: ok"

    lines = ["Dialogue script validation:"]
    for issue in result.issues:
        location = f" line {issue.line_number}:" if issue.line_number else ""
        lines.append(f"  [{issue.severity}]{location} {issue.message}")
    return "\n".join(lines)


def repair_dialogue_script_text(
    script_text: str,
    validation: ScriptValidationResult | None = None,
) -> str:
    validation = validation or validate_dialogue_script(script_text)
    line_numbers_to_remove = {
        issue.line_number for issue in validation.issues if issue.code == "meta_phrase" and issue.line_number
    }
    generic_filler_line_numbers = {
        issue.line_number
        for issue in validation.issues
        if issue.code == "generic_filler" and issue.line_number
    }
    if not line_numbers_to_remove and not generic_filler_line_numbers:
        return script_text

    repaired_lines = []
    for line_number, line in enumerate(script_text.splitlines(), start=1):
        if line_number in line_numbers_to_remove:
            continue
        if line_number in generic_filler_line_numbers:
            line = _remove_generic_filler_sentences(line)
            if not line.strip():
                continue
        repaired_lines.append(line)
    return "\n".join(repaired_lines).strip()


def _collect_explicit_speakers(
    script_text: str,
    issues: list[ScriptValidationIssue],
) -> set[str]:
    speakers: set[str] = set()
    for line_number, raw_line in enumerate(script_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        match = _SPEAKER_LINE_RE.match(line)
        if not match:
            continue

        speaker = match.group("speaker")
        try:
            speakers.add(resolve_character_key(speaker))
        except ValueError:
            normalized = speaker.strip().casefold().replace("ё", "е")
            speakers.add(normalized)
            issues.append(
                ScriptValidationIssue(
                    "error",
                    f"Unknown dialogue speaker `{speaker}`.",
                    line_number=line_number,
                    code="unknown_speaker",
                ),
            )
    return speakers


def _speaker_streaks(speakers: list[str]) -> list[tuple[str, int]]:
    if not speakers:
        return []

    streaks = []
    current = speakers[0]
    count = 1
    for speaker in speakers[1:]:
        if speaker == current:
            count += 1
            continue
        streaks.append((current, count))
        current = speaker
        count = 1
    streaks.append((current, count))
    return streaks


def _append_banned_meta_phrase_issues(
    script_text: str,
    issues: list[ScriptValidationIssue],
) -> None:
    normalized_lines = [line.casefold() for line in script_text.splitlines()]
    for pattern in sorted(_BANNED_META_PHRASE_PATTERNS):
        for line_number, line in enumerate(normalized_lines, start=1):
            if not re.search(pattern, line):
                continue
            issues.append(
                ScriptValidationIssue(
                    "error",
                    f"Script contains meta phrase matching `{pattern}`.",
                    line_number=line_number,
                    code="meta_phrase",
                ),
            )


def _append_forbidden_stock_phrase_issues(
    script_text: str,
    issues: list[ScriptValidationIssue],
) -> None:
    normalized_text = script_text.casefold().replace("ё", "е")
    for phrase in sorted(_FORBIDDEN_STOCK_PHRASES):
        if phrase in normalized_text:
            issues.append(
                ScriptValidationIssue(
                    "error",
                    f"Script copies stock character phrase `{phrase}`.",
                    code="stock_phrase",
                ),
            )


def _append_repeated_phrase_issues(
    script_text: str,
    issues: list[ScriptValidationIssue],
) -> None:
    normalized_text = script_text.casefold()
    for phrase in sorted(_OVERUSED_PHRASES):
        count = normalized_text.count(phrase)
        if count > 1:
            issues.append(
                ScriptValidationIssue(
                    "error",
                    f"Phrase `{phrase}` is repeated {count} times.",
                    code="repeated_phrase",
                ),
            )


def _append_generic_filler_phrase_issues(
    script_text: str,
    issues: list[ScriptValidationIssue],
) -> None:
    normalized_lines = [line.casefold().replace("ё", "е") for line in script_text.splitlines()]
    normalized_phrases = {phrase.replace("ё", "е") for phrase in _GENERIC_FILLER_PHRASES}
    for line_number, line in enumerate(normalized_lines, start=1):
        for phrase in sorted(normalized_phrases):
            if phrase not in line:
                continue
            issues.append(
                ScriptValidationIssue(
                    "warning",
                    f"Script uses generic filler phrase `{phrase}`.",
                    line_number=line_number,
                    code="generic_filler",
                ),
            )


def _remove_generic_filler_sentences(line: str) -> str:
    match = _SPEAKER_LINE_RE.match(line.strip())
    if not match:
        return "" if _contains_generic_filler(line) else line

    speaker = match.group("speaker")
    text = match.group("text").strip()
    sentences = re.split(r"(?<=[.!?])\s+", text)
    kept_sentences = [
        sentence.strip()
        for sentence in sentences
        if sentence.strip() and not _contains_generic_filler(sentence)
    ]
    if not kept_sentences:
        return ""
    return f"{speaker}: {' '.join(kept_sentences)}"


def _contains_generic_filler(text: str) -> bool:
    normalized_text = text.casefold().replace("ё", "е")
    normalized_phrases = {phrase.replace("ё", "е") for phrase in _GENERIC_FILLER_PHRASES}
    return any(phrase in normalized_text for phrase in normalized_phrases)


def _append_unexpected_language_issues(
    script_text: str,
    issues: list[ScriptValidationIssue],
) -> None:
    match = _CJK_RE.search(script_text)
    if not match:
        return

    line_number = None
    for index, line in enumerate(script_text.splitlines(), start=1):
        if _CJK_RE.search(line):
            line_number = index
            break

    issues.append(
        ScriptValidationIssue(
            "error",
            "Script contains non-Russian CJK text or an unintended translation block.",
            line_number=line_number,
            code="unexpected_language",
        ),
    )
