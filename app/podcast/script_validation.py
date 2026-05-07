import re
from dataclasses import dataclass

from app.audio.dialogue import script_to_dialogue_lines
from app.podcast.characters import get_character_keys, resolve_character_key

_SPEAKER_LINE_RE = re.compile(r"^(?P<speaker>[\wА-Яа-яЁё-]+)\s*[:：]\s*(?P<text>.*)$")
_LEGACY_CHARACTERS = {
    "boris": "mark",
    "lena": "nika",
    "max": "artem",
    "ilya": "artem",
}


@dataclass(frozen=True)
class ScriptValidationIssue:
    severity: str
    message: str
    line_number: int | None = None


@dataclass(frozen=True)
class ScriptValidationResult:
    issues: list[ScriptValidationIssue]
    lines_count: int
    speakers: list[str]

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == "error" for issue in self.issues)


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
                ),
            )

    for index, line in enumerate(dialogue_lines, start=1):
        if len(line.text) > max_line_chars:
            issues.append(
                ScriptValidationIssue(
                    "warning",
                    f"Line {index} is long for TTS: {len(line.text)} chars.",
                ),
            )

    for speaker, streak in _speaker_streaks(speakers):
        if streak >= 4:
            issues.append(
                ScriptValidationIssue(
                    "warning",
                    f"Speaker `{speaker}` has {streak} consecutive lines.",
                ),
            )

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
