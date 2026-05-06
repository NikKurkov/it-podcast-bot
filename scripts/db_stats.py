import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.repositories.posts import count_posts, count_posts_by_source, count_unprocessed_posts
from app.db.repositories.sources import count_sources
from app.db.session import SessionLocal, init_db


def main() -> None:
    init_db()
    with SessionLocal() as session:
        print("Database stats:")
        print(f"  sources: {count_sources(session)}")
        print(f"  posts: {count_posts(session)}")
        print(f"  unprocessed_posts: {count_unprocessed_posts(session)}")
        print("")
        print("Posts by source:")
        for username, title, posts_count in count_posts_by_source(session):
            label = f"@{username}"
            if title:
                label = f"{label} ({title})"
            print(f"  {label}: {posts_count}")


if __name__ == "__main__":
    main()
