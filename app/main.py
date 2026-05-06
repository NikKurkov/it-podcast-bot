import asyncio

from app.telegram_reader.collector import collect_latest_posts
from app.utils.logger import setup_logging


def main() -> None:
    setup_logging()
    stats = asyncio.run(collect_latest_posts())
    print(stats)


if __name__ == "__main__":
    main()
