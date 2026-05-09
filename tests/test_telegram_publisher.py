import json
import asyncio
from pathlib import Path

from app.telegram_publisher import publisher
from app.telegram_publisher.publisher import (
    build_episode_caption,
    prepare_publish_audio,
    publish_episode_package,
)


def test_build_episode_caption_uses_metadata_topics(tmp_path: Path) -> None:
    package_path = tmp_path / "episode"
    package_path.mkdir()
    (package_path / "episode_metadata.json").write_text(
        json.dumps(
            {
                "title": "НикКаст от 09 мая",
                "created_at": "2026-05-09T07:00:00+00:00",
                "topics": [
                    {"title": "GitHub снова штормит у части разработчиков"},
                    {"title": "Новый TTS научился быстрее отвечать в realtime"},
                ],
                "sources": [
                    {"summary": "GitHub снова штормит у части разработчиков"},
                    {"summary": "Новый TTS научился быстрее отвечать в realtime"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    caption = build_episode_caption(package_path)

    assert "НикКаст #001 от 09.05.2026" in caption
    assert "Темы выпуска:" in caption
    assert "GitHub снова штормит" in caption
    assert "Приятного прослушивания!" in caption
    assert len(caption) <= publisher.TELEGRAM_CAPTION_LIMIT


def test_prepare_publish_audio_copies_with_nice_filename_without_cover(
    tmp_path: Path,
    monkeypatch,
) -> None:
    package_path = tmp_path / "data" / "episodes" / "episode"
    package_path.mkdir(parents=True)
    (package_path / "audio.mp3").write_bytes(b"fake mp3")
    (package_path / "episode_metadata.json").write_text(
        json.dumps({"created_at": "2026-05-09T07:00:00+00:00"}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(publisher.settings, "podcast_cover_image", None)

    output_path = prepare_publish_audio(package_path)

    assert output_path.name == "НикКаст_001_от_09-05-2026.mp3"
    assert output_path.read_bytes() == b"fake mp3"


def test_build_episode_caption_falls_back_to_selected_posts(tmp_path: Path) -> None:
    package_path = tmp_path / "episode"
    package_path.mkdir()
    (package_path / "metadata.json").write_text(
        json.dumps({"created_at": "2026-05-09T07:00:00+00:00"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (package_path / "selected_posts.json").write_text(
        json.dumps(
            [
                {"text": "GitHub испытывает проблемы с доступностью в России."},
                {"text": "Новая realtime voice-модель ускоряет голосовых агентов."},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    caption = build_episode_caption(package_path)

    assert "Темы выпуска:" in caption
    assert "GitHub испытывает проблемы" in caption


def test_build_episode_caption_shortens_selected_post_titles(tmp_path: Path) -> None:
    package_path = tmp_path / "episode"
    package_path.mkdir()
    (package_path / "selected_posts.json").write_text(
        json.dumps(
            [
                {
                    "text": (
                        "Discord массово сбоит по всему миру — сервис не запускается "
                        "ни на одной платформе."
                    ),
                },
                {
                    "text": (
                        "В Телеграм появилось казино, официально — в мессенджере теперь "
                        "можно бросать кубики на деньги."
                    ),
                },
                {
                    "text": (
                        "Instagram* больше не конфиденциальная соцсеть — компания Meta* "
                        "убрала шифрование end2end."
                    ),
                },
                {
                    "text": (
                        "Почти удачная вейкап-атака с выходом на комбо — жаль, что в блок "
                        "Фильм «Мортал Комбат 2» во всём лучше первой части."
                    ),
                },
                {
                    "text": (
                        "У OpenAI вышло новое поколение realtime voice-моделей 🎙️ "
                        "GPT-Realtime-2: голосовая модель с reasoning уровня GPT-5."
                    ),
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    caption = build_episode_caption(package_path)

    assert "- Discord массово сбоит по всему миру" in caption
    assert "- В Телеграм появилось казино" in caption
    assert "- Instagram* больше не конфиденциальная соцсеть" in caption
    assert '- Выход фильма "Мортал Комбат 2"' in caption
    assert "- OpenAI выпустил новые realtime voice-модели" in caption
    assert "сервис не запускается" not in caption


def test_prepare_publish_audio_embeds_cover_with_ffmpeg(
    tmp_path: Path,
    monkeypatch,
) -> None:
    package_path = tmp_path / "data" / "episodes" / "episode"
    package_path.mkdir(parents=True)
    cover_path = tmp_path / "cover.png"
    (package_path / "audio.mp3").write_bytes(b"fake mp3")
    cover_path.write_bytes(b"fake png")
    calls = []

    def fake_run(command, check, capture_output, text):
        calls.append(command)
        Path(command[-1]).write_bytes(b"mp3 with cover")

    monkeypatch.setattr(publisher.subprocess, "run", fake_run)

    output_path = prepare_publish_audio(package_path, cover_path=cover_path)

    assert output_path.exists()
    assert calls
    assert str(cover_path) in calls[0]


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
    monkeypatch.setattr(publisher.settings, "podcast_cover_image", None)

    result = asyncio.run(publish_episode_package(package_path, channel_id="-1001"))

    assert result.channel_id == "-1001"
    assert result.message_id == 42
    assert client.sent_file["entity"] == "resolved:-1001"
    assert client.sent_file["file"].endswith(".mp3")
    assert "publish" in client.sent_file["file"]
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
    monkeypatch.setattr(publisher.settings, "podcast_cover_image", None)

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
    monkeypatch.setattr(publisher.settings, "podcast_cover_image", None)

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
