from pathlib import Path

from telethon import TelegramClient

from app.config.settings import settings


def create_telegram_client() -> TelegramClient:
    if not settings.telegram_api_id or not settings.telegram_api_hash:
        raise RuntimeError(
            "Telegram credentials are not configured. "
            "Set TELEGRAM_API_ID and TELEGRAM_API_HASH in .env.",
        )

    session_dir = Path("data/sessions")
    session_dir.mkdir(parents=True, exist_ok=True)
    session_path = session_dir / settings.telegram_session_name

    return TelegramClient(
        str(session_path),
        settings.telegram_api_id,
        settings.telegram_api_hash,
    )
