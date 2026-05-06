import argparse
import sys
from datetime import datetime, time, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.repositories.posts import mark_posts_processed
from app.db.session import SessionLocal, init_db
from app.pipeline.daily_digest import (
    build_digest_items,
    export_digest_json,
    export_digest_markdown,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export collected posts into a simple digest file.")
    parser.add_argument("--limit", type=int, default=50, help="How many latest posts to export.")
    parser.add_argument("--channel", default=None, help="Filter by channel username.")
    parser.add_argument(
        "--only-unprocessed",
        action="store_true",
        help="Export only posts not marked as processed.",
    )
    parser.add_argument("--since", default=None, help="Start date or datetime, inclusive.")
    parser.add_argument("--until", default=None, help="End date or datetime, inclusive.")
    parser.add_argument("--min-views", type=int, default=None, help="Export posts with at least this many views.")
    parser.add_argument(
        "--min-forwards",
        type=int,
        default=None,
        help="Export posts with at least this many forwards.",
    )
    parser.add_argument("--contains", default=None, help="Export posts containing this text.")
    parser.add_argument("--exclude", default=None, help="Skip posts containing this text.")
    parser.add_argument(
        "--mark-processed",
        action="store_true",
        help="Mark exported posts as processed after successful export.",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output file path. Defaults to data/episodes/latest_digest.md or .json.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    init_db()
    output_path = Path(args.output) if args.output else _default_output_path(args.format)
    since = _parse_cli_datetime(args.since, end_of_day=False) if args.since else None
    until = _parse_cli_datetime(args.until, end_of_day=True) if args.until else None

    with SessionLocal() as session:
        items = build_digest_items(
            session,
            limit=args.limit,
            source_username=args.channel,
            only_unprocessed=args.only_unprocessed,
            since=since,
            until=until,
            min_views=args.min_views,
            min_forwards=args.min_forwards,
            contains=args.contains,
            exclude=args.exclude,
        )

        if args.format == "json":
            export_digest_json(items, output_path)
        else:
            export_digest_markdown(items, output_path)

        marked_count = mark_posts_processed(session, [item.post_id for item in items]) if args.mark_processed else 0

    print(f"Exported {len(items)} posts to {output_path}")
    if args.mark_processed:
        print(f"Marked {marked_count} posts as processed")


def _default_output_path(output_format: str) -> Path:
    suffix = "json" if output_format == "json" else "md"
    return Path("data/episodes") / f"latest_digest.{suffix}"


def _parse_cli_datetime(value: str, end_of_day: bool) -> datetime:
    parsed_date: datetime
    if "T" in value or " " in value:
        parsed_date = datetime.fromisoformat(value)
    else:
        parsed_date = datetime.combine(datetime.fromisoformat(value).date(), time.max if end_of_day else time.min)

    if parsed_date.tzinfo is None:
        return parsed_date.replace(tzinfo=timezone.utc)

    return parsed_date.astimezone(timezone.utc)


if __name__ == "__main__":
    main()
