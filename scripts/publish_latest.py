import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.settings import settings
from app.telegram_publisher.publisher import publish_episode_package
from app.utils.logger import setup_logging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish an episode package audio to Telegram.")
    parser.add_argument("--episode", default="latest", help="Episode directory name/path or latest.")
    parser.add_argument("--channel-id", default=settings.telegram_publish_channel_id)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging()
    episode_path = _resolve_episode_path(args.episode)
    result = asyncio.run(publish_episode_package(episode_path, channel_id=args.channel_id))

    print("Published episode to Telegram:")
    print(f"  channel_id: {result.channel_id}")
    print(f"  message_id: {result.message_id}")
    print(f"  audio: {result.audio_path}")


def _resolve_episode_path(value: str) -> Path:
    if value == "latest":
        episodes_dir = Path("data/episodes")
        if not episodes_dir.exists():
            raise SystemExit("No episode packages found in data/episodes.")
        candidates = [
            path
            for path in episodes_dir.iterdir()
            if path.is_dir() and (path / "audio.mp3").exists()
        ]
        if not candidates:
            raise SystemExit("No episode packages with audio.mp3 found in data/episodes.")
        return max(candidates, key=lambda path: path.stat().st_mtime)

    path = Path(value)
    if path.exists():
        return path

    return Path("data/episodes") / value


if __name__ == "__main__":
    main()
