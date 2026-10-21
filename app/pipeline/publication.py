import json
from pathlib import Path

from app.pipeline.daily_digest import DigestItem
from app.config.settings import settings
from app.podcast.characters import get_active_character_keys


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
        f"{settings.podcast_title}: обсуждение новостей выпуска.",
        "",
    ]
    if duration_seconds:
        lines.extend([f"Длительность: {_format_duration(duration_seconds)}", ""])
    if topics:
        lines.extend([f"Темы: {', '.join(topics)}", ""])

    lines.extend(["## Примерные таймкоды (оценка, не разметка аудио)", ""])
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
    research_sources: dict[int, list[dict[str, str]]] | None = None,
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
        "characters": get_active_character_keys(),
        "sources": [
            {
                "source": item.source,
                "title": item.title,
                "url": item.url,
                "message_date": item.message_date.isoformat() if item.message_date else None,
                "summary": _short_topic(item.text),
                "supporting_sources": [
                    {"url": source["url"], "title": source["title"]}
                    for source in (research_sources or {}).get(item.post_id, [])
                    if source.get("status") == "fetched"
                ],
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
    return list(dict.fromkeys(_short_topic(item.text) for item in digest_items))


def _description(digest_items: list[DigestItem]) -> str:
    return f"{settings.podcast_title}: обсуждение выбранных новостей. Источники указаны в описании."


def _short_topic(text: str, max_chars: int | None = None) -> str:
    # All qualifiers are part of the source, even on later physical lines.
    return " ".join(text.split())


def _format_duration(duration_seconds: float | int) -> str:
    total_seconds = int(round(duration_seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def refresh_rendered_package(
    path: Path, *, provider: str | None, with_music: bool, music_volume: float
) -> None:
    """Refresh publication files after rendering an existing source snapshot."""
    from datetime import datetime, timezone

    def read_object(filename: str) -> dict:
        file = path / filename
        if not file.exists():
            return {}
        value = json.loads(file.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"Invalid package object: {filename}")
        return value

    metadata = read_object("metadata.json")
    generation = read_object("script_generation.json")
    sources = read_object("source_research.json")
    selected = json.loads((path / "selected_posts.json").read_text(encoding="utf-8"))
    items = [
        DigestItem(**{**item, "message_date": datetime.fromisoformat(item["message_date"])})
        for item in selected
    ]
    metadata.setdefault("title", path.name)
    metadata.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    provider = provider or metadata.get("tts_provider")
    metadata.update(
        posts_count=len(items),
        post_ids=[item.post_id for item in items],
        tts_provider=provider,
        background_music=with_music,
        background_music_volume=music_volume if with_music else None,
        audio_rendered_at=datetime.now(timezone.utc).isoformat(),
    )
    files = metadata.setdefault("files", {})
    for key, value in files.items():
        if isinstance(value, str) and (path / Path(value).name).is_file():
            files[key] = str(path / Path(value).name)
    files.update(
        {
            "audio_mp3": str(path / "audio.mp3"),
            "audio_wav": str(path / "audio.wav"),
            "audio_voice_wav": str(path / "audio_voice.wav")
            if (path / "audio_voice.wav").exists()
            else None,
            "audio_report": str(path / "audio_report.json"),
            "llm_script": str(path / "llm_script.md"),
        }
    )
    for name in ("spoken_script.md", "speech_pronunciation.json"):
        if (path / name).exists():
            files[Path(name).stem] = str(path / name)
    model = (
        generation.get("model")
        or metadata.get("llm_script_generation_model")
        or metadata.get("llm_model")
    )
    write_show_notes(
        title=metadata["title"],
        digest_items=items,
        output_path=path / "show_notes.md",
        audio_report_path=path / "audio_report.json",
    )
    write_episode_metadata(
        title=metadata["title"],
        created_at=metadata["created_at"],
        digest_items=items,
        output_path=path / "episode_metadata.json",
        audio_path=path / "audio.mp3",
        audio_report_path=path / "audio_report.json",
        llm_model=model,
        tts_provider=provider,
        background_music=with_music,
        research_sources={int(key): value for key, value in sources.items()},
    )
    (path / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
