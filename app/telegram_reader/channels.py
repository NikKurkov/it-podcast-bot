from pathlib import Path

from app.config.settings import settings


def _clean_channel(value: str) -> str:
    return value.strip().lstrip("@")


def _parse_channels(value: str) -> list[str]:
    channels: list[str] = []
    for raw_line in value.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue

        for item in line.split(","):
            channel = _clean_channel(item)
            if channel:
                channels.append(channel)

    return _deduplicate_channels(channels)


def _read_channels_file(path: str) -> list[str]:
    channels_path = Path(path)
    if not channels_path.exists():
        return []

    return _parse_channels(channels_path.read_text(encoding="utf-8"))


def get_channels() -> list[str]:
    if settings.telegram_channels:
        return _parse_channels(settings.telegram_channels)

    return _read_channels_file(settings.telegram_channels_file)


def _deduplicate_channels(channels: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for channel in channels:
        if channel in seen:
            continue
        seen.add(channel)
        result.append(channel)

    return result
