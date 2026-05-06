import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.repositories.posts import update_editorial_state
from app.db.session import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Set editorial state for collected posts.")
    parser.add_argument("--id", type=int, action="append", required=True, help="Post id. Can be repeated.")

    state_group = parser.add_mutually_exclusive_group()
    state_group.add_argument("--select", action="store_true")
    state_group.add_argument("--reject", action="store_true")
    state_group.add_argument("--reset-state", action="store_true")

    parser.add_argument("--category", default=None)
    parser.add_argument("--note", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    selected = True if args.select else False if args.reset_state else None
    rejected = True if args.reject else False if args.reset_state else None

    init_db()
    with SessionLocal() as session:
        changed_count = update_editorial_state(
            session,
            args.id,
            selected=selected,
            rejected=rejected,
            category=args.category,
            editor_note=args.note,
        )

    print(f"Updated {changed_count} posts")


if __name__ == "__main__":
    main()
