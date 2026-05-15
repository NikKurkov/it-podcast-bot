from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories.episodes import (
    create_episode_draft,
    delete_episode_draft,
    get_episode_by_slug,
    get_latest_episode_drafts,
    get_recent_episode_post_ids,
    mark_episode_published,
    record_episode_package,
)
from app.db.repositories.posts import save_post
from app.db.repositories.sources import get_or_create_source


def test_create_episode_draft() -> None:
    session_factory = _make_session_factory()
    with session_factory() as session:
        episode = create_episode_draft(
            session,
            title="Test episode",
            source_post_ids=[1, 2, 3],
            markdown_path="data/episodes/test.md",
            json_path="data/episodes/test.json",
        )

        episodes = get_latest_episode_drafts(session)

        assert episode.id is not None
        assert episodes[0].title == "Test episode"
        assert episodes[0].source_post_ids == "[1, 2, 3]"


def test_delete_episode_draft() -> None:
    session_factory = _make_session_factory()
    with session_factory() as session:
        episode = create_episode_draft(session, title="Delete me", source_post_ids=[1])

        deleted_episode = delete_episode_draft(session, episode.id)

        assert deleted_episode is not None
        assert get_latest_episode_drafts(session) == []


def test_record_episode_package_tracks_posts_in_order() -> None:
    session_factory = _make_session_factory()
    with session_factory() as session:
        source = get_or_create_source(session, "durov")
        first_post = save_post(session, source, _post_data(1, "First story"))
        second_post = save_post(session, source, _post_data(2, "Second story"))

        episode = record_episode_package(
            session,
            slug="2026-05-10_070000",
            title="Morning episode",
            package_path="data/episodes/2026-05-10_070000",
            post_ids=[first_post.id, second_post.id],
            audio_path="data/episodes/2026-05-10_070000/audio.mp3",
            metadata_path="data/episodes/2026-05-10_070000/metadata.json",
        )

        assert episode.status == "completed"
        assert [link.telegram_post_id for link in episode.posts] == [first_post.id, second_post.id]
        assert get_recent_episode_post_ids(session, limit=1) == {first_post.id, second_post.id}


def test_record_episode_package_replaces_existing_post_links() -> None:
    session_factory = _make_session_factory()
    with session_factory() as session:
        source = get_or_create_source(session, "durov")
        first_post = save_post(session, source, _post_data(1, "First story"))
        second_post = save_post(session, source, _post_data(2, "Second story"))

        record_episode_package(
            session,
            slug="same-slug",
            title="First",
            package_path="data/episodes/same-slug",
            post_ids=[first_post.id],
        )
        record_episode_package(
            session,
            slug="same-slug",
            title="Second",
            package_path="data/episodes/same-slug",
            post_ids=[second_post.id],
        )

        episode = get_episode_by_slug(session, "same-slug")

        assert episode is not None
        assert episode.title == "Second"
        assert [link.telegram_post_id for link in episode.posts] == [second_post.id]


def test_mark_episode_published_updates_channel_metadata() -> None:
    session_factory = _make_session_factory()
    with session_factory() as session:
        episode = record_episode_package(
            session,
            slug="publish-me",
            title="Publish me",
            package_path="data/episodes/publish-me",
            post_ids=[],
            audio_path="data/episodes/publish-me/audio.mp3",
        )

        published_episode = mark_episode_published(
            session,
            slug=episode.slug,
            channel_id="-1001",
            message_id=42,
        )

        assert published_episode is not None
        assert published_episode.status == "published"
        assert published_episode.telegram_channel_id == "-1001"
        assert published_episode.telegram_message_id == 42
        assert published_episode.published_at is not None


def _make_session_factory() -> sessionmaker:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def _post_data(message_id: int, text: str) -> dict:
    from datetime import datetime, timezone

    return {
        "telegram_message_id": message_id,
        "message_date": datetime(2026, 5, 10, tzinfo=timezone.utc),
        "text": text,
        "url": f"https://t.me/durov/{message_id}",
    }
