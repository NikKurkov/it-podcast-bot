import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.audio.dialogue import script_to_dialogue_lines
from app.config.settings import settings
from app.podcast.characters import get_character_keys
from app.podcast.script_validation import (
    repair_dialogue_script_text,
    validate_dialogue_script,
)


@dataclass(frozen=True)
class ScriptPostprocessResult:
    script_text: str
    report: dict


def postprocess_dialogue_script(
    script_text: str,
    *,
    target_minutes: float | None = None,
) -> ScriptPostprocessResult:
    before_validation = validate_dialogue_script(script_text, require_all_characters=False)
    repaired_text = repair_dialogue_script_text(script_text, before_validation)
    repaired_text = _normalize_editorial_text(repaired_text)
    after_validation = validate_dialogue_script(repaired_text, require_all_characters=False)
    report = build_script_quality_report(
        repaired_text,
        original_script_text=script_text,
        target_minutes=target_minutes,
        validation_issues=[
            {
                "severity": issue.severity,
                "message": issue.message,
                "line_number": issue.line_number,
                "code": issue.code,
            }
            for issue in after_validation.issues
        ],
    )
    report["postprocess"] = {
        "changed": repaired_text != script_text,
        "original_validation_issues": len(before_validation.issues),
        "final_validation_issues": len(after_validation.issues),
        "changed_lines": _count_changed_lines(script_text, repaired_text),
    }
    return ScriptPostprocessResult(script_text=repaired_text, report=report)


def ensure_opening_and_rundown(
    script_text: str,
    *,
    topic_summaries: list[str] | None = None,
    episode_date: datetime | None = None,
) -> str:
    """Compatibility hook: framing is generated with the dialogue, never grafted on."""
    return script_text


def quality_gate_allows_tts(report: dict) -> tuple[bool, list[str]]:
    blocking = []
    if any(issue.get("severity") == "error" for issue in report.get("validation_issues", [])):
        blocking.append("validation_issues")
    return not blocking, blocking


def build_script_quality_report(
    script_text: str,
    *,
    original_script_text: str | None = None,
    validation_issues: list[dict] | None = None,
    target_minutes: float | None = None,
) -> dict:
    dialogue_lines = script_to_dialogue_lines(script_text)
    if validation_issues is None:
        validation_issues = [
            {
                "severity": issue.severity,
                "message": issue.message,
                "code": issue.code,
                "line_number": issue.line_number,
            }
            for issue in validate_dialogue_script(script_text, require_all_characters=False).issues
        ]
    word_count = sum(
        len(re.findall(r"\b[\w]+(?:[-’'][\w]+)*\b", line.text)) for line in dialogue_lines
    )
    # Approximate pacing only; ffprobe duration after rendering is authoritative.
    estimated_seconds = word_count / 135 * 60 + sum(
        line.pause_after_ms / 1000 for line in dialogue_lines[:-1]
    )
    target_seconds = (target_minutes or settings.podcast_target_minutes) * 60
    duration_status = "on_target"
    if estimated_seconds < target_seconds * 5 / 6:
        duration_status = "short"
    elif estimated_seconds > target_seconds * 1.25:
        duration_status = "long"
    speaker_counts = Counter(line.speaker for line in dialogue_lines)
    text_lint = _build_text_lint_report(dialogue_lines)
    report = {
        "word_count": word_count,
        "estimated_duration_seconds": round(estimated_seconds, 1),
        "target_duration_seconds": target_seconds,
        "duration_status": duration_status,
        "lines_count": len(dialogue_lines),
        "speaker_counts": {
            speaker: speaker_counts.get(speaker, 0) for speaker in get_character_keys()
        },
        "text_lint": text_lint,
        "validation_issues": validation_issues or [],
        "warnings": [],
    }
    if duration_status != "on_target":
        report["warnings"].append(f"duration_{duration_status}")

    for warning in text_lint["warnings"]:
        report["warnings"].append(f"text_lint:{warning}")

    if original_script_text is not None:
        report["changed_lines"] = _count_changed_lines(original_script_text, script_text)

    return report


def write_script_quality_report(
    report: dict,
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def _normalize_editorial_text(script_text: str) -> str:
    return "\n".join(line.strip() for line in script_text.splitlines()).strip()


def _build_text_lint_report(dialogue_lines) -> dict:
    line_starts = Counter(
        _line_start_signature(line.text)
        for line in dialogue_lines
        if _line_start_signature(line.text)
    )
    repeated_line_starts = {
        start: count for start, count in sorted(line_starts.items()) if count >= 2
    }

    warnings = []
    for start, count in repeated_line_starts.items():
        if count >= 3:
            warnings.append(f"repeated_line_start:{start}")

    return {
        "repeated_line_starts": repeated_line_starts,
        "warnings": warnings,
    }


def _line_start_signature(text: str, words_count: int = 3) -> str:
    words = re.findall(r"[A-Za-zА-Яа-яЁё0-9-]+", text.casefold().replace("ё", "е"))
    if len(words) < words_count:
        return ""
    return " ".join(words[:words_count])


def _count_changed_lines(before: str, after: str) -> int:
    before_lines = [line.strip() for line in before.splitlines() if line.strip()]
    after_lines = [line.strip() for line in after.splitlines() if line.strip()]
    max_len = max(len(before_lines), len(after_lines))
    changed = 0
    for index in range(max_len):
        before_line = before_lines[index] if index < len(before_lines) else ""
        after_line = after_lines[index] if index < len(after_lines) else ""
        if before_line != after_line:
            changed += 1
    return changed
