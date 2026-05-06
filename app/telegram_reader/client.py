from pathlib import Path
from urllib.parse import unquote, urlparse

from telethon import TelegramClient

from app.config.settings import settings


def _build_proxy() -> tuple | None:
    if not settings.telegram_proxy_url:
        return None

    parsed = urlparse(settings.telegram_proxy_url)
    scheme_to_proxy_type = {
        "socks4": "socks4",
        "socks5": "socks5",
    }
    proxy_type = scheme_to_proxy_type.get(parsed.scheme.lower())
    if proxy_type is None:
        raise RuntimeError(
            "Unsupported TELEGRAM_PROXY_URL scheme. Use socks4:// or socks5://.",
        )
    if not parsed.hostname or not parsed.port:
        raise RuntimeError("TELEGRAM_PROXY_URL must include host and port.")

    username = unquote(parsed.username) if parsed.username else None
    password = unquote(parsed.password) if parsed.password else None
    return (proxy_type, parsed.hostname, parsed.port, True, username, password)


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
        proxy=_build_proxy(),
    )
