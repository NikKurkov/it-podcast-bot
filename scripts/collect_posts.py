import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.telegram_reader.collector import collect_latest_posts
from app.utils.logger import setup_logging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect latest posts from Telegram channels.")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="How many latest messages to read per channel.",
    )
    parser.add_argument(
        "--channel",
        action="append",
        default=None,
        help="Collect only this channel. Can be passed multiple times.",
    )
    return parser.parse_args()


def print_stats(stats: dict[str, int]) -> None:
    print("\nCollection stats:")
    for key, value in stats.items():
        print(f"  {key}: {value}")


def main() -> None:
    args = parse_args()
    setup_logging()
    channels = [channel.strip().lstrip("@") for channel in args.channel] if args.channel else None
    stats = asyncio.run(collect_latest_posts(limit_per_channel=args.limit, channels=channels))
    print_stats(stats)


if __name__ == "__main__":
    main()
