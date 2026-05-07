from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories.posts import save_post
from app.db.repositories.sources import get_or_create_source
from app.pipeline.scoring import detect_topics, rank_posts, score_post, score_post_breakdown


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


def test_score_post_breakdown_rewards_it_relevance() -> None:
    session_factory = _make_session_factory()
    now = datetime(2026, 5, 6, 12, tzinfo=timezone.utc)

    with session_factory() as session:
        source = get_or_create_source(session, "xakep_ru")
        post = save_post(
            session,
            source,
            {
                "telegram_message_id": 1,
                "message_date": now,
                "text": "Security release fixes Python API vulnerability in production infrastructure",
                "views": 100,
                "forwards": 5,
            },
        )

        breakdown = score_post_breakdown(post, now=now)

        assert breakdown.it_relevance > 0
        assert breakdown.investigation_potential > 0
        assert breakdown.reasons


def test_score_post_breakdown_penalizes_low_signal_wording() -> None:
    session_factory = _make_session_factory()
    now = datetime(2026, 5, 6, 12, tzinfo=timezone.utc)

    with session_factory() as session:
        source = get_or_create_source(session, "promo")
        post = save_post(
            session,
            source,
            {
                "telegram_message_id": 1,
                "message_date": now,
                "text": "Срочно забираем скидку, жми тут и сохраняем себе",
                "views": 100,
                "forwards": 5,
            },
        )

        breakdown = score_post_breakdown(post, now=now)

        assert breakdown.penalty > 0
        assert breakdown.penalties


def test_score_post_breakdown_penalizes_non_it_text() -> None:
    session_factory = _make_session_factory()
    now = datetime(2026, 5, 6, 12, tzinfo=timezone.utc)

    with session_factory() as session:
        source = get_or_create_source(session, "general")
        post = save_post(
            session,
            source,
            {
                "telegram_message_id": 1,
                "message_date": now,
                "text": "Большой трейлер нового фильма выходит летом",
                "views": 100,
                "forwards": 5,
            },
        )

        breakdown = score_post_breakdown(post, now=now)

        assert breakdown.penalty >= 4
        assert "no IT or investigation signals" in breakdown.penalties


def test_score_post_breakdown_uses_source_weights() -> None:
    session_factory = _make_session_factory()
    now = datetime(2026, 5, 6, 12, tzinfo=timezone.utc)

    with session_factory() as session:
        source = get_or_create_source(session, "trusted")
        post = save_post(
            session,
            source,
            {
                "telegram_message_id": 1,
                "message_date": now,
                "text": "Python API release for production infrastructure",
                "views": 100,
                "forwards": 5,
            },
        )

        breakdown = score_post_breakdown(post, now=now, source_weights={"trusted": 1.25})

        assert breakdown.source_weight == 1.0
        assert "source boost: +1.00" in breakdown.reasons


def test_detect_topics() -> None:
    assert detect_topics("Claude LLM security incident in production infrastructure") == [
        "ai",
        "security",
        "devops",
    ]


def _make_session_factory() -> sessionmaker:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
