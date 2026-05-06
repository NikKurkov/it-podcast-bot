import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.repositories.posts import get_posts_for_digest
from app.db.session import SessionLocal, init_db
from app.pipeline.scoring import rank_posts
from app.utils.text import shorten_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rank collected posts with a simple non-LLM heuristic.")
    parser.add_argument("--limit", type=int, default=20, help="How many latest posts to rank.")
    parser.add_argument("--top", type=int, default=10, help="How many ranked posts to show.")
    parser.add_argument("--channel", default=None, help="Filter by channel username.")
    parser.add_argument("--only-unprocessed", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    init_db()
    with SessionLocal() as session:
        posts = get_posts_for_digest(
            session,
            limit=args.limit,
            source_username=args.channel,
            only_unprocessed=args.only_unprocessed,
        )
        ranked_posts = rank_posts(posts)[: args.top]

        if not ranked_posts:
            print("No posts found.")
            return

        for index, ranked_post in enumerate(ranked_posts, start=1):
            post = ranked_post.post
            source = post.source_channel.username
            print(f"{index}. score={ranked_post.score:.2f} @{source} #{post.telegram_message_id}")
            print(f"   {shorten_text(post.text, max_length=220)}")
            if post.url:
                print(f"   {post.url}")
            print("")


if __name__ == "__main__":
    main()
