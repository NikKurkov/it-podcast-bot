import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.settings import settings
from app.telegram_reader.channels import _clean_channel, _parse_channels, get_channels


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage local Telegram channel config.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="Show configured channels.")

    add_parser = subparsers.add_parser("add", help="Add channel to config file.")
    add_parser.add_argument("channel")

    remove_parser = subparsers.add_parser("remove", help="Remove channel from config file.")
    remove_parser.add_argument("channel")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    channels_file = Path(settings.telegram_channels_file)

    if args.command == "list":
        _print_channels(get_channels())
        return

    channels = _read_channels_for_edit(channels_file)
    if args.command == "add":
        channel = _clean_channel(args.channel)
        if channel not in channels:
            channels.append(channel)
            _write_channels(channels_file, channels)
        _print_channels(channels)
        return

    if args.command == "remove":
        channel = _clean_channel(args.channel)
        channels = [existing_channel for existing_channel in channels if existing_channel != channel]
        _write_channels(channels_file, channels)
        _print_channels(channels)


def _read_channels_for_edit(path: Path) -> list[str]:
    if not path.exists():
        return []

    return _parse_channels(path.read_text(encoding="utf-8"))


def _write_channels(path: Path, channels: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(channels).strip()
    path.write_text(f"{content}\n" if content else "", encoding="utf-8")


def _print_channels(channels: list[str]) -> None:
    if not channels:
        print("No channels configured.")
        return

    print("Configured channels:")
    for channel in channels:
        print(f"  @{channel}")


if __name__ == "__main__":
    main()
