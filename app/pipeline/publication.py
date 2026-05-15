import json
import re
from pathlib import Path

from app.pipeline.daily_digest import DigestItem
from app.pipeline.scoring import detect_topics


def write_show_notes(
    *,
    title: str,
    digest_items: list[DigestItem],
    output_path: Path,
    audio_report_path: Path | None = None,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration_seconds = _audio_duration_seconds(audio_report_path)
    timestamps = estimate_topic_timestamps(len(digest_items), duration_seconds)
    topics = _episode_topics(digest_items)

    lines = [
        f"# {title}",
        "",
        "НикКаст: разговорное техно-расследование по главным IT-новостям выпуска.",
        "",
    ]
    if duration_seconds:
        lines.extend([f"Длительность: {_format_duration(duration_seconds)}", ""])
    if topics:
        lines.extend([f"Темы: {', '.join(topics)}", ""])

    lines.extend(["## Таймкоды", ""])
    if digest_items:
        lines.append(f"{timestamps[0]} — Вступление и обзор тем")
        for index, item in enumerate(digest_items, start=1):
            timestamp = timestamps[index] if index < len(timestamps) else "00:00"
            lines.append(f"{timestamp} — {_short_topic(item.text)}")
    else:
        lines.append("00:00 — Выпуск без выбранных новостей")

    lines.extend(["", "## Источники", ""])
    for index, item in enumerate(digest_items, start=1):
        source = f"@{item.source}"
        date = item.message_date.isoformat() if item.message_date else ""
        lines.append(f"{index}. {source} — {_short_topic(item.text)}")
        if date:
            lines.append(f"   Дата: {date}")
        if item.url:
            lines.append(f"   Ссылка: {item.url}")

    lines.extend(["", "## Практический вывод", ""])
    lines.append(
        "Проверьте зависимости от внешних сервисов, резервные сценарии доступа, "
        "политику хранения данных и наблюдаемость критичных инструментов.",
    )
    output_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return output_path


def write_episode_metadata(
    *,
    title: str,
    created_at: str,
    digest_items: list[DigestItem],
    output_path: Path,
    audio_path: Path | None = None,
    audio_report_path: Path | None = None,
    llm_model: str | None = None,
    tts_provider: str | None = None,
    background_music: bool | None = None,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration_seconds = _audio_duration_seconds(audio_report_path)
    metadata = {
        "title": title,
        "description": _description(digest_items),
        "created_at": created_at,
        "duration_seconds": duration_seconds,
        "duration": _format_duration(duration_seconds) if duration_seconds else None,
        "audio_path": str(audio_path) if audio_path else None,
        "topics": _episode_topics(digest_items),
        "characters": ["mark", "gleb", "nika", "artem"],
        "sources": [
            {
                "source": item.source,
                "title": item.title,
                "url": item.url,
                "message_date": item.message_date.isoformat() if item.message_date else None,
                "summary": _short_topic(item.text),
            }
            for item in digest_items
        ],
        "generation": {
            "llm_model": llm_model,
            "tts_provider": tts_provider,
            "background_music": background_music,
        },
    }
    output_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def estimate_topic_timestamps(topic_count: int, duration_seconds: float | None) -> list[str]:
    if topic_count <= 0:
        return ["00:00"]
    if not duration_seconds or duration_seconds <= 0:
        return [_format_duration(index * 90) for index in range(topic_count + 1)]

    intro_seconds = min(45.0, max(20.0, duration_seconds * 0.12))
    content_seconds = max(duration_seconds - intro_seconds - 20.0, topic_count * 10.0)
    segment_seconds = content_seconds / topic_count
    timestamps = ["00:00"]
    for index in range(topic_count):
        timestamps.append(_format_duration(int(intro_seconds + index * segment_seconds)))
    return timestamps


def _audio_duration_seconds(audio_report_path: Path | None) -> float | None:
    if not audio_report_path or not audio_report_path.exists():
        return None
    try:
        report = json.loads(audio_report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    mp3_items = [item for item in report if str(item.get("path", "")).endswith(".mp3")]
    candidates = mp3_items or report
    if not candidates:
        return None
    duration = candidates[0].get("duration_seconds")
    return float(duration) if duration else None


def _episode_topics(digest_items: list[DigestItem]) -> list[str]:
    topics = []
    seen = set()
    for item in digest_items:
        for topic in detect_topics(item.text):
            if topic in seen:
                continue
            seen.add(topic)
            topics.append(topic)
    return topics


def _description(digest_items: list[DigestItem]) -> str:
    if not digest_items:
        return "НикКаст с обзором главных новостей в мире айти."
    topics = "; ".join(_short_topic(item.text) for item in digest_items[:3])
    return f"НикКаст с обзором главных IT-новостей: {topics}."


def _short_topic(text: str, max_chars: int = 110) -> str:
    clean_text = " ".join(text.replace("\n", " ").split())
    clean_text = clean_text.strip(" -—")
    clean_text = _cut_topic_title(clean_text)
    if len(clean_text) <= max_chars:
        return clean_text
    return _drop_truncated_topic_tail(clean_text[:max_chars].rsplit(" ", 1)[0].strip())


def _cut_topic_title(text: str) -> str:
    text = re.split(r"\s+(?:Старт продаж|Продажи)\b", text, maxsplit=1, flags=re.IGNORECASE)[0]
    match = re.search(r"\s+[—–-]\s+|[.:?!…]+(?:\s+|$)", text)
    if match:
        text = text[: match.start()]
    return _drop_truncated_topic_tail(text.strip(" .,:;!?—-"))


def _drop_truncated_topic_tail(text: str) -> str:
    fragments = {
        "заплан",
        "экс",
        "официальных",
        "производител",
    }
    words = text.split()
    while words and words[-1].casefold().replace("ё", "е").strip(".,:;!?—-") in fragments:
        words.pop()
    return " ".join(words).strip(" .,:;!?—-")


def _format_duration(duration_seconds: float | int) -> str:
    total_seconds = int(round(duration_seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"
