import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.repositories.posts import get_post_by_id, get_post_by_source_message_id
from app.db.session import SessionLocal, init_db
from app.pipeline.scoring import score_post


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show full collected post by local id or channel/message id.")
    parser.add_argument("--id", type=int, default=None, help="Local database post id.")
    parser.add_argument("--channel", default=None, help="Telegram channel username.")
    parser.add_argument("--message-id", type=int, default=None, help="Telegram message id.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.id is None and not (args.channel and args.message_id):
        raise SystemExit("Pass --id or both --channel and --message-id.")

    init_db()
    with SessionLocal() as session:
        if args.id is not None:
            post = get_post_by_id(session, args.id)
        else:
            post = get_post_by_source_message_id(session, args.channel, args.message_id)

        if not post:
            raise SystemExit("Post not found.")

        print(f"Post #{post.id}")
        print(f"  source: @{post.source_channel.username}")
        print(f"  title: {post.source_channel.title}")
        print(f"  telegram_message_id: {post.telegram_message_id}")
        print(f"  message_date: {post.message_date.isoformat()}")
        print(f"  views: {post.views}")
        print(f"  forwards: {post.forwards}")
        print(f"  score: {score_post(post):.2f}")
        print(f"  processed: {post.is_processed}")
        print(f"  selected: {post.is_selected}")
        print(f"  rejected: {post.is_rejected}")
        print(f"  category: {post.category}")
        print(f"  editor_note: {post.editor_note}")
        print(f"  url: {post.url}")
        print("")
        print(post.text)


if __name__ == "__main__":
    main()
