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


def test_package_refuses_to_overwrite_existing_directory(tmp_path, monkeypatch) -> None:
    import pytest

    monkeypatch.chdir(tmp_path)
    path = tmp_path / "data/episodes/existing"
    path.mkdir(parents=True)
    sentinel = path / "script_draft.md"
    sentinel.write_text("original", encoding="utf-8")
    with _make_session_factory()() as session:
        with pytest.raises(FileExistsError):
            create_episode_package(session, slug="existing")
    assert sentinel.read_text(encoding="utf-8") == "original"


def test_package_refuses_paths_in_slug(tmp_path, monkeypatch) -> None:
    import pytest
    from app.pipeline.episode_package import _build_package_slug

    monkeypatch.chdir(tmp_path)
    for slug in ("../outside", "/tmp/outside", ".", "..", "nested/name", "nested\\name", " "):
        with pytest.raises(ValueError):
            _build_package_slug(slug)


def test_package_quality_gate_blocks_before_tts(tmp_path, monkeypatch) -> None:
    import pytest
    from app.pipeline import episode_package
    from app.podcast.script_validation import validate_dialogue_script

    monkeypatch.chdir(tmp_path)
    script = "unknown: Привет.\nnika: Новость.\ngleb: Понятно.\nartem: Пока."
    monkeypatch.setattr(
        episode_package,
        "rewrite_chunked_dialogue_script_draft",
        lambda *args, **kwargs: (script, validate_dialogue_script(script)),
    )
    monkeypatch.setattr(episode_package, "ensure_opening_and_rundown", lambda text, **kwargs: text)

    async def unexpected_tts(*args, **kwargs):
        pytest.fail("TTS must not run for a blocked script")

    monkeypatch.setattr(episode_package, "synthesize_dialogue_lines", unexpected_tts)
    with _make_session_factory()() as session:
        with pytest.raises(RuntimeError, match="failed validation"):
            create_episode_package(
                session,
                slug="blocked",
                llm_profile="fast",
                dialogue_script=True,
                with_audio=True,
                tts_provider="xtts",
            )
    assert (tmp_path / "data/episodes/blocked/llm_script.md").exists()


def test_narrative_espeak_audio_does_not_require_dialogue_cast(tmp_path, monkeypatch):
    from app.pipeline import episode_package

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(episode_package, "rewrite_script_draft", lambda *a, **k: "Обычный рассказ.")

    def write_audio(text, path, **kwargs):
        path.write_bytes(b"voice")
        return path

    def convert_audio(source, destination):
        destination.write_bytes(source.read_bytes())
        return destination

    monkeypatch.setattr(episode_package, "synthesize_with_espeak", write_audio)
    monkeypatch.setattr(episode_package, "convert_wav_to_mp3", convert_audio)
    monkeypatch.setattr(episode_package, "write_audio_report", lambda *a, **k: None)
    with _make_session_factory()() as session:
        package = create_episode_package(
            session,
            slug="narrative",
            llm_profile="fast",
            with_audio=True,
            tts_provider="espeak",
        )
    assert package.audio_mp3_path.read_bytes() == b"voice"
