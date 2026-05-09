from pathlib import Path

from app.telegram_publisher.publisher import TelegramPublishResult, publish_episode_package


async def publish_episode(package_path: Path, channel_id: str | None = None) -> TelegramPublishResult:
    return await publish_episode_package(package_path, channel_id=channel_id)
