import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.repositories.posts import get_latest_posts
from app.db.session import SessionLocal, init_db
from app.utils.text import shorten_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="List latest collected Telegram posts.")
    parser.add_argument("--limit", type=int, default=20, help="How many posts to show.")
    parser.add_argument("--channel", default=None, help="Filter by channel username.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    init_db()
    with SessionLocal() as session:
        posts = get_latest_posts(session, limit=args.limit, source_username=args.channel)
        if not posts:
            print("No posts found.")
            return

        for post in posts:
            source = post.source_channel.username
            date_text = post.message_date.isoformat(timespec="minutes")
            print(f"[{post.id}] @{source} #{post.telegram_message_id} {date_text}")
            print(f"  {shorten_text(post.text, max_length=220)}")
            if post.url:
                print(f"  {post.url}")
            print("")


if __name__ == "__main__":
    main()
