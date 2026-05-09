import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from telethon.errors import RPCError

from app.config.settings import settings
from app.telegram_reader.client import create_telegram_client

TELEGRAM_CAPTION_LIMIT = 1024


@dataclass(frozen=True)
class TelegramPublishResult:
    channel_id: str
    message_id: int
    audio_path: Path
    caption: str


async def publish_episode_package(
    package_path: Path,
    channel_id: str | None = None,
) -> TelegramPublishResult:
    """Publish an episode package audio file to a Telegram channel."""
    target_channel = (channel_id or settings.telegram_publish_channel_id or "").strip()
    if not target_channel:
        raise RuntimeError(
            "Telegram publish channel is not configured. "
            "Set TELEGRAM_PUBLISH_CHANNEL_ID in .env.",
        )

    audio_path = package_path / "audio.mp3"
    if not audio_path.exists():
        raise FileNotFoundError(
            f"Episode audio was not found: {audio_path}. "
            "Generate the episode with --with-audio before publishing.",
        )

    caption = build_episode_caption(package_path)
    client = create_telegram_client()
    async with client:
        entity = await _resolve_publish_entity(client, target_channel)
        try:
            message = await client.send_file(
                entity,
                file=str(audio_path),
                caption=caption,
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
    write_publish_result(package_path / "telegram_publish.json", result)
    return result


def build_episode_caption(package_path: Path) -> str:
    metadata = _read_json(package_path / "episode_metadata.json")
    fallback_metadata = _read_json(package_path / "metadata.json")

    title = (
        metadata.get("title")
        or fallback_metadata.get("title")
        or package_path.name
    )
    topics = metadata.get("topics") or []

    lines = [str(title), "", "НикКаст: обзор главных новостей в мире IT."]
    if topics:
        lines.append("")
        lines.append("В выпуске:")
        for topic in topics[:5]:
            topic_title = str(topic.get("title") or topic.get("text") or "").strip()
            if topic_title:
                lines.append(f"- {_one_line(topic_title, 120)}")

    return _trim_caption("\n".join(lines), TELEGRAM_CAPTION_LIMIT)


def write_publish_result(output_path: Path, result: TelegramPublishResult) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(result)
    payload["audio_path"] = str(result.audio_path)
    payload["published_at"] = datetime.now(timezone.utc).isoformat()
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


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


def _one_line(value: str, limit: int) -> str:
    clean = " ".join(value.split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rstrip() + "..."


def _trim_caption(caption: str, limit: int) -> str:
    if len(caption) <= limit:
        return caption
    return caption[: limit - 1].rstrip() + "..."
