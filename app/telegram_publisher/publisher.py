import json
import logging
import shutil
import subprocess
from html import escape, unescape
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from telethon.errors import RPCError

from app.config.settings import settings
from app.db.repositories.episodes import mark_episode_published
from app.db.session import SessionLocal, init_db
from app.podcast.script_quality import build_script_quality_report, quality_gate_allows_tts
from app.telegram_reader.client import create_telegram_client, telegram_session
from app.utils.locking import exclusive_lock

TELEGRAM_CAPTION_LIMIT = 1024
PUBLISH_AUDIO_DIR = "publish"
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TelegramPublishResult:
    channel_id: str
    message_id: int
    audio_path: Path
    caption: str


async def publish_episode_package(
    package_path: Path,
    channel_id: str | None = None,
    *,
    republish: bool = False,
) -> TelegramPublishResult:
    """Publish an episode package audio file to a Telegram channel."""
    # ponytail: Linux file lock; use a shared DB lock if publishers move to multiple hosts.
    with exclusive_lock(package_path / ".package.lock", "This episode package is busy."):
        if (package_path / "telegram_publish.json").exists() and not republish:
            raise RuntimeError("Episode is already published. Use --republish to send it again.")
        return await _publish_episode_package(package_path, channel_id)


async def _publish_episode_package(
    package_path: Path,
    channel_id: str | None,
) -> TelegramPublishResult:
    target_channel = (channel_id or settings.telegram_publish_channel_id or "").strip()
    if not target_channel:
        raise RuntimeError(
            "Telegram publish channel is not configured. Set TELEGRAM_PUBLISH_CHANNEL_ID in .env.",
        )

    source_audio_path = package_path / "audio.mp3"
    if not source_audio_path.exists():
        raise FileNotFoundError(
            f"Episode audio was not found: {source_audio_path}. "
            "Generate the episode with --with-audio before publishing.",
        )

    caption = build_episode_caption(package_path)
    audio_path = prepare_publish_audio(package_path)
    client = create_telegram_client()
    async with telegram_session(client):
        entity = await _resolve_publish_entity(client, target_channel)
        try:
            message = await client.send_file(
                entity,
                file=str(audio_path),
                caption=caption,
                parse_mode="html",
                supports_streaming=True,
            )
        except RPCError as exc:
            if exc.__class__.__name__ == "ChatWriteForbiddenError":
                raise RuntimeError(
                    f"Telegram account cannot write to channel {target_channel!r}. "
                    "Add this user account as a channel admin with posting rights, "
                    "or set TELEGRAM_PUBLISH_CHANNEL_ID to another writable channel.",
                ) from exc
            raise

        result = TelegramPublishResult(
            channel_id=target_channel,
            message_id=int(message.id),
            audio_path=audio_path,
            caption=caption,
        )
        # Record the confirmed send before disconnecting: cleanup can fail too.
        write_publish_result(package_path / "telegram_publish.json", result)
    _mark_package_published(package_path, result)
    return result


def build_episode_caption(package_path: Path) -> str:
    metadata = _read_json(package_path / "episode_metadata.json")
    fallback_metadata = _read_json(package_path / "metadata.json")
    episode_title = build_episode_title(
        package_path, metadata=metadata, fallback_metadata=fallback_metadata
    )
    summaries = _episode_summaries(package_path, metadata)

    lines = [escape(episode_title), "", "Обзор главных новостей в мире IT."]
    if summaries:
        lines.append("")
        lines.append("<b>Темы выпуска:</b>")
        for summary in summaries:
            bullet = f"- {escape(_ensure_sentence_period(_short_news_title(summary)))}"
            candidate = "\n".join([*lines, bullet, "", "Приятного прослушивания!"])
            if len(candidate.encode("utf-16-le")) // 2 <= TELEGRAM_CAPTION_LIMIT:
                lines.append(bullet)
    lines.extend(["", "Приятного прослушивания!"])

    return _trim_caption("\n".join(lines), TELEGRAM_CAPTION_LIMIT)


def validate_episode_for_publish(package_path: Path) -> list[str]:
    issues = []
    if not (package_path / "audio.mp3").exists():
        issues.append("audio.mp3 is missing")
    script_path = package_path / "llm_script.md"
    if not script_path.exists():
        issues.append("llm_script.md is missing")
    else:
        report = build_script_quality_report(script_path.read_text(encoding="utf-8"))
        allowed, blocking = quality_gate_allows_tts(report)
        if not allowed:
            issues.extend(f"script quality: {item}" for item in blocking)
    return issues


def build_episode_title(
    package_path: Path,
    *,
    metadata: dict[str, Any] | None = None,
    fallback_metadata: dict[str, Any] | None = None,
) -> str:
    metadata = (
        metadata if metadata is not None else _read_json(package_path / "episode_metadata.json")
    )
    fallback_metadata = (
        fallback_metadata
        if fallback_metadata is not None
        else _read_json(package_path / "metadata.json")
    )
    episode_number = _episode_number(package_path)
    date_text = _episode_date_text(metadata, fallback_metadata)
    return f"{settings.podcast_title} #{episode_number:03d} от {date_text}"


def prepare_publish_audio(package_path: Path, cover_path: Path | None = None) -> Path:
    source_audio_path = package_path / "audio.mp3"
    if not source_audio_path.exists():
        raise FileNotFoundError(f"Episode audio was not found: {source_audio_path}")

    output_dir = package_path / PUBLISH_AUDIO_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata = _read_json(package_path / "episode_metadata.json")
    fallback_metadata = _read_json(package_path / "metadata.json")
    title = build_episode_title(
        package_path,
        metadata=metadata,
        fallback_metadata=fallback_metadata,
    )
    output_path = output_dir / f"{_safe_filename(title)}.mp3"
    resolved_cover_path = _resolve_cover_path(cover_path)

    if resolved_cover_path and resolved_cover_path.exists():
        _embed_cover_art(
            source_audio_path=source_audio_path,
            cover_path=resolved_cover_path,
            output_path=output_path,
            title=title,
        )
    else:
        shutil.copy2(source_audio_path, output_path)

    return output_path


def write_publish_result(output_path: Path, result: TelegramPublishResult) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(result)
    payload["audio_path"] = str(result.audio_path)
    payload["published_at"] = datetime.now(timezone.utc).isoformat()
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def _mark_package_published(package_path: Path, result: TelegramPublishResult) -> None:
    try:
        init_db()
        with SessionLocal() as session:
            episode = mark_episode_published(
                session,
                slug=package_path.name,
                channel_id=result.channel_id,
                message_id=result.message_id,
            )
            if episode is None:
                logger.info(
                    "Episode %s is not recorded in DB; publish JSON was written only.",
                    package_path.name,
                )
    except Exception:
        logger.exception("Could not update local episode publish history for %s", package_path)


def _resolve_channel_id(value: str) -> int | str:
    stripped = value.strip()
    if stripped.lstrip("-").isdigit():
        return int(stripped)
    return stripped


async def _resolve_publish_entity(client, value: str):
    entity = _resolve_channel_id(value)
    try:
        return await client.get_input_entity(entity)
    except (ValueError, TypeError, RPCError) as exc:
        if not isinstance(entity, int):
            raise RuntimeError(
                f"Could not resolve Telegram channel {value!r}. "
                "Check TELEGRAM_PUBLISH_CHANNEL_ID and account permissions.",
            ) from exc

        internal_id = _telegram_channel_internal_id(entity)
        async for dialog in client.iter_dialogs():
            dialog_entity = getattr(dialog, "entity", None)
            dialog_id = getattr(dialog, "id", None)
            entity_id = getattr(dialog_entity, "id", None)
            if dialog_id == entity or entity_id == internal_id:
                return dialog_entity

        raise RuntimeError(
            f"Could not resolve Telegram channel id {value!r}. "
            "Make sure the Telethon account can see this channel, or use a public/private "
            "channel username like @my_channel in TELEGRAM_PUBLISH_CHANNEL_ID.",
        ) from exc


def _telegram_channel_internal_id(value: int) -> int:
    text = str(abs(value))
    if text.startswith("100") and len(text) > 3:
        return int(text[3:])
    return abs(value)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _episode_number(package_path: Path) -> int:
    episodes_dir = package_path.parent
    if not episodes_dir.exists():
        return 1
    packages = sorted(
        path for path in episodes_dir.iterdir() if path.is_dir() and (path / "audio.mp3").exists()
    )
    try:
        return packages.index(package_path) + 1
    except ValueError:
        return len(packages) + 1


def _episode_date_text(metadata: dict[str, Any], fallback_metadata: dict[str, Any]) -> str:
    created_at = str(metadata.get("created_at") or fallback_metadata.get("created_at") or "")
    if created_at:
        try:
            parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            return parsed.strftime("%d.%m.%Y")
        except ValueError:
            pass
    return datetime.now().strftime("%d.%m.%Y")


def _episode_summaries(package_path: Path, metadata: dict[str, Any]) -> list[str]:
    summaries = []
    for source in metadata.get("sources") or []:
        summary = str(source.get("summary") or "").strip()
        if summary:
            summaries.append(summary)
    if summaries:
        return summaries

    topic_summaries = [
        str(topic).strip() for topic in metadata.get("topics") or [] if str(topic).strip()
    ]
    if topic_summaries:
        return topic_summaries

    selected_posts = _read_json_list(package_path / "selected_posts.json")
    for post in selected_posts:
        text = str(post.get("text") or "").strip()
        if text:
            summaries.append(_short_news_title(text))
    return summaries


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _safe_filename(value: str) -> str:
    replacements = {
        "№": "",
        "#": "",
        " ": "_",
        ".": "-",
    }
    result = value
    for old, new in replacements.items():
        result = result.replace(old, new)
    return "".join(char for char in result if char.isalnum() or char in {"_", "-"}).strip("_-")


def _resolve_cover_path(cover_path: Path | None) -> Path | None:
    if cover_path:
        return cover_path
    if not settings.podcast_cover_image:
        return None
    return Path(settings.podcast_cover_image)


def _embed_cover_art(
    *,
    source_audio_path: Path,
    cover_path: Path,
    output_path: Path,
    title: str,
) -> None:
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(source_audio_path),
        "-i",
        str(cover_path),
        "-map",
        "0:a",
        "-map",
        "1:v",
        "-c:a",
        "copy",
        "-c:v",
        "copy",
        "-disposition:v:0",
        "attached_pic",
        "-id3v2_version",
        "3",
        "-metadata",
        f"title={title}",
        "-metadata",
        f"album={settings.podcast_title}",
        "-metadata",
        "artist=NikCast",
        "-metadata:s:v",
        "title=Podcast cover",
        "-metadata:s:v",
        "comment=Cover (front)",
        str(output_path),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg is required to embed podcast cover art into MP3.") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Could not embed podcast cover art: {exc.stderr.strip()}") from exc


def _one_line(value: str, limit: int) -> str:
    clean = " ".join(value.split())
    if len(clean) <= limit:
        return clean
    truncated = clean[:limit].rsplit(" ", 1)[0].strip(" .,:;!?—-")
    return truncated or clean[:limit].strip(" .,:;!?—-")


def _short_news_title(value: str) -> str:
    return " ".join(value.split())


def _ensure_sentence_period(value: str) -> str:
    clean = value.strip()
    if not clean:
        return clean
    if clean.endswith((".", "!", "?")):
        return clean
    return f"{clean}."


def _trim_caption(caption: str, limit: int) -> str:
    if len(caption.encode("utf-16-le")) <= limit * 2:
        return caption
    # Only the generated bold heading uses markup. Drop it when truncating so
    # tags stay balanced, and escape each character to keep entities intact.
    text = unescape(caption.replace("<b>", "").replace("</b>", ""))
    suffix = "." * min(3, max(0, limit))
    budget = max(0, limit - len(suffix))
    parts = []
    for char in text:
        token = escape(char)
        size = len(token.encode("utf-16-le")) // 2
        if size > budget:
            break
        parts.append(token)
        budget -= size
    return "".join(parts).rstrip() + suffix
