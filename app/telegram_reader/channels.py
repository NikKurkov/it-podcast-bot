from app.config.settings import settings


CHANNELS = [
    "durov",
    "pythonetc",
]


def get_channels() -> list[str]:
    if settings.telegram_channels:
        return [
            channel.strip().lstrip("@")
            for channel in settings.telegram_channels.split(",")
            if channel.strip()
        ]

    return [channel.strip().lstrip("@") for channel in CHANNELS if channel.strip()]
