import argparse
import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.repositories.posts import get_posts_for_digest
from app.db.session import SessionLocal, init_db
from app.pipeline.scoring import score_post


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export collected posts to CSV.")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--channel", default=None)
    parser.add_argument("--output", default="data/raw/posts_export.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    init_db()
    with SessionLocal() as session:
        posts = get_posts_for_digest(session, limit=args.limit, source_username=args.channel)

        with output_path.open("w", encoding="utf-8", newline="") as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=[
                    "id",
                    "source",
                    "telegram_message_id",
                    "message_date",
                    "views",
                    "forwards",
                    "score",
                    "url",
                    "text",
                ],
            )
            writer.writeheader()
            for post in posts:
                writer.writerow(
                    {
                        "id": post.id,
                        "source": post.source_channel.username,
                        "telegram_message_id": post.telegram_message_id,
                        "message_date": post.message_date.isoformat(),
                        "views": post.views,
                        "forwards": post.forwards,
                        "score": score_post(post),
                        "url": post.url,
                        "text": post.text,
                    },
                )

    print(f"Exported {len(posts)} posts to {output_path}")


if __name__ == "__main__":
    main()
