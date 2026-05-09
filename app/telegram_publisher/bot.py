from telethon import TelegramClient

from app.telegram_reader.client import create_telegram_client


def create_publisher_client() -> TelegramClient:
    """Create a Telethon client for publishing through the user account session."""
    return create_telegram_client()
