import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.repositories.posts import mark_posts_processed, mark_posts_unprocessed
from app.db.session import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mark collected posts as processed or unprocessed.")
    parser.add_argument("state", choices=("processed", "unprocessed"))
    parser.add_argument("--id", type=int, action="append", default=None, help="Post id. Can be repeated.")
    parser.add_argument("--all", action="store_true", help="Apply to all posts.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.all and not args.id:
        raise SystemExit("Pass --id at least once or use --all.")

    init_db()
    with SessionLocal() as session:
        if args.state == "processed":
            changed_count = mark_posts_processed(session, args.id or [])
        else:
            changed_count = mark_posts_unprocessed(session, None if args.all else args.id)

    print(f"Marked {changed_count} posts as {args.state}")


if __name__ == "__main__":
    main()
