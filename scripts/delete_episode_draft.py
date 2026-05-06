import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.repositories.episodes import delete_episode_draft
from app.db.session import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Delete an episode draft and optionally its files.")
    parser.add_argument("episode_id", type=int)
    parser.add_argument("--keep-files", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    init_db()

    with SessionLocal() as session:
        episode = delete_episode_draft(session, args.episode_id)

    if episode is None:
        raise SystemExit("Episode draft not found.")

    deleted_files = []
    if not args.keep_files:
        for file_path in (episode.markdown_path, episode.json_path):
            if not file_path:
                continue
            path = Path(file_path)
            if path.exists():
                path.unlink()
                deleted_files.append(str(path))

    print(f"Deleted episode draft #{episode.id}: {episode.title}")
    for file_path in deleted_files:
        print(f"  deleted file: {file_path}")


if __name__ == "__main__":
    main()
