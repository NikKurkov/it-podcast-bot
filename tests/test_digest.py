from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories.posts import save_post
from app.db.repositories.sources import get_or_create_source
from app.pipeline.daily_digest import build_digest_items, export_digest_json, export_digest_markdown


def test_build_and_export_digest(tmp_path) -> None:
    session_factory = _make_session_factory()
    with session_factory() as session:
        source = get_or_create_source(session, "durov", title="Durov")
        save_post(
            session,
            source,
            {
                "telegram_message_id": 1,
                "message_date": datetime(2026, 5, 6, tzinfo=timezone.utc),
                "text": "Digest item",
                "url": "https://t.me/durov/1",
            },
        )

        items = build_digest_items(session, limit=10)

    markdown_path = tmp_path / "digest.md"
    json_path = tmp_path / "digest.json"
    export_digest_markdown(items, markdown_path)
    export_digest_json(items, json_path)

    assert items[0].source == "durov"
    assert "Digest item" in markdown_path.read_text(encoding="utf-8")
    assert '"post_id":' in json_path.read_text(encoding="utf-8")
    assert '"source": "durov"' in json_path.read_text(encoding="utf-8")


def _make_session_factory() -> sessionmaker:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
