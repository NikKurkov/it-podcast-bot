from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories.posts import save_post
from app.db.repositories.sources import get_or_create_source
from app.pipeline.scoring import rank_posts, score_post


def test_score_post_prefers_posts_with_more_engagement() -> None:
    session_factory = _make_session_factory()
    now = datetime(2026, 5, 6, 12, tzinfo=timezone.utc)

    with session_factory() as session:
        source = get_or_create_source(session, "pythonetc")
        low_post = save_post(
            session,
            source,
            {
                "telegram_message_id": 1,
                "message_date": now,
                "text": "Short but valid news text",
                "views": 10,
                "forwards": 1,
            },
        )
        high_post = save_post(
            session,
            source,
            {
                "telegram_message_id": 2,
                "message_date": now,
                "text": "Long enough post text with much stronger engagement signals",
                "views": 10000,
                "forwards": 100,
            },
        )

        assert low_post is not None
        assert high_post is not None
        assert score_post(high_post, now=now) > score_post(low_post, now=now)


def test_rank_posts_orders_by_score() -> None:
    session_factory = _make_session_factory()
    now = datetime(2026, 5, 6, 12, tzinfo=timezone.utc)

    with session_factory() as session:
        source = get_or_create_source(session, "durov")
        older_post = save_post(
            session,
            source,
            {
                "telegram_message_id": 1,
                "message_date": now - timedelta(days=2),
                "text": "Old post",
                "views": 10,
                "forwards": 1,
            },
        )
        fresh_post = save_post(
            session,
            source,
            {
                "telegram_message_id": 2,
                "message_date": now,
                "text": "Fresh and much more important post",
                "views": 5000,
                "forwards": 50,
            },
        )

        assert older_post is not None
        assert fresh_post is not None
        ranked_posts = rank_posts([older_post, fresh_post], now=now)
        assert ranked_posts[0].post.telegram_message_id == 2


def _make_session_factory() -> sessionmaker:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
