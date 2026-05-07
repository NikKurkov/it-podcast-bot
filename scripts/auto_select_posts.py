import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.repositories.posts import get_posts_for_digest, update_editorial_state
from app.db.session import SessionLocal, init_db
from app.pipeline.filters import filter_excluded_items, load_exclude_keywords
from app.pipeline.scoring import rank_posts
from app.utils.text import shorten_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automatically select top ranked posts for an episode.")
    parser.add_argument("--pool-limit", type=int, default=50)
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--category", default="top news")
    parser.add_argument("--reset-existing", action="store_true")
    parser.add_argument("--use-exclude-keywords", action="store_true", default=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    init_db()
    with SessionLocal() as session:
        if args.reset_existing:
            posts = get_posts_for_digest(session, limit=10_000, include_rejected=True)
            update_editorial_state(session, [post.id for post in posts], selected=False)

        posts = get_posts_for_digest(session, limit=args.pool_limit)
        ranked_posts = [ranked_post.post for ranked_post in rank_posts(posts)]
        if args.use_exclude_keywords:
            ranked_posts = filter_excluded_items(ranked_posts, load_exclude_keywords())

        selected_posts = ranked_posts[: args.top]
        update_editorial_state(
            session,
            [post.id for post in selected_posts],
            selected=True,
            category=args.category,
            editor_note="Auto-selected by heuristic score",
        )
        output_rows = [
            (
                post.id,
                post.source_channel.username,
                post.telegram_message_id,
                shorten_text(post.text, max_length=180),
            )
            for post in selected_posts
        ]

    print(f"Selected {len(selected_posts)} posts:")
    for post_id, source, message_id, text in output_rows:
        print(f"  [{post_id}] @{source} #{message_id}")
        print(f"    {text}")


if __name__ == "__main__":
    main()
