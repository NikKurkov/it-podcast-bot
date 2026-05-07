import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.repositories.posts import get_posts_for_digest, update_editorial_state
from app.db.session import SessionLocal, init_db
from app.pipeline.filters import contains_excluded_keyword, load_exclude_keywords
from app.pipeline.scoring import rank_posts
from app.pipeline.source_weights import load_source_weights
from app.utils.text import shorten_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automatically select top ranked posts for an episode.")
    parser.add_argument("--pool-limit", type=int, default=50)
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--category", default="top news")
    parser.add_argument("--reset-existing", action="store_true")
    parser.add_argument("--use-exclude-keywords", action="store_true", default=True)
    parser.add_argument("--use-source-weights", action="store_true", default=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    init_db()
    with SessionLocal() as session:
        if args.reset_existing:
            posts = get_posts_for_digest(session, limit=10_000, include_rejected=True)
            update_editorial_state(session, [post.id for post in posts], selected=False)

        posts = get_posts_for_digest(session, limit=args.pool_limit)
        source_weights = load_source_weights() if args.use_source_weights else {}
        ranked_posts = rank_posts(posts, source_weights=source_weights)
        if args.use_exclude_keywords:
            keywords = load_exclude_keywords()
            ranked_posts = [
                ranked_post
                for ranked_post in ranked_posts
                if not contains_excluded_keyword(ranked_post.post.text, keywords)
            ]

        selected_ranked_posts = ranked_posts[: args.top]
        selected_posts = [ranked_post.post for ranked_post in selected_ranked_posts]
        for ranked_post in selected_ranked_posts:
            update_editorial_state(
                session,
                [ranked_post.post.id],
                selected=True,
                category=args.category,
                editor_note=_build_editor_note(ranked_post),
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


def _build_editor_note(ranked_post) -> str:
    reasons = "; ".join(ranked_post.reasons[:3]) if ranked_post.reasons else "no strong reasons"
    topics = f" Topics: {', '.join(ranked_post.topics)}." if ranked_post.topics else ""
    penalties = (
        f" Penalties: {'; '.join(ranked_post.penalties[:2])}."
        if ranked_post.penalties
        else ""
    )
    return (
        f"Auto-selected by heuristic score={ranked_post.score:.2f}. "
        f"Reasons: {reasons}.{topics}{penalties}"
    )


if __name__ == "__main__":
    main()
