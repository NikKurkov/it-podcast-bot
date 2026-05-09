import json
import asyncio
from pathlib import Path

from app.telegram_publisher import publisher
from app.telegram_publisher.publisher import build_episode_caption, publish_episode_package


def test_build_episode_caption_uses_metadata_topics(tmp_path: Path) -> None:
    package_path = tmp_path / "episode"
    package_path.mkdir()
    (package_path / "episode_metadata.json").write_text(
        json.dumps(
            {
                "title": "НикКаст от 09 мая",
                "topics": [
                    {"title": "GitHub снова штормит у части разработчиков"},
                    {"title": "Новый TTS научился быстрее отвечать в realtime"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    caption = build_episode_caption(package_path)

    assert "НикКаст от 09 мая" in caption
    assert "GitHub снова штормит" in caption
    assert len(caption) <= publisher.TELEGRAM_CAPTION_LIMIT


def test_resolve_channel_id_keeps_usernames_and_converts_numeric_ids() -> None:
    assert publisher._resolve_channel_id("-1001234567890") == -1001234567890
    assert publisher._resolve_channel_id("@example_channel") == "@example_channel"
    assert publisher._telegram_channel_internal_id(-1001234567890) == 1234567890


def test_publish_episode_package_sends_audio_and_writes_result(tmp_path: Path, monkeypatch) -> None:
    package_path = tmp_path / "episode"
    package_path.mkdir()
    (package_path / "audio.mp3").write_bytes(b"fake mp3")
    (package_path / "episode_metadata.json").write_text(
        json.dumps({"title": "Test episode"}, ensure_ascii=False),
        encoding="utf-8",
    )
    client = FakeTelegramClient()
    monkeypatch.setattr(publisher, "create_telegram_client", lambda: client)

    result = asyncio.run(publish_episode_package(package_path, channel_id="-1001"))

    assert result.channel_id == "-1001"
    assert result.message_id == 42
    assert client.sent_file["entity"] == "resolved:-1001"
    assert client.sent_file["file"].endswith("audio.mp3")
    assert (package_path / "telegram_publish.json").exists()


def test_publish_episode_package_resolves_numeric_channel_from_dialogs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    package_path = tmp_path / "episode"
    package_path.mkdir()
    (package_path / "audio.mp3").write_bytes(b"fake mp3")
    client = FakeTelegramClient(resolve_numeric=False)
    monkeypatch.setattr(publisher, "create_telegram_client", lambda: client)

    asyncio.run(publish_episode_package(package_path, channel_id="-10012345"))

    assert client.sent_file["entity"].id == 12345


def test_publish_episode_package_resolves_numeric_channel_by_dialog_id(
    tmp_path: Path,
    monkeypatch,
) -> None:
    package_path = tmp_path / "episode"
    package_path.mkdir()
    (package_path / "audio.mp3").write_bytes(b"fake mp3")
    client = FakeTelegramClient(resolve_numeric=False, dialog_id=-10067890, entity_id=111)
    monkeypatch.setattr(publisher, "create_telegram_client", lambda: client)

    asyncio.run(publish_episode_package(package_path, channel_id="-10067890"))

    assert client.sent_file["entity"].id == 111


class FakeMessage:
    id = 42


class FakeDialogEntity:
    def __init__(self, entity_id: int) -> None:
        self.id = entity_id


class FakeDialog:
    def __init__(self, entity_id: int, dialog_id: int | None = None) -> None:
        self.id = dialog_id
        self.entity = FakeDialogEntity(entity_id)


class FakeTelegramClient:
    def __init__(
        self,
        resolve_numeric: bool = True,
        dialog_id: int | None = None,
        entity_id: int = 12345,
    ) -> None:
        self.sent_file = {}
        self.resolve_numeric = resolve_numeric
        self.dialog_id = dialog_id
        self.entity_id = entity_id

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def get_input_entity(self, entity):
        if isinstance(entity, int) and not self.resolve_numeric:
            raise ValueError("not cached")
        return f"resolved:{entity}"

    async def iter_dialogs(self):
        yield FakeDialog(self.entity_id, dialog_id=self.dialog_id)

    async def send_file(self, entity, file, caption, supports_streaming):
        self.sent_file = {
            "entity": entity,
            "file": file,
            "caption": caption,
            "supports_streaming": supports_streaming,
        }
        return FakeMessage()
