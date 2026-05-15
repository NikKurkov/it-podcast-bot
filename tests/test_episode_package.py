from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories.episodes import get_episode_by_slug
from app.db.repositories.posts import save_post, update_editorial_state
from app.db.repositories.sources import get_or_create_source
from app.pipeline.episode_package import create_episode_package


def test_create_episode_package_without_llm(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    session_factory = _make_session_factory()

    with session_factory() as session:
        source = get_or_create_source(session, "durov")
        post = save_post(
            session,
            source,
            {
                "telegram_message_id": 1,
                "message_date": datetime(2026, 5, 7, tzinfo=timezone.utc),
                "text": "Selected package story",
                "url": "https://t.me/durov/1",
            },
        )
        assert post is not None
        post_id = post.id
        update_editorial_state(session, [post.id], selected=True, category="top news")

        package = create_episode_package(
            session,
            limit=10,
            title="Test package",
            slug="test-package",
        )
        episode = get_episode_by_slug(session, "test-package")

    assert package.path.exists()
    assert package.digest_markdown_path.exists()
    assert package.selected_posts_path.exists()
    assert package.script_draft_path.exists()
    assert package.metadata_path.exists()
    assert package.audio_mp3_path is None
    assert package.audio_voice_wav_path is None
    assert "Selected package story" in package.script_draft_path.read_text(encoding="utf-8")
    assert episode is not None
    assert episode.status == "draft"
    assert [link.telegram_post_id for link in episode.posts] == [post_id]


def _make_session_factory() -> sessionmaker:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
