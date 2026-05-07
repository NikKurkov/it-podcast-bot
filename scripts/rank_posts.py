import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.repositories.posts import get_posts_for_digest
from app.db.session import SessionLocal, init_db
from app.pipeline.filters import contains_excluded_keyword, load_exclude_keywords
from app.pipeline.scoring import rank_posts, score_post_breakdown
from app.pipeline.source_weights import load_source_weights
from app.utils.text import shorten_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rank collected posts with a simple non-LLM heuristic.")
    parser.add_argument("--limit", type=int, default=20, help="How many latest posts to rank.")
    parser.add_argument("--top", type=int, default=10, help="How many ranked posts to show.")
    parser.add_argument("--channel", default=None, help="Filter by channel username.")
    parser.add_argument("--only-unprocessed", action="store_true")
    parser.add_argument("--use-exclude-keywords", action="store_true", default=True)
    parser.add_argument("--use-source-weights", action="store_true", default=True)
    parser.add_argument("--show-breakdown", action="store_true")
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
        if args.use_exclude_keywords:
            keywords = load_exclude_keywords()
            posts = [
                post
                for post in posts
                if not contains_excluded_keyword(post.text, keywords)
            ]
        source_weights = load_source_weights() if args.use_source_weights else {}
        ranked_posts = rank_posts(posts, source_weights=source_weights)[: args.top]

        if not ranked_posts:
            print("No posts found.")
            return

        for index, ranked_post in enumerate(ranked_posts, start=1):
            post = ranked_post.post
            source = post.source_channel.username
            print(f"{index}. score={ranked_post.score:.2f} @{source} #{post.telegram_message_id}")
            print(f"   {shorten_text(post.text, max_length=220)}")
            if ranked_post.reasons:
                print(f"   reasons: {', '.join(ranked_post.reasons)}")
            if ranked_post.penalties:
                print(f"   penalties: {', '.join(ranked_post.penalties)}")
            if ranked_post.topics:
                print(f"   topics: {', '.join(ranked_post.topics)}")
            if args.show_breakdown:
                breakdown = score_post_breakdown(post, source_weights=source_weights)
                print(
                    "   breakdown: "
                    f"engagement={breakdown.engagement:.2f}, "
                    f"freshness={breakdown.freshness:.2f}, "
                    f"length={breakdown.length:.2f}, "
                    f"it={breakdown.it_relevance:.2f}, "
                    f"investigation={breakdown.investigation_potential:.2f}, "
                    f"source={breakdown.source_weight:.2f}, "
                    f"penalty={breakdown.penalty:.2f}",
                )
            if post.url:
                print(f"   {post.url}")
            print("")


if __name__ == "__main__":
    main()
