import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.repositories.posts import get_selected_posts
from app.db.session import SessionLocal, init_db
from app.pipeline.script_draft import export_script_markdown


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a simple podcast script draft from selected posts.")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--title", default=None)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    init_db()
    title = args.title or f"IT podcast script {datetime.now(timezone.utc).date().isoformat()}"
    output_path = Path(args.output) if args.output else Path("data/episodes/latest_script.md")

    with SessionLocal() as session:
        posts = get_selected_posts(session, limit=args.limit)

    export_script_markdown(posts, output_path, title)
    print(f"Exported script draft with {len(posts)} posts to {output_path}")


if __name__ == "__main__":
    main()
