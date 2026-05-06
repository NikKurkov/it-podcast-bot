import json
import sys
from pathlib import Path

from sqlalchemy import func, select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.models import EpisodeDraft, SourceChannel, TelegramPost
from app.db.session import SessionLocal, init_db


def main() -> None:
    init_db()
    with SessionLocal() as session:
        duplicate_keys = session.execute(
            select(
                TelegramPost.source_channel_id,
                TelegramPost.telegram_message_id,
                func.count(TelegramPost.id),
            )
            .group_by(TelegramPost.source_channel_id, TelegramPost.telegram_message_id)
            .having(func.count(TelegramPost.id) > 1),
        ).all()
        empty_text_count = session.scalar(
            select(func.count(TelegramPost.id)).where(func.trim(TelegramPost.text) == ""),
        ) or 0
        orphan_count = session.scalar(
            select(func.count(TelegramPost.id))
            .join(SourceChannel, SourceChannel.id == TelegramPost.source_channel_id, isouter=True)
            .where(SourceChannel.id.is_(None)),
        ) or 0
        invalid_episode_count = 0
        missing_episode_file_count = 0
        for episode in session.scalars(select(EpisodeDraft)).all():
            try:
                post_ids = json.loads(episode.source_post_ids)
            except json.JSONDecodeError:
                invalid_episode_count += 1
                continue
            if not isinstance(post_ids, list):
                invalid_episode_count += 1
            for file_path in (episode.markdown_path, episode.json_path):
                if file_path and not Path(file_path).exists():
                    missing_episode_file_count += 1

    print("Database validation:")
    print(f"  duplicate_message_keys: {len(duplicate_keys)}")
    print(f"  empty_text_posts: {empty_text_count}")
    print(f"  orphan_posts: {orphan_count}")
    print(f"  invalid_episode_drafts: {invalid_episode_count}")
    print(f"  missing_episode_files: {missing_episode_file_count}")

    if (
        duplicate_keys
        or empty_text_count
        or orphan_count
        or invalid_episode_count
        or missing_episode_file_count
    ):
        raise SystemExit(1)

    print("  status: ok")


if __name__ == "__main__":
    main()
