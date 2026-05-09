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
    assert client.sent_file["entity"] == -1001
    assert client.sent_file["file"].endswith("audio.mp3")
    assert (package_path / "telegram_publish.json").exists()


class FakeMessage:
    id = 42


class FakeTelegramClient:
    def __init__(self) -> None:
        self.sent_file = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def send_file(self, entity, file, caption, supports_streaming):
        self.sent_file = {
            "entity": entity,
            "file": file,
            "caption": caption,
            "supports_streaming": supports_streaming,
        }
        return FakeMessage()
