import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.settings import settings
from app.db.repositories.posts import count_posts
from app.db.repositories.sources import count_sources
from app.db.session import SessionLocal, init_db
from app.telegram_reader.channels import get_channels
from app.telegram_reader.client import _build_proxy, create_telegram_client


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check local project setup.")
    parser.add_argument(
        "--telegram",
        action="store_true",
        help="Also connect to Telegram and check whether the saved session is authorized.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    init_db()

    channels = get_channels()
    proxy = _build_proxy()
    session_file = Path("data/sessions") / f"{settings.telegram_session_name}.session"

    print("Setup check:")
    print(f"  telegram_api_id: {'configured' if settings.telegram_api_id else 'missing'}")
    print(f"  telegram_api_hash: {'configured' if settings.telegram_api_hash else 'missing'}")
    print(f"  telegram_session_file: {'exists' if session_file.exists() else 'missing'}")
    print(f"  telegram_proxy: {_format_proxy(proxy)}")
    print(f"  channels: {len(channels)}")
    for channel in channels:
        print(f"    @{channel}")

    with SessionLocal() as session:
        print(f"  database_url: {settings.database_url}")
        print(f"  database_sources: {count_sources(session)}")
        print(f"  database_posts: {count_posts(session)}")

    if args.telegram:
        authorized = asyncio.run(_check_telegram_authorization())
        print(f"  telegram_authorized: {'yes' if authorized else 'no'}")


def _format_proxy(proxy: tuple | None) -> str:
    if not proxy:
        return "disabled"

    proxy_type, host, port, _, username, _ = proxy
    auth = " with auth" if username else ""
    return f"{proxy_type}://{host}:{port}{auth}"


async def _check_telegram_authorization() -> bool:
    client = create_telegram_client()
    await client.connect()
    try:
        return await client.is_user_authorized()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    main()
