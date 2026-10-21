import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.pipeline.episode_paths import resolve_episode_path

from app.config.settings import settings
from app.telegram_publisher.publisher import (
    build_episode_caption,
    prepare_publish_audio,
    publish_episode_package,
    validate_episode_for_publish,
)
from app.utils.logger import setup_logging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish an episode package audio to Telegram.")
    parser.add_argument(
        "--episode", default="latest", help="Episode directory name/path or latest."
    )
    parser.add_argument("--channel-id", default=settings.telegram_publish_channel_id)
    parser.add_argument(
        "--dry-run", action="store_true", help="Prepare audio and print caption without sending."
    )
    parser.add_argument(
        "--republish",
        action="store_true",
        help="Explicitly allow sending a published episode again.",
    )
    parser.add_argument(
        "--skip-quality-gate",
        action="store_true",
        help="Publish even if script quality checks report blocking issues.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging()
    episode_path = _resolve_episode_path(args.episode)
    issues = validate_episode_for_publish(episode_path)
    if issues and not args.skip_quality_gate:
        print("Episode is not ready to publish:")
        for issue in issues:
            print(f"  - {issue}")
        raise SystemExit(1)

    if args.dry_run:
        audio_path = prepare_publish_audio(episode_path)
        caption = build_episode_caption(episode_path)
        print("Telegram publish dry run:")
        print(f"  channel_id: {args.channel_id}")
        print(f"  audio: {audio_path}")
        print("  caption:")
        print(caption)
        return

    result = asyncio.run(
        publish_episode_package(episode_path, channel_id=args.channel_id, republish=args.republish),
    )

    print("Published episode to Telegram:")
    print(f"  channel_id: {result.channel_id}")
    print(f"  message_id: {result.message_id}")
    print(f"  audio: {result.audio_path}")


def _resolve_episode_path(value: str) -> Path:
    return resolve_episode_path(value, PROJECT_ROOT, required_file="audio.mp3")


if __name__ == "__main__":
    main()
