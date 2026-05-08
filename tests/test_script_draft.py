from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories.posts import get_selected_posts, save_post, update_editorial_state
from app.db.repositories.sources import get_or_create_source
from app.pipeline.script_draft import export_script_markdown


def test_export_script_markdown(tmp_path) -> None:
    session_factory = _make_session_factory()
    with session_factory() as session:
        source = get_or_create_source(session, "durov")
        post = save_post(
            session,
            source,
            {
                "telegram_message_id": 1,
                "message_date": datetime(2026, 5, 6, tzinfo=timezone.utc),
                "text": "Selected story",
                "url": "https://t.me/durov/1",
            },
        )
        assert post is not None
        update_editorial_state(session, [post.id], selected=True, category="top news", editor_note="Open with this")
        posts = get_selected_posts(session)

    output_path = tmp_path / "script.md"
    export_script_markdown(posts, output_path, "Test script")
    content = output_path.read_text(encoding="utf-8")

    assert "# Test script" in content
    assert "## top news" in content
    assert "Editor note: Open with this" not in content
    assert "Selected story" in content


def _make_session_factory() -> sessionmaker:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
