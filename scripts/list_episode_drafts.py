import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.repositories.episodes import get_latest_episode_drafts
from app.db.session import SessionLocal, init_db


def main() -> None:
    init_db()
    with SessionLocal() as session:
        episodes = get_latest_episode_drafts(session)

    if not episodes:
        print("No episode drafts found.")
        return

    for episode in episodes:
        post_ids = json.loads(episode.source_post_ids)
        print(f"[{episode.id}] {episode.title} ({episode.status})")
        print(f"  posts: {len(post_ids)}")
        print(f"  markdown: {episode.markdown_path}")
        print(f"  json: {episode.json_path}")
        print("")


if __name__ == "__main__":
    main()
