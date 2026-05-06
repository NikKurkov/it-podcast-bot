from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories.posts import (
    count_posts,
    count_posts_by_source,
    count_unprocessed_posts,
    get_latest_posts,
    mark_posts_processed,
    save_post,
)
from app.db.repositories.sources import count_sources, get_or_create_source


def test_save_post_deduplicates_by_source_and_message_id() -> None:
    session_factory = _make_session_factory()
    with session_factory() as session:
        source = get_or_create_source(session, "durov", title="Durov")
        post_data = {
            "telegram_message_id": 1,
            "message_date": datetime(2026, 5, 6, tzinfo=timezone.utc),
            "text": " hello   world ",
            "views": 10,
            "forwards": 2,
            "url": "https://t.me/durov/1",
            "raw_json": "{}",
        }

        first_post = save_post(session, source, post_data)
        second_post = save_post(session, source, post_data)

        assert first_post is not None
        assert second_post is None
        assert count_posts(session) == 1
        assert count_unprocessed_posts(session) == 1


def test_repository_stats_and_latest_posts() -> None:
    session_factory = _make_session_factory()
    with session_factory() as session:
        source = get_or_create_source(session, "pythonetc", title="Python etc")
        save_post(
            session,
            source,
            {
                "telegram_message_id": 10,
                "message_date": datetime(2026, 5, 6, 10, tzinfo=timezone.utc),
                "text": "First",
            },
        )
        save_post(
            session,
            source,
            {
                "telegram_message_id": 11,
                "message_date": datetime(2026, 5, 6, 11, tzinfo=timezone.utc),
                "text": "Second",
            },
        )

        latest_posts = get_latest_posts(session, limit=1)

        assert count_sources(session) == 1
        assert count_posts_by_source(session) == [("pythonetc", "Python etc", 2)]
        assert latest_posts[0].telegram_message_id == 11


def test_mark_posts_processed() -> None:
    session_factory = _make_session_factory()
    with session_factory() as session:
        source = get_or_create_source(session, "durov")
        post = save_post(
            session,
            source,
            {
                "telegram_message_id": 1,
                "message_date": datetime(2026, 5, 6, tzinfo=timezone.utc),
                "text": "Process me",
            },
        )

        assert post is not None
        assert mark_posts_processed(session, [post.id]) == 1
        assert count_unprocessed_posts(session) == 0


def _make_session_factory() -> sessionmaker:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
