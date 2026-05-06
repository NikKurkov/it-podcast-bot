from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories.episodes import (
    create_episode_draft,
    delete_episode_draft,
    get_latest_episode_drafts,
)


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


def _make_session_factory() -> sessionmaker:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
