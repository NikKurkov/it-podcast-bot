from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories.posts import save_post
from app.db.repositories.sources import get_or_create_source
from app.pipeline.scoring import (
    diversify_ranked_posts,
    is_podcast_candidate,
    rank_posts,
    score_post,
    score_post_breakdown,
)


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


def test_consumer_auto_keyword_does_not_match_automation() -> None:
    session_factory = _make_session_factory()
    now = datetime(2026, 5, 20, 12, tzinfo=timezone.utc)

    with session_factory() as session:
        source = get_or_create_source(session, "dev_tools")
        post = save_post(
            session,
            source,
            {
                "telegram_message_id": 1,
                "message_date": now,
                "text": "Anthropic выпустила курсы по Claude Code и MCP для автоматизации задач ИИ-разработки",
                "views": 30000,
                "forwards": 250,
            },
        )
        assert post is not None

        ranked = rank_posts([post], now=now)[0]

        assert is_podcast_candidate(ranked) is True
        assert not any("consumer topic" in item for item in ranked.penalties)


def test_consumer_auto_keyword_does_not_match_autonomous_agent_work() -> None:
    session_factory = _make_session_factory()
    now = datetime(2026, 5, 22, 12, tzinfo=timezone.utc)

    with session_factory() as session:
        source = get_or_create_source(session, "ai_models")
        post = save_post(
            session,
            source,
            {
                "telegram_message_id": 1,
                "message_date": now,
                "text": (
                    "Alibaba выпустила Qwen3.7-Max: модель пишет код, выполняет агентские задачи "
                    "и может автономно работать дольше часа."
                ),
                "views": 30000,
                "forwards": 250,
            },
        )
        assert post is not None

        ranked = rank_posts([post], now=now)[0]

        assert is_podcast_candidate(ranked) is True
        assert not any("consumer topic" in item for item in ranked.penalties)


def test_is_podcast_candidate_keeps_real_code_security_story() -> None:
    session_factory = _make_session_factory()
    now = datetime(2026, 5, 20, 12, tzinfo=timezone.utc)

    with session_factory() as session:
        source = get_or_create_source(session, "dev_tools")
        post = save_post(
            session,
            source,
            {
                "telegram_message_id": 1,
                "message_date": now,
                "text": (
                    "GitHub расследует взлом репозиториев: заражённое расширение VS Code "
                    "утекло исходным кодом и токенами доступа."
                ),
                "views": 100000,
                "forwards": 500,
            },
        )
        assert post is not None

        ranked = rank_posts([post], now=now)[0]

        assert is_podcast_candidate(ranked) is True
        assert not any("weak code context" in item for item in ranked.penalties)


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


def test_diversify_ranked_posts_keeps_distinct_claude_tool_stories() -> None:
    session_factory = _make_session_factory()
    now = datetime(2026, 5, 20, 12, tzinfo=timezone.utc)

    with session_factory() as session:
        source_a = get_or_create_source(session, "source_a")
        source_b = get_or_create_source(session, "source_b")
        course_post = save_post(
            session,
            source_a,
            {
                "telegram_message_id": 1,
                "message_date": now,
                "text": (
                    "Anthropic выпустила библиотеку курсов по Claude Code, MCP "
                    "и навыкам ИИ-разработки для автоматизации рабочих задач."
                ),
                "views": 10000,
                "forwards": 100,
            },
        )
        cursor_post = save_post(
            session,
            source_b,
            {
                "telegram_message_id": 2,
                "message_date": now,
                "text": (
                    "Cursor выпустил Composer 2.5: модель пишет код на уровне Claude Opus "
                    "и лучше работает над долгими задачами."
                ),
                "views": 9000,
                "forwards": 90,
            },
        )

        assert course_post is not None
        assert cursor_post is not None
        ranked_posts = rank_posts([course_post, cursor_post], now=now)
        selected = diversify_ranked_posts(ranked_posts, limit=2)

        assert len(selected) == 2


def _make_session_factory() -> sessionmaker:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def test_exact_dedup_preserves_negations_numbers_symbols_and_order():
    from app.pipeline.scoring import is_similar_to_any_text

    original = "The upcoming product release supports C++ and needs 16 GB of memory."
    for changed in (
        original.replace("supports", "does not support"),
        original.replace("16", "32"),
        original.replace("C++", "C#"),
        " ".join(reversed(original.split())),
    ):
        assert not is_similar_to_any_text(changed, [original])
    assert is_similar_to_any_text("  " + original.replace(" ", "\n") + "  ", [original])
