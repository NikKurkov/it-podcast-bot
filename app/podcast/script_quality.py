import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.audio.dialogue import script_to_dialogue_lines
from app.audio.voice_direction import apply_voice_direction
from app.podcast.characters import get_character_keys
from app.podcast.prompt_context import format_russian_episode_date
from app.podcast.script_validation import (
    repair_dialogue_script_text,
    validate_dialogue_script,
)

_DIRECT_ADDRESS_RE = re.compile(r"\b(марк|ника|глеб|арт[её]м)\b", re.IGNORECASE)
_INTERRUPTION_RE = re.compile(
    r"(подожди|секунду|ой,\s*да\s+ладно|стоп|погоди|можно\s+я)",
    re.IGNORECASE,
)
_OUTRO_RE = re.compile(
    r"(на\s+этом\s+вс[её]|с\s+вами\s+был|хорошего\s+(?:вам\s+)?(?:дня|вечера)|"
    r"до\s+новых\s+встреч|пусть\s+.+(?:день|релиз|релизы|алерт|алерты)|\bпока\b)",
    re.IGNORECASE,
)
_OUTRO_END_MARKER_RE = re.compile(
    r"(на\s+этом\s+вс[её]|это\s+были\s+все\s+новости|наш\s+выпуск\s+заканчивается|"
    r"выпуск\s+заканчивается)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ScriptPostprocessResult:
    script_text: str
    report: dict


def postprocess_dialogue_script(script_text: str) -> ScriptPostprocessResult:
    before_validation = validate_dialogue_script(script_text)
    repaired_text = repair_dialogue_script_text(script_text, before_validation)
    repaired_text = _normalize_editorial_text(repaired_text)
    repaired_text = _ensure_closing_outro(repaired_text)
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


def ensure_opening_and_rundown(
    script_text: str,
    *,
    topic_summaries: list[str] | None = None,
    episode_date: datetime | None = None,
) -> str:
    report = build_script_quality_report(script_text)
    lines = [line.strip() for line in script_text.splitlines() if line.strip()]
    prefix = []
    if not report["opening_present"]:
        prefix.append(
            "mark: "
            f"Добрый день, сегодня {format_russian_episode_date(episode_date)}, "
            "и вы слушаете НикКаст с обзором главных новостей в мире айти. "
            "Разбираем, где в этих историях технический риск, а где просто шум.",
        )
    if not report["rundown_present"]:
        rundown = _build_rundown_text(topic_summaries or [])
        prefix.append(f"nika: {rundown}")

    if not prefix:
        return script_text
    return "\n\n".join(prefix + lines).strip()


def quality_gate_allows_tts(report: dict) -> tuple[bool, list[str]]:
    blocking = []
    if report.get("validation_issues"):
        blocking.append("validation_issues")
    if not report.get("opening_present"):
        blocking.append("opening_missing")
    if not report.get("rundown_present"):
        blocking.append("rundown_missing")
    if report.get("lines_count", 0) >= 12 and report.get("transition_lines", 0) < 2:
        blocking.append("few_transitions")
    if report.get("lines_count", 0) >= 12 and not report.get("outro_present"):
        blocking.append("outro_missing")
    for speaker in get_character_keys():
        if report.get("speaker_counts", {}).get(speaker, 0) < 2:
            blocking.append(f"underused_{speaker}")
    return not blocking, blocking


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
    direct_address_lines = sum(1 for line in dialogue_lines if _DIRECT_ADDRESS_RE.search(line.text))
    interruption_lines = sum(1 for line in dialogue_lines if _INTERRUPTION_RE.search(line.text))
    repeated_openers = _repeated_openers(dialogue_lines)
    outro_present = _has_outro(dialogue_lines)
    outro_end_marker_present = _has_outro_end_marker(dialogue_lines)

    report = {
        "lines_count": len(dialogue_lines),
        "speaker_counts": {speaker: speaker_counts.get(speaker, 0) for speaker in get_character_keys()},
        "opening_present": _has_opening(first_text),
        "rundown_present": any(line.emotion == "rundown" for line in directed_lines[:4]),
        "outro_present": outro_present,
        "outro_end_marker_present": outro_end_marker_present,
        "transition_lines": emotion_counts.get("transition", 0),
        "aside_lines": emotion_counts.get("aside", 0),
        "interruption_lines": interruption_lines,
        "direct_address_lines": direct_address_lines,
        "verdict_lines": emotion_counts.get("verdict", 0),
        "emotion_counts": dict(emotion_counts),
        "repeated_openers": repeated_openers,
        "validation_issues": validation_issues or [],
        "warnings": [],
    }

    if not report["opening_present"]:
        report["warnings"].append("opening_missing")
    if not report["rundown_present"]:
        report["warnings"].append("rundown_missing")
    if len(dialogue_lines) >= 12 and report["transition_lines"] < 2:
        report["warnings"].append("few_transitions")
    if len(dialogue_lines) >= 12 and not outro_present:
        report["warnings"].append("outro_missing")
    if len(dialogue_lines) >= 12 and outro_present and not outro_end_marker_present:
        report["warnings"].append("outro_end_marker_missing")
    if len(dialogue_lines) >= 16 and direct_address_lines < 1:
        report["warnings"].append("few_direct_addresses")
    if len(dialogue_lines) >= 16 and direct_address_lines > 2:
        report["warnings"].append("too_many_direct_addresses")
    if len(dialogue_lines) >= 16 and interruption_lines < 1 and report["aside_lines"] < 1:
        report["warnings"].append("too_clean_dialogue")
    for opener, count in repeated_openers.items():
        if count > 1:
            report["warnings"].append(f"repeated_opener:{opener}")
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


def _build_rundown_text(topic_summaries: list[str]) -> str:
    summaries = [_short_topic(summary) for summary in topic_summaries if summary.strip()]
    if summaries:
        return "В выпуске: " + "; ".join(summaries[:5]) + "."
    return (
        "В выпуске: самые заметные IT-события дня, риски для команд, "
        "инструменты и решения, которые стоит проверить."
    )


def _ensure_closing_outro(script_text: str, min_lines: int = 10) -> str:
    dialogue_lines = script_to_dialogue_lines(script_text)
    if len(dialogue_lines) < min_lines:
        return script_text.strip()
    if _has_outro(dialogue_lines):
        if _has_outro_end_marker(dialogue_lines):
            return script_text.strip()
        return _insert_outro_end_marker(script_text)

    outro_lines = [
        "mark: На этом всё, это были главные новости на сегодня. С вами были Марк, Ника, Глеб и Артём.",
        "nika: Хорошего вам дня, пусть релизы проходят спокойно, а алерты молчат.",
        "gleb: И пусть никто не чинит зависимости в три ночи. Пока.",
        "artem: Проверьте резервные сценарии и до новых встреч.",
    ]
    return "\n".join([script_text.strip(), *outro_lines]).strip()


def _short_topic(text: str, max_chars: int = 90) -> str:
    clean_text = " ".join(text.replace("\n", " ").split()).strip(" -—")
    if len(clean_text) <= max_chars:
        return clean_text
    return f"{clean_text[: max_chars - 3].rstrip()}..."


def _has_outro(dialogue_lines) -> bool:
    return any(_OUTRO_RE.search(line.text) for line in dialogue_lines[-5:])


def _has_outro_end_marker(dialogue_lines) -> bool:
    return any(_OUTRO_END_MARKER_RE.search(line.text) for line in dialogue_lines[-6:])


def _insert_outro_end_marker(script_text: str) -> str:
    raw_lines = [line.strip() for line in script_text.splitlines() if line.strip()]
    insert_at = len(raw_lines)
    for index in range(len(raw_lines) - 1, max(-1, len(raw_lines) - 6), -1):
        if _OUTRO_RE.search(raw_lines[index]):
            insert_at = index
    raw_lines.insert(insert_at, "mark: На этом всё, это были главные новости на сегодня.")
    return "\n".join(raw_lines).strip()


def _repeated_openers(dialogue_lines) -> dict[str, int]:
    tracked_openers = {
        "а по-человечески": "а по-человечески",
        "а по человечески": "а по-человечески",
        "почему это важно": "почему это важно",
        "что это значит": "что это значит",
        "как это влияет": "как это влияет",
        "как это поможет": "как это поможет",
    }
    counts = Counter()
    for line in dialogue_lines:
        normalized = line.text.casefold().replace("ё", "е")
        for phrase, label in tracked_openers.items():
            if normalized.startswith(phrase):
                counts[label] += 1
    return dict(counts)


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
