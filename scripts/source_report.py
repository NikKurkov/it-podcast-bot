import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.repositories.posts import get_source_report
from app.db.session import SessionLocal, init_db


def main() -> None:
    init_db()
    with SessionLocal() as session:
        rows = get_source_report(session)

    if not rows:
        print("No sources found.")
        return

    print("Source report:")
    for row in rows:
        latest_date = row["latest_message_date"].isoformat(timespec="minutes") if row["latest_message_date"] else "-"
        avg_views = int(row["avg_views"]) if row["avg_views"] is not None else 0
        avg_forwards = int(row["avg_forwards"]) if row["avg_forwards"] is not None else 0
        title = f" ({row['title']})" if row["title"] else ""
        print(f"  @{row['username']}{title}")
        print(f"    posts: {row['posts_count']}")
        print(f"    latest: {latest_date}")
        print(f"    avg_views: {avg_views}")
        print(f"    avg_forwards: {avg_forwards}")


if __name__ == "__main__":
    main()
