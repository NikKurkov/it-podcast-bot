import argparse
import asyncio
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
from app.telegram_reader.collector import collect_latest_posts
from app.utils.logger import setup_logging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local daily MVP pipeline.")
    parser.add_argument("--collect-limit", type=int, default=20)
    parser.add_argument("--digest-limit", type=int, default=10)
    parser.add_argument("--use-exclude-keywords", action="store_true", default=True)
    parser.add_argument("--mark-processed", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging()
    init_db()

    collect_stats = asyncio.run(collect_latest_posts(limit_per_channel=args.collect_limit))
    slug = datetime.now(timezone.utc).strftime("daily_%Y%m%d_%H%M%S")
    markdown_path = Path("data/episodes") / f"{slug}.md"
    json_path = Path("data/episodes") / f"{slug}.json"

    with SessionLocal() as session:
        items = build_digest_items(
            session,
            limit=args.digest_limit,
            only_unprocessed=True,
            ranked=True,
        )
        if args.use_exclude_keywords:
            items = filter_excluded_items(items, load_exclude_keywords())

        export_digest_markdown(items, markdown_path)
        export_digest_json(items, json_path)

        if args.mark_processed:
            mark_posts_processed(session, [item.post_id for item in items])

        episode = create_episode_draft(
            session,
            title=f"IT digest {datetime.now(timezone.utc).date().isoformat()}",
            source_post_ids=[item.post_id for item in items],
            markdown_path=str(markdown_path),
            json_path=str(json_path),
        )

    print("Daily run complete:")
    for key, value in collect_stats.items():
        print(f"  {key}: {value}")
    print(f"  episode_draft_id: {episode.id}")
    print(f"  digest_posts: {len(items)}")
    print(f"  markdown: {markdown_path}")
    print(f"  json: {json_path}")


if __name__ == "__main__":
    main()
