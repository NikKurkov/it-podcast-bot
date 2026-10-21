"""Structural dialogue validation without content blacklists or host quotas."""

import re
from collections import Counter
from dataclasses import dataclass

from app.audio.dialogue import script_to_dialogue_lines
from app.podcast.characters import get_character_keys, resolve_character_key

_FORMATTED_SPEAKER_RE = re.compile(
    r"^(?P<markup>\*\*|__|\*|_|`)(?P<speaker>[\w-]+)"
    r"(?:(?P=markup)\s*(?P<outer>[:：])|(?P<inner>[:：])(?P=markup))(?P<text>.*)$"
)
_SPEAKER_LINE_RE = re.compile(r"^(?P<speaker>[\w-]+)\s*[:：]\s*(?P<text>.*)$")


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
        return self.has_errors

    @property
    def has_structural_blocking_issues(self) -> bool:
        return self.has_errors

    @property
    def has_quality_retry_issues(self) -> bool:
        return any(issue.code == "repeated_turn" for issue in self.issues)


def validate_dialogue_script(
    script_text: str,
    max_line_chars: int = 450,
    require_all_characters: bool = False,
    allowed_speakers: set[str] | None = None,
) -> ScriptValidationResult:
    issues = []
    speakers = set()
    texts = []
    for number, raw in enumerate(script_text.splitlines(), start=1):
        if not raw.strip():
            continue
        match = _SPEAKER_LINE_RE.fullmatch(raw.strip())
        if not match:
            issues.append(
                ScriptValidationIssue(
                    "error",
                    "Expected speaker: text dialogue format.",
                    number,
                    "non_dialogue_text",
                )
            )
            continue
        try:
            speaker = resolve_character_key(match["speaker"])
        except ValueError:
            issues.append(
                ScriptValidationIssue(
                    "error",
                    f"Unknown dialogue speaker `{match['speaker']}`.",
                    number,
                    "unknown_speaker",
                )
            )
            continue
        if allowed_speakers is not None and speaker not in allowed_speakers:
            issues.append(
                ScriptValidationIssue(
                    "error",
                    f"Inactive dialogue speaker `{speaker}`.",
                    number,
                    "inactive_speaker",
                )
            )
        speakers.add(speaker)
        text = match["text"].strip()
        if not text:
            issues.append(
                ScriptValidationIssue("error", "Empty dialogue turn.", number, "empty_turn")
            )
        else:
            texts.append(" ".join(text.casefold().split()))
        if len(text) > max_line_chars:
            issues.append(
                ScriptValidationIssue(
                    "warning",
                    "Long turn will be partitioned for TTS.",
                    number,
                    "long_line",
                )
            )
    dialogue = script_to_dialogue_lines(script_text)
    if not dialogue:
        issues.append(
            ScriptValidationIssue("error", "Dialogue has no speakable lines.", code="empty_script")
        )
    for text, count in Counter(texts).items():
        if count > 1:
            issues.append(
                ScriptValidationIssue(
                    "warning",
                    f"An identical turn occurs {count} times; review repetition.",
                    code="repeated_turn",
                )
            )
    if require_all_characters:
        missing = set(get_character_keys()) - speakers
        if missing:
            issues.append(
                ScriptValidationIssue(
                    "warning",
                    f"Unused configured speakers: {', '.join(sorted(missing))}.",
                    code="missing_character",
                )
            )
    return ScriptValidationResult(
        issues, len(dialogue), [key for key in get_character_keys() if key in speakers]
    )


def format_validation_report(result: ScriptValidationResult) -> str:
    lines = ["Dialogue script validation:"]
    for issue in result.issues:
        location = f" line {issue.line_number}" if issue.line_number else ""
        lines.append(f"  [{issue.severity}]{location}: {issue.message}")
    if not result.issues:
        return "Dialogue script validation: ok"
    return "\n".join(lines)


def repair_dialogue_script_text(
    script_text: str, validation: ScriptValidationResult | None = None
) -> str:
    """Normalize layout and known speaker markup; never rewrite spoken wording."""
    lines = []
    for raw in script_text.splitlines():
        line = raw.strip()
        match = _FORMATTED_SPEAKER_RE.fullmatch(line)
        if match:
            try:
                resolve_character_key(match["speaker"])
            except ValueError:
                pass
            else:
                line = match["speaker"] + (match["outer"] or match["inner"]) + match["text"]
        lines.append(line)
    return "\n".join(lines).strip()
