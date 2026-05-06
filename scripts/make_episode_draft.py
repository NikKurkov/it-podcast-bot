import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.repositories.episodes import create_episode_draft
from app.db.repositories.posts import mark_posts_processed
from app.db.session import SessionLocal, init_db
from app.pipeline.daily_digest import build_digest_items, export_digest_json, export_digest_markdown
from app.pipeline.filters import filter_excluded_items, load_exclude_keywords


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a local episode draft from collected posts.")
    parser.add_argument("--title", default=None, help="Episode draft title.")
    parser.add_argument("--limit", type=int, default=10, help="How many posts to include.")
    parser.add_argument("--only-unprocessed", action="store_true")
    parser.add_argument("--ranked", action="store_true", default=True)
    parser.add_argument("--mark-processed", action="store_true")
    parser.add_argument("--use-exclude-keywords", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    init_db()

    title = args.title or f"IT digest {datetime.now(timezone.utc).date().isoformat()}"
    slug = _slug_from_datetime()
    markdown_path = Path("data/episodes") / f"{slug}.md"
    json_path = Path("data/episodes") / f"{slug}.json"

    with SessionLocal() as session:
        items = build_digest_items(
            session,
            limit=args.limit,
            only_unprocessed=args.only_unprocessed,
            ranked=args.ranked,
        )
        if args.use_exclude_keywords:
            items = filter_excluded_items(items, load_exclude_keywords())
        export_digest_markdown(items, markdown_path)
        export_digest_json(items, json_path)

        if args.mark_processed:
            mark_posts_processed(session, [item.post_id for item in items])

        episode = create_episode_draft(
            session,
            title=title,
            source_post_ids=[item.post_id for item in items],
            markdown_path=str(markdown_path),
            json_path=str(json_path),
        )

    print(f"Created episode draft #{episode.id}: {episode.title}")
    print(f"  posts: {len(items)}")
    print(f"  markdown: {markdown_path}")
    print(f"  json: {json_path}")


def _slug_from_datetime() -> str:
    return datetime.now(timezone.utc).strftime("episode_%Y%m%d_%H%M%S")


if __name__ == "__main__":
    main()
