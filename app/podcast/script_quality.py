import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.audio.dialogue import script_to_dialogue_lines
from app.audio.voice_direction import apply_voice_direction
from app.config.settings import settings
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
_CHARACTER_NAME_RE = r"(?:Марк|Ника|Глеб|Арт[её]м)"
_TEXT_LINT_WORDS = {
    "важно": r"\bважн\w*",
    "риск": r"\bриск\w*",
    "вывод": r"\bвывод\w*",
    "проверить": r"\bпровер\w*",
    "зафиксировать": r"\bзафикс\w*",
}
_TEXT_LINT_CONSTRUCTS = {
    "здесь_важно": r"\bздесь\s+важн\w*",
    "вывод_простой": r"\bвывод\s+прост\w*",
    "практический_смысл": r"\bпрактическ\w+\s+смысл",
    "практический_вывод": r"\bпрактическ\w+\s+вывод",
    "команде_нужно": r"\bкоманд[ае]\s+нужн\w*",
}


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
        prefix.append(f"mark: {_build_opening_text(topic_summaries or [], episode_date)}")
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
    text_lint = _build_text_lint_report(dialogue_lines)
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
        "text_lint": text_lint,
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
    for warning in text_lint["warnings"]:
        report["warnings"].append(f"text_lint:{warning}")
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
        (
            r"анонс\s+звучит\s+бодро,\s+но\s+его\s+еще\s+надо\s+проверять:\s*"
            r"проверять\s+прид[её]тся\s+реальные\s+ограничения",
            "анонс звучит бодро, но реальные ограничения всё равно придётся проверить",
        ),
        (
            r"витрина\s+красивая,\s+а\s+ограничения\s+вс[её]\s+равно\s+придется\s+смотреть\s+руками:\s*"
            r"проверять\s+прид[её]тся\s+реальные\s+ограничения",
            "витрина красивая, а ограничения всё равно придётся проверять руками",
        ),
        (r"\s+([,.!?;:])", r"\1"),
    ]
    result = script_text
    for pattern, replacement in replacements:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    phrase_counts: Counter[str] = Counter()
    sentence_counts: Counter[str] = Counter()
    lines = [_normalize_dialogue_line(line, phrase_counts=phrase_counts) for line in result.splitlines()]
    lines = [_vary_repeated_sentences(line, sentence_counts=sentence_counts) for line in lines]
    lines = _remove_weak_transition_lines(lines)
    lines = _remove_duplicate_opening_lines([line for line in lines if line])
    lines = _thin_excess_direct_addresses(lines)
    return "\n".join(lines).strip()


def _build_rundown_text(topic_summaries: list[str]) -> str:
    summaries = [_short_topic(summary) for summary in topic_summaries if summary.strip()]
    if summaries:
        return "В выпуске: " + "; ".join(summaries[:5]) + "."
    return (
        "В выпуске: самые заметные IT-события дня, риски для команд, "
        "инструменты и решения, которые стоит проверить."
    )


def _build_opening_text(topic_summaries: list[str], episode_date: datetime | None) -> str:
    variants = [
        "Сегодня в выпуске смотрим, какие новости действительно меняют работу команд.",
        "Что новенького: проверяем факты, последствия и то, что важно для айти-команд.",
        "Итак, сегодня новости такие: отделяем подтверждённые факты от громких формулировок.",
        "Пройдёмся по главным сигналам дня и посмотрим, где есть практические последствия.",
    ]
    seed = sum(ord(char) for summary in topic_summaries for char in summary)
    suffix = variants[seed % len(variants)]
    return (
        f"Добрый день, сегодня {format_russian_episode_date(episode_date)}, "
        f"и вы слушаете {settings.podcast_title} с обзором главных новостей в мире айти. "
        f"{suffix}"
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
    clean_text = _cut_topic_title(clean_text)
    clean_text = _compact_topic_title(clean_text)
    clean_text = _drop_truncated_topic_tail(clean_text)
    if len(clean_text) <= max_chars:
        return clean_text
    return _drop_truncated_topic_tail(clean_text[:max_chars].rsplit(" ", 1)[0].strip())


def _cut_topic_title(text: str) -> str:
    text = re.split(r"\s+(?:Старт продаж|Продажи)\b", text, maxsplit=1, flags=re.IGNORECASE)[0]
    match = re.search(r"\s+[—–-]\s+|[.:?!…]+(?:\s+|$)", text)
    if match:
        title = text[: match.start()].strip(" .,:;!?—-")
        tail = text[match.end() :].strip(" .,:;!?—-")
        if _is_weak_topic_title(title) and tail:
            return _cut_topic_title(tail)
        return title
    return text.strip(" .,:;!?—-")


def _drop_truncated_topic_tail(text: str) -> str:
    fragments = {
        "заплан",
        "которая",
        "которое",
        "который",
        "которые",
        "создает",
        "создаёт",
        "экс",
        "официальных",
        "производител",
    }
    words = text.split()
    while words and words[-1].casefold().replace("ё", "е").strip(".,:;!?—-") in fragments:
        words.pop()
    return " ".join(words).strip(" .,:;!?—-")


def _compact_topic_title(text: str, max_words: int = 9) -> str:
    text = _drop_weak_topic_prefix(text)
    words = text.split()
    if len(words) <= max_words:
        return text.strip(" .,:;!?—-")

    entity = _extract_topic_entity(text)
    event = _extract_topic_event(text)
    if entity and event and event.casefold().replace("ё", "е") not in entity.casefold().replace("ё", "е"):
        compact = f"{entity} {event}"
    else:
        compact = " ".join(words[:max_words])
    return compact.strip(" .,:;!?—-")


def _drop_weak_topic_prefix(text: str) -> str:
    return re.sub(
        r"^(?:по\s+исходной\s+новости|важное|и\s+важное|к\s+важным\s+новостям)\s*[:—–-]?\s+",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip(" .,:;!?—-")


def _extract_topic_entity(text: str) -> str:
    words = text.split()
    entity_words = []
    for word in words[:8]:
        cleaned = word.strip("«»\"'()[]{}.,:;!?—-")
        if not cleaned:
            continue
        if (
            re.search(r"[A-ZА-ЯЁ0-9]", cleaned)
            or "-" in cleaned
            or cleaned.casefold() in {"api", "llm", "ios"}
        ):
            entity_words.append(cleaned)
            continue
        if entity_words:
            break
    if entity_words:
        return " ".join(entity_words[:4])
    return " ".join(words[:3]).strip(" .,:;!?—-")


def _extract_topic_event(text: str) -> str:
    tail = r"(?:\s+[A-Za-zА-Яа-яЁё0-9-]+){0,4}"
    event_patterns = [
        rf"\b(?:массово\s+)?(?:сбо\w+|не\s+запуска\w+|снизил\w*\s+доступност\w*)\b{tail}",
        rf"\b(?:официально\s+)?(?:выпуст\w+|представ\w+|запуст\w+|анонсир\w+|готовит\w*)\b{tail}",
        rf"\b(?:заблокир\w+|огранич\w+|зафиксир\w+)\b{tail}",
        rf"\b(?:уязвимост\w+|CVE-\d[\w-]*)\b{tail}",
    ]
    for pattern in event_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(0).strip(" .,:;!?—-")
    return ""


def _is_weak_topic_title(text: str) -> bool:
    normalized = text.casefold().replace("ё", "е").strip(" .,:;!?—-")
    return normalized in {
        "finally",
        "finally...",
        "факт дня",
        "важно",
        "и важное",
        "и к важным новостям",
        "срочно",
    }


def _normalize_dialogue_line(line: str, *, phrase_counts: Counter[str] | None = None) -> str:
    line = re.sub(r"\s+", " ", line).strip()
    match = re.match(r"^(?P<speaker>[\wА-Яа-яЁё-]+)\s*[:：]\s*(?P<text>.*)$", line)
    if not match:
        return line
    speaker = match.group("speaker")
    speaker_key = speaker.casefold().replace("ё", "е")
    text = match.group("text").strip()
    text = _normalize_character_names(text)
    text = _normalize_weak_transition_title(text)
    text = _remove_self_address(text, speaker_key)
    text = _normalize_speaker_gender_agreement(text, speaker_key)
    text = _tighten_editorial_labels(text)
    if phrase_counts is None:
        phrase_counts = Counter()
    text = _vary_mechanical_phrases(text, phrase_counts)
    if text.casefold().replace("ё", "е").startswith("в выпуске:"):
        text = _normalize_rundown_text(text)
    text = _capitalize_sentence_starts(text)
    return f"{speaker}: {text}" if text else ""


def _normalize_rundown_text(text: str) -> str:
    _, _, payload = text.partition(":")
    topics = [
        topic
        for topic in (_short_topic(part) for part in payload.split(";") if part.strip())
        if topic and not _is_weak_topic_title(topic)
    ]
    if not topics:
        return text
    return "В выпуске: " + "; ".join(topics) + "."


def _normalize_character_names(text: str) -> str:
    replacements = {
        r"\bMark\b": "Марк",
        r"\bNika\b": "Ника",
        r"\bGleb\b": "Глеб",
        r"\bArtem\b": "Артём",
    }
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def _normalize_weak_transition_title(text: str) -> str:
    transition_re = (
        r"(?P<prefix>^(?:первая\s+зацепка|а\s+вот\s+следующая\s+тема|"
        r"дальше\s+история\s+с\s+подвохом|переключаемся\s+на\s+практический\s+риск)\s*:\s*)"
    )
    return re.sub(
        transition_re + r"(?:finally|факт\s+дня)\s*[.:!?…—–-]+\s*(?P<tail>.+)$",
        lambda match: f"{match.group('prefix')}{match.group('tail')}",
        text,
        flags=re.IGNORECASE,
    ).strip()


def _normalize_speaker_gender_agreement(text: str, speaker_key: str) -> str:
    if speaker_key == "nika":
        replacements = {
            r"\bя\s+бы\s+перев[её]л\b": "я бы перевела",
            r"\bя\s+бы\s+сказал\b": "я бы сказала",
            r"\bя\s+бы\s+спросил\b": "я бы спросила",
            r"\bя\s+бы\s+добавил\b": "я бы добавила",
            r"\bя\s+бы\s+проверил\b": "я бы проверила",
            r"\bя\s+бы\s+посмотрел\b": "я бы посмотрела",
            r"\bя\s+спросил\b": "я спросила",
            r"\bя\s+сказал\b": "я сказала",
            r"\bя\s+добавил\b": "я добавила",
        }
    elif speaker_key in {"mark", "gleb", "artem"}:
        replacements = {
            r"\bя\s+бы\s+перевела\b": "я бы перевёл",
            r"\bя\s+бы\s+сказала\b": "я бы сказал",
            r"\bя\s+бы\s+спросила\b": "я бы спросил",
            r"\bя\s+бы\s+добавила\b": "я бы добавил",
            r"\bя\s+бы\s+проверила\b": "я бы проверил",
            r"\bя\s+бы\s+посмотрела\b": "я бы посмотрел",
            r"\bя\s+спросила\b": "я спросил",
            r"\bя\s+сказала\b": "я сказал",
            r"\bя\s+добавила\b": "я добавил",
        }
    else:
        return text

    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def _tighten_editorial_labels(text: str) -> str:
    replacements = [
        (r"^здесь\s+важно\s+проверить\b", "Проверьте"),
        (r"^здесь\s+важно\s+зафиксировать\b", "Зафиксируйте"),
        (r"^здесь\s+важно\s+сравнить\b", "Сравните"),
        (r"^здесь\s+важно\s+вынести\b", "Вынесите"),
        (r"^здесь\s+важно\s+заложить\b", "Заложите"),
        (r"^для\s+команды\s+вывод\s+простой\s*:\s*", "Для команды: "),
        (r"^вывод\s+простой\s*:\s*", ""),
        (r"^практический\s+шаг\s+простой\s*:\s*", ""),
        (r"^практический\s+смысл\s+такой\s*:\s*", ""),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", text).strip()


def _remove_self_address(text: str, speaker_key: str) -> str:
    self_names = {
        "mark": ["Марк"],
        "nika": ["Ника"],
        "gleb": ["Глеб"],
        "artem": ["Артём", "Артем"],
    }.get(speaker_key, [])
    for name in self_names:
        text = re.sub(rf"^\s*{name}\s*,\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(rf"(?<=[.!?])\s*{name}\s*,\s*", " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", text).strip()


def _vary_mechanical_phrases(text: str, phrase_counts: Counter[str]) -> str:
    variants = {
        "а по-человечески": [
            "если проще",
            "на бытовом уровне",
            "в переводе с технарского",
            "короче",
            "без витрины",
            "если отбросить упаковку",
        ],
        "практический вывод": [
            "вывод",
            "прикладной смысл",
            "рабочий вывод",
            "что проверить",
        ],
        "для разработчиков и пользователей": [
            "для команд и пользователей",
            "для тех, кто это поддерживает",
            "для продуктовых команд",
        ],
        "практический смысл простой": [
            "если совсем коротко",
            "рабочий смысл такой",
            "главная проверка здесь простая",
        ],
        "тут не хайп важен": [
            "здесь важен не заголовок",
            "я бы смотрел не на шум",
            "главный вопрос не в эффектности",
        ],
        "красивый анонс сам по себе ничего не гарантирует": [
            "анонс звучит бодро, но его еще надо проверять",
            "витрина красивая, а ограничения всё равно придется смотреть руками",
        ],
        "я бы не радовался раньше времени": [
            "я бы сначала дождался практики",
            "праздновать рано",
        ],
    }
    for phrase, options in variants.items():
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        while pattern.search(text):
            replacement = options[phrase_counts[phrase] % len(options)]
            phrase_counts[phrase] += 1
            text = pattern.sub(replacement, text, count=1)
    text = re.sub(r"\bчто\s+значит\s+", "", text, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", text).strip()


def _vary_repeated_sentences(line: str, *, sentence_counts: Counter[str]) -> str:
    match = re.match(r"^(?P<speaker>[\wА-Яа-яЁё-]+)\s*[:：]\s*(?P<text>.*)$", line)
    if not match:
        return line
    speaker = match.group("speaker")
    text = match.group("text").strip()
    replacements = {
        "Тут не хайп важен, а то, насколько команда понимает, где у неё точка отказа.": [
            "Здесь важнее понять, где у команды слабое место и кто его чинит.",
            "Я бы проверил не заголовок, а реальную точку отказа.",
        ],
        "Практический смысл простой: меньше догадок, больше проверяемых фактов и наблюдаемости.": [
            "Практически это про наблюдаемость, факты и меньше решений на ощущениях.",
            "Вывод простой: сначала данные и логи, потом уже красивые версии.",
        ],
        "Зафиксируйте, что меняется для сборки, данных, доступов или пользовательского сценария.": [
            "Запишите, какие доступы, данные и сценарии реально задевает эта новость.",
            "Проверьте, что именно меняется в сборке, правах и пользовательском пути.",
        ],
    }
    for sentence, options in replacements.items():
        if sentence not in text:
            continue
        count = sentence_counts[sentence]
        sentence_counts[sentence] += 1
        if count == 0:
            continue
        replacement = options[(count - 1) % len(options)]
        text = text.replace(sentence, replacement, 1)
    return f"{speaker}: {text}" if text else ""


def _capitalize_sentence_starts(text: str) -> str:
    result = []
    capitalize_next = True
    for char in text:
        if capitalize_next and char.isalpha():
            result.append(char.upper())
            capitalize_next = False
            continue
        result.append(char)
        if char in ".!?":
            capitalize_next = True
    return "".join(result)


def _remove_duplicate_opening_lines(lines: list[str]) -> list[str]:
    result = []
    opening_seen = False
    for line in lines:
        has_opening = _has_opening(line)
        if has_opening and opening_seen:
            continue
        if has_opening:
            opening_seen = True
        result.append(line)
    return result


def _remove_weak_transition_lines(lines: list[str]) -> list[str]:
    result = []
    weak_transition_re = re.compile(
        r"^[\wА-Яа-яЁё-]+\s*[:：]\s*"
        r"(?:первая\s+зацепка|а\s+вот\s+следующая\s+тема|дальше\s+история\s+с\s+подвохом|"
        r"переключаемся\s+на\s+практический\s+риск)\s*:\s*"
        r"(?:finally|факт\s+дня)\s*[.!?…]*\s*$",
        re.IGNORECASE,
    )
    for line in lines:
        if weak_transition_re.match(line):
            continue
        result.append(line)
    return result


def _thin_excess_direct_addresses(lines: list[str]) -> list[str]:
    allowed_addresses = _allowed_direct_address_count(len(lines))
    if allowed_addresses < 0:
        return lines

    result = []
    direct_address_count = 0
    for line in lines:
        if not _DIRECT_ADDRESS_RE.search(line):
            result.append(line)
            continue

        direct_address_count += 1
        if direct_address_count <= allowed_addresses:
            result.append(line)
            continue

        result.append(_remove_vocative_address(line))
    return result


def _allowed_direct_address_count(lines_count: int) -> int:
    if lines_count < 8:
        return 3
    if lines_count < 16:
        return 2
    return 2


def _remove_vocative_address(line: str) -> str:
    match = re.match(r"^(?P<speaker>[\wА-Яа-яЁё-]+)\s*[:：]\s*(?P<text>.*)$", line)
    if not match:
        return line

    speaker = match.group("speaker")
    text = match.group("text").strip()
    text = re.sub(
        rf"^((?:подожди|погоди|секунду|стоп|слушай|смотри|ой)\s*,\s*){_CHARACTER_NAME_RE}\s*,\s*",
        r"\1",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        rf"^\s*{_CHARACTER_NAME_RE}\s*,\s*",
        "",
        text,
        count=1,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        rf"(?<=[.!?])\s*{_CHARACTER_NAME_RE}\s*,\s*",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\s{2,}", " ", text).strip()
    return f"{speaker}: {text}" if text else ""


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


def _build_text_lint_report(dialogue_lines) -> dict:
    full_text = " ".join(line.text for line in dialogue_lines).casefold().replace("ё", "е")
    word_counts = {
        label: len(re.findall(pattern, full_text, flags=re.IGNORECASE))
        for label, pattern in _TEXT_LINT_WORDS.items()
    }
    construct_counts = {
        label: len(re.findall(pattern, full_text, flags=re.IGNORECASE))
        for label, pattern in _TEXT_LINT_CONSTRUCTS.items()
    }
    line_starts = Counter(
        _line_start_signature(line.text)
        for line in dialogue_lines
        if _line_start_signature(line.text)
    )
    repeated_line_starts = {
        start: count
        for start, count in sorted(line_starts.items())
        if count >= 2
    }

    warnings = []
    lines_count = max(len(dialogue_lines), 1)
    for label, count in word_counts.items():
        if count >= max(4, round(lines_count * 0.35)):
            warnings.append(f"overused_word:{label}")
    for label, count in construct_counts.items():
        if count >= 2:
            warnings.append(f"repeated_construct:{label}")
    for start, count in repeated_line_starts.items():
        if count >= 3:
            warnings.append(f"repeated_line_start:{start}")

    return {
        "word_counts": word_counts,
        "construct_counts": construct_counts,
        "repeated_line_starts": repeated_line_starts,
        "warnings": warnings,
    }


def _line_start_signature(text: str, words_count: int = 3) -> str:
    words = re.findall(r"[A-Za-zА-Яа-яЁё0-9-]+", text.casefold().replace("ё", "е"))
    if len(words) < words_count:
        return ""
    return " ".join(words[:words_count])


def _has_opening(first_text: str) -> bool:
    normalized = first_text.casefold().replace("ё", "е")
    podcast_title = settings.podcast_title.casefold().replace("ё", "е")
    return "добрый день" in normalized and (
        podcast_title in normalized
        or ("вы слушаете" in normalized and "с обзором" in normalized)
    )


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
