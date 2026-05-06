import json
import logging
from typing import Any

from telethon.errors import RPCError

from app.config.settings import settings
from app.db.repositories.posts import save_or_update_post
from app.db.repositories.sources import get_or_create_source
from app.db.session import SessionLocal, init_db
from app.telegram_reader.channels import get_channels
from app.telegram_reader.client import create_telegram_client
from app.utils.dates import ensure_utc
from app.utils.text import is_meaningful_text, normalize_text

logger = logging.getLogger(__name__)


def _message_url(channel_username: str, message_id: int) -> str | None:
    if "/" in channel_username or channel_username.startswith("+"):
        return None

    return f"https://t.me/{channel_username.lstrip('@')}/{message_id}"


def _message_to_raw_json(message: Any) -> str | None:
    try:
        return json.dumps(message.to_dict(), ensure_ascii=False, default=str)
    except (TypeError, ValueError, AttributeError):
        return None


async def collect_latest_posts(
    limit_per_channel: int | None = None,
    channels: list[str] | None = None,
) -> dict[str, int]:
    init_db()

    channels = channels or get_channels()
    limit = limit_per_channel or settings.default_limit_per_channel
    stats = {
        "channels_total": len(channels),
        "channels_ok": 0,
        "channels_failed": 0,
        "posts_seen": 0,
        "posts_saved": 0,
        "posts_updated": 0,
        "posts_duplicates": 0,
        "posts_skipped": 0,
    }

    client = create_telegram_client()

    async with client:
        for channel_username in channels:
            channel_seen = 0
            channel_saved = 0
            logger.info("Collecting latest Telegram posts from @%s", channel_username)

            try:
                entity = await client.get_entity(channel_username)
                title = getattr(entity, "title", None)
                channel_skipped = 0
                channel_updated = 0

                with SessionLocal() as session:
                    source = get_or_create_source(session, channel_username, title=title)

                    async for message in client.iter_messages(entity, limit=limit):
                        channel_seen += 1
                        stats["posts_seen"] += 1

                        text = normalize_text(getattr(message, "message", "") or "")
                        if not is_meaningful_text(text):
                            stats["posts_skipped"] += 1
                            channel_skipped += 1
                            continue

                        save_result = save_or_update_post(
                            session,
                            source,
                            {
                                "telegram_message_id": message.id,
                                "message_date": ensure_utc(message.date),
                                "text": text,
                                "views": getattr(message, "views", None),
                                "forwards": getattr(message, "forwards", None),
                                "url": _message_url(channel_username, message.id),
                                "raw_json": _message_to_raw_json(message),
                            },
                        )

                        if save_result["created"]:
                            channel_saved += 1
                            stats["posts_saved"] += 1
                        elif save_result["updated"]:
                            channel_updated += 1
                            stats["posts_updated"] += 1
                        else:
                            stats["posts_duplicates"] += 1

                stats["channels_ok"] += 1
                logger.info(
                    "Finished @%s: seen=%s, saved=%s, updated=%s, duplicates=%s, skipped=%s",
                    channel_username,
                    channel_seen,
                    channel_saved,
                    channel_updated,
                    channel_seen - channel_saved - channel_updated - channel_skipped,
                    channel_skipped,
                )
            except (RPCError, ValueError, OSError, RuntimeError) as exc:
                stats["channels_failed"] += 1
                logger.exception("Failed to collect posts from @%s: %s", channel_username, exc)
                continue

    return stats
