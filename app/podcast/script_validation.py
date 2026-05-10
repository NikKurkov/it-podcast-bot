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
    "а по человечески",
    "а по-человечески",
    "почему это важно",
    "что это значит",
    "командам стоит",
    "давайте восстановим цепочку событий",
    "звучит отлично. осталось понять",
    "в продакшене это упирается",
    "люблю новости, после которых",
}
_GENERIC_FILLER_PHRASES = {
    "начнем?",
    "начнём?",
    "начнем с",
    "начнём с",
    "давайте начнем",
    "давайте начнём",
    "давайте перейдем",
    "давайте перейдём",
    "давайте обсудим дальше",
    "переходим к следующей новости",
    "перейдем к следующей новости",
    "перейдём к следующей новости",
    "сегодня мы поговорим",
    "несколько интересных новостей",
    "что же нас ждет",
    "что же нас ждёт",
    "что нас ждет",
    "что нас ждёт",
    "как начинается наш расследование",
    "как начинается наше расследование",
    "давайте разберем",
    "давайте разберём",
    "давайте разберемся по порядку",
    "давайте разберёмся по порядку",
    "это интересно",
    "интересно, как",
    "это как?",
    "это действительно",
    "это действительно интересно",
    "абсолютно верно",
    "шаг в правильном направлении",
    "сегодня мы узнали",
    "сегодня обсудим",
    "в целом, сегодня",
    "будем следить",
    "продолжим следить",
    "следите за новостями",
    "следите за обновлениями",
    "до следующего выпуска",
    "в следующем выпуске",
    "спасибо за внимание",
    "что мы узнали",
    "как это поможет обычному разработчику",
    "может быть, стоит",
    "как это влияет на обычного разработчика",
    "обычного разработчика",
    "командам стоит следить",
    "следить за такими новостями",
    "важно следить",
    "всегда следите",
    "помните, всегда",
    "на этом наш выпуск",
    "спасибо, марк",
    "действительно полезны",
    "революцию в",
    "спасибо за разбор",
    "в прошлом выпуске",
}
_SERVICE_LEAK_PATTERNS = {
    r"auto-selected",
    r"editor note",
    r"final run score",
    r"\bscore\s*=",
    r"\btopics\s*:",
    r"\bpenalties\s*:",
}
_SELF_ADDRESS_NAMES = {
    "mark": {"марк"},
    "nika": {"ника"},
    "gleb": {"глеб"},
    "artem": {"артем", "артём"},
}
_QUALITY_RETRY_CODES = {
    "generic_filler",
    "bad_opening_speaker",
    "markdown_separator",
    "missing_character",
    "non_dialogue_text",
    "self_address",
    "speaker_streak",
    "underused_character",
}
_BLOCKING_QUALITY_CODES = {
    "bad_opening_speaker",
    "generic_filler",
    "markdown_separator",
    "missing_character",
    "non_dialogue_text",
    "service_leak",
    "self_address",
    "underused_character",
}


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
    def has_structural_blocking_issues(self) -> bool:
        return any(
            issue.code
            in {
                "bad_opening_speaker",
                "markdown_separator",
                "meta_phrase",
                "missing_character",
                "non_dialogue_text",
                "service_leak",
                "stock_phrase",
                "unexpected_language",
                "unknown_speaker",
            }
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
        _append_underused_character_issues(speakers, issues)

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
    _append_format_issues(script_text, dialogue_lines, issues)
    _append_self_address_issues(dialogue_lines, issues)
    _append_service_leak_issues(script_text, issues)
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
        issue.line_number
        for issue in validation.issues
        if issue.code in {"markdown_separator", "meta_phrase", "non_dialogue_text"}
        and issue.line_number
    }
    generic_filler_line_numbers = {
        issue.line_number
        for issue in validation.issues
        if issue.code == "generic_filler" and issue.line_number
    }
    if not line_numbers_to_remove and not generic_filler_line_numbers and not validation.issues:
        return script_text

    repaired_lines = []
    team_should_replacement_index = 0
    for line_number, line in enumerate(script_text.splitlines(), start=1):
        if line_number in line_numbers_to_remove:
            continue
        line, team_should_replacement_index = _rewrite_generic_filler_line(
            line,
            team_should_replacement_index,
        )
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


def _append_underused_character_issues(
    speakers: list[str],
    issues: list[ScriptValidationIssue],
    min_lines: int = 2,
    min_total_lines: int = 8,
) -> None:
    if len(speakers) < min_total_lines:
        return

    for character in get_character_keys():
        count = speakers.count(character)
        if count == 0 or count >= min_lines:
            continue
        issues.append(
            ScriptValidationIssue(
                "warning",
                f"Character `{character}` is underused: {count} line, expected at least {min_lines}.",
                code="underused_character",
            ),
        )


def _append_format_issues(
    script_text: str,
    dialogue_lines,
    issues: list[ScriptValidationIssue],
) -> None:
    if dialogue_lines and dialogue_lines[0].speaker != "mark":
        issues.append(
            ScriptValidationIssue(
                "warning",
                "Dialogue should open with `mark` to frame the investigation.",
                code="bad_opening_speaker",
            ),
        )

    for line_number, raw_line in enumerate(script_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        if re.fullmatch(r"-{3,}|_{3,}|\*{3,}", line):
            issues.append(
                ScriptValidationIssue(
                    "warning",
                    "Script contains markdown separator lines.",
                    line_number=line_number,
                    code="markdown_separator",
                ),
            )
            continue
        if not _SPEAKER_LINE_RE.match(line):
            issues.append(
                ScriptValidationIssue(
                    "warning",
                    "Script contains text outside `speaker: text` dialogue format.",
                    line_number=line_number,
                    code="non_dialogue_text",
                ),
            )


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


def _append_service_leak_issues(
    script_text: str,
    issues: list[ScriptValidationIssue],
) -> None:
    normalized_lines = [line.casefold() for line in script_text.splitlines()]
    for pattern in sorted(_SERVICE_LEAK_PATTERNS):
        for line_number, line in enumerate(normalized_lines, start=1):
            if not re.search(pattern, line):
                continue
            issues.append(
                ScriptValidationIssue(
                    "error",
                    f"Script leaks internal service text matching `{pattern}`.",
                    line_number=line_number,
                    code="service_leak",
                ),
            )


def _append_self_address_issues(dialogue_lines, issues: list[ScriptValidationIssue]) -> None:
    for line_number, line in enumerate(dialogue_lines, start=1):
        normalized_text = line.text.casefold().replace("ё", "е")
        own_names = _SELF_ADDRESS_NAMES.get(line.speaker, set())
        for name in own_names:
            if re.search(rf"\b{name}\b\s*,", normalized_text):
                issues.append(
                    ScriptValidationIssue(
                        "warning",
                        f"Speaker `{line.speaker}` addresses themselves by name.",
                        line_number=line_number,
                        code="self_address",
                    ),
                )
                break


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


def _rewrite_generic_filler_line(line: str, team_should_replacement_index: int) -> tuple[str, int]:
    match = _SPEAKER_LINE_RE.match(line.strip())
    if not match:
        return line, team_should_replacement_index

    speaker = match.group("speaker")
    text = match.group("text").strip()
    text = re.sub(
        r"^сегодня\s+мы\s+поговорим\s+о\s+",
        "Разбираем ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"^переходим\s+к\s+следующей\s+новости\s+[—-]\s*",
        "Следующий риск - ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"^давайте\s+(?:перейд[её]м|переходим)\s+к\s+следующей\s+новости\s+о\s+",
        "Следующий риск - ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"^давайте\s+(?:перейд[её]м|переходим)\s+к\s+следующей\s+новости\.?\s*",
        "Следующий риск - ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"^давайте\s+теперь\s+обсудим\s+новость\s+про\s+",
        "Следующий риск - ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"^интересно,\s+как\s+это\s+(?:влияет\s+на|поможет)\s+обычн(?:ого|ому)\s+"
        r"разработчик(?:а|у)\?\s*",
        "Практический вопрос - ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"^на\s+этом\s+наш\s+выпуск\s+подходит\s+к\s+концу\.\s*",
        "Финальный вывод: ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\s*спасибо\s+за\s+внимание,?\s*",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"^совершенно\s+верно\.\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"^абсолютно\s+верно\.\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"^да,\s+но\s+",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"^да,\s+",
        "",
        text,
        flags=re.IGNORECASE,
    )

    team_should_labels = [
        "Практическое действие:",
        "Проверка для команды:",
        "Минимальный шаг:",
        "Инженерный вывод:",
        "Что зафиксировать:",
    ]

    def replace_team_should(match: re.Match) -> str:
        nonlocal team_should_replacement_index
        label = team_should_labels[team_should_replacement_index % len(team_should_labels)]
        team_should_replacement_index += 1
        if match.group(1).isupper():
            return label
        return label[0].lower() + label[1:]

    text = re.sub(
        r"\b(Командам|командам)\s+стоит\b",
        replace_team_should,
        text,
    )
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return "", team_should_replacement_index

    return f"{speaker}: {text}", team_should_replacement_index


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
