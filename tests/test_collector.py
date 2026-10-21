from app.telegram_reader.collector import _message_url


def test_message_url_for_public_channel() -> None:
    assert _message_url("durov", 123) == "https://t.me/durov/123"


def test_message_url_is_empty_for_private_or_invite_source() -> None:
    assert _message_url("https://t.me/+invite", 123) is None
    assert _message_url("+invite", 123) is None


def test_unattended_collection_never_requests_interactive_login(monkeypatch):
    import asyncio
    import pytest
    from app.telegram_reader import collector

    class UnauthorizedClient:
        connected = False

        async def connect(self):
            self.connected = True

        async def is_user_authorized(self):
            return False

        async def disconnect(self):
            self.connected = False

        async def __aenter__(self):
            pytest.fail("Unattended jobs must not enter interactive Telethon start")

    client = UnauthorizedClient()
    monkeypatch.setattr(collector, "init_db", lambda: None)
    monkeypatch.setattr(collector, "create_telegram_client", lambda: client)
    with pytest.raises(RuntimeError, match="authorized"):
        asyncio.run(collector.collect_latest_posts(channels=["source"], interactive=False))
    assert client.connected is False


def test_daily_collection_reads_the_whole_date_window_not_twenty_messages(monkeypatch):
    import asyncio
    from contextlib import asynccontextmanager
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace
    from app.telegram_reader import collector

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    saved = []

    class Client:
        async def get_entity(self, username):
            return SimpleNamespace(title="Source")

        async def iter_messages(self, entity, limit):
            assert limit is None
            for index in range(36):
                yield SimpleNamespace(
                    id=index,
                    date=cutoff + timedelta(minutes=1)
                    if index < 35
                    else cutoff - timedelta(seconds=1),
                    message=f"News {index}",
                    views=1,
                    forwards=0,
                )

    @asynccontextmanager
    async def connected(*args, **kwargs):
        yield

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(collector, "init_db", lambda: None)
    monkeypatch.setattr(collector, "SessionLocal", Session)
    monkeypatch.setattr(collector, "create_telegram_client", Client)
    monkeypatch.setattr(collector, "telegram_session", connected)
    monkeypatch.setattr(collector, "get_or_create_source", lambda *a, **k: object())

    def save(session, source, data):
        saved.append(data)
        return {"created": True, "updated": False}

    monkeypatch.setattr(collector, "save_or_update_post", save)
    stats = asyncio.run(collector.collect_latest_posts(channels=["source"], since=cutoff))
    assert len(saved) == stats["posts_seen"] == 35
    assert all(post["message_date"] >= cutoff for post in saved)


def test_zero_configured_limit_requires_a_time_window(monkeypatch):
    import asyncio
    import pytest
    from app.telegram_reader import collector

    monkeypatch.setattr(collector.settings, "default_limit_per_channel", 0)
    monkeypatch.setattr(
        collector, "init_db", lambda: pytest.fail("Reject before touching the database")
    )
    with pytest.raises(ValueError, match="date cutoff"):
        asyncio.run(collector.collect_latest_posts(channels=["source"]))
