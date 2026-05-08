import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from app.audio.dialogue import script_to_dialogue_lines
from app.audio.voice_direction import apply_voice_direction
from app.podcast.characters import get_character_keys
from app.podcast.script_validation import (
    repair_dialogue_script_text,
    validate_dialogue_script,
)


@dataclass(frozen=True)
class ScriptPostprocessResult:
    script_text: str
    report: dict


def postprocess_dialogue_script(script_text: str) -> ScriptPostprocessResult:
    before_validation = validate_dialogue_script(script_text)
    repaired_text = repair_dialogue_script_text(script_text, before_validation)
    repaired_text = _normalize_editorial_text(repaired_text)
    after_validation = validate_dialogue_script(repaired_text)
    report = build_script_quality_report(
        repaired_text,
        original_script_text=script_text,
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


def build_script_quality_report(
    script_text: str,
    *,
    original_script_text: str | None = None,
    validation_issues: list[dict] | None = None,
) -> dict:
    dialogue_lines = script_to_dialogue_lines(script_text)
    speaker_counts = Counter(line.speaker for line in dialogue_lines)
    directed_lines = [
        apply_voice_direction(
            line.speaker,
            line.text,
            base_pause_after_ms=line.pause_after_ms,
        )
        for line in dialogue_lines
    ]
    emotion_counts = Counter(line.emotion or "plain" for line in directed_lines)
    first_text = dialogue_lines[0].text if dialogue_lines else ""

    report = {
        "lines_count": len(dialogue_lines),
        "speaker_counts": {speaker: speaker_counts.get(speaker, 0) for speaker in get_character_keys()},
        "opening_present": _has_opening(first_text),
        "rundown_present": any(line.emotion == "rundown" for line in directed_lines[:4]),
        "transition_lines": emotion_counts.get("transition", 0),
        "aside_lines": emotion_counts.get("aside", 0),
        "verdict_lines": emotion_counts.get("verdict", 0),
        "emotion_counts": dict(emotion_counts),
        "validation_issues": validation_issues or [],
        "warnings": [],
    }

    if not report["opening_present"]:
        report["warnings"].append("opening_missing")
    if not report["rundown_present"]:
        report["warnings"].append("rundown_missing")
    if len(dialogue_lines) >= 12 and report["transition_lines"] < 2:
        report["warnings"].append("few_transitions")
    for speaker in get_character_keys():
        if speaker_counts.get(speaker, 0) < 2:
            report["warnings"].append(f"underused_{speaker}")

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
    replacements = [
        (r"\bэто\s+уже\s+было\.\s*это\s+уже\s+было\b", "это уже было"),
        (r"\bда,\s+но\s+это\s+уже\s+было\b", "это уже было"),
        (r"\bсовершенно\s+верно\.\s*", ""),
        (r"\bабсолютно\s+верно\.\s*", ""),
        (r"\s+([,.!?;:])", r"\1"),
    ]
    result = script_text
    for pattern, replacement in replacements:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    lines = [re.sub(r"\s+", " ", line).strip() for line in result.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _has_opening(first_text: str) -> bool:
    normalized = first_text.casefold().replace("ё", "е")
    return "добрый день" in normalized and "никкаст" in normalized


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
