import json
import asyncio
from pathlib import Path

from app.telegram_publisher import publisher
from app.telegram_publisher.publisher import (
    build_episode_caption,
    prepare_publish_audio,
    publish_episode_package,
    validate_episode_for_publish,
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

    assert f"{publisher.settings.podcast_title} #001 от 09.05.2026" in caption
    assert "<b>Темы выпуска:</b>" in caption
    assert "GitHub снова штормит" in caption
    assert "- GitHub снова штормит у части разработчиков." in caption
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

    expected_title = publisher.settings.podcast_title.replace(" ", "_")
    assert output_path.name == f"{expected_title}_001_от_09-05-2026.mp3"
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

    assert "<b>Темы выпуска:</b>" in caption
    assert "GitHub испытывает проблемы" in caption


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


def test_validate_episode_for_publish_reports_missing_files(tmp_path: Path) -> None:
    package_path = tmp_path / "episode"
    package_path.mkdir()

    issues = validate_episode_for_publish(package_path)

    assert "audio.mp3 is missing" in issues
    assert "llm_script.md is missing" in issues


def test_validate_episode_for_publish_allows_good_episode(tmp_path: Path) -> None:
    package_path = tmp_path / "episode"
    package_path.mkdir()
    (package_path / "audio.mp3").write_bytes(b"fake mp3")
    (package_path / "llm_script.md").write_text(
        """
mark: Добрый день, сегодня девятое мая, и вы слушаете НикКаст с обзором главных новостей в мире айти.
nika: В выпуске: GitHub и инфраструктура.
gleb: Дальше у нас риск с доступностью.
artem: Проверьте зеркала и план отката.
mark: А вот теперь переключаемся к безопасности.
nika: Здесь важно проверить доступы.
gleb: Без логов команда узнает о проблеме слишком поздно.
artem: Зафиксируйте мониторинг и ответственных.
mark: На этом всё, это были главные новости на сегодня.
nika: Хорошего вам дня.
gleb: Проверяйте резервные сценарии.
artem: До новых встреч.
""",
        encoding="utf-8",
    )

    assert validate_episode_for_publish(package_path) == []


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
    monkeypatch.setattr(publisher, "_mark_package_published", lambda package_path, result: None)

    result = asyncio.run(publish_episode_package(package_path, channel_id="-1001"))

    assert result.channel_id == "-1001"
    assert result.message_id == 42
    assert client.sent_file["entity"] == "resolved:-1001"
    assert client.sent_file["file"].endswith(".mp3")
    assert "publish" in client.sent_file["file"]
    assert client.sent_file["parse_mode"] == "html"
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
    monkeypatch.setattr(publisher, "_mark_package_published", lambda package_path, result: None)

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
    monkeypatch.setattr(publisher, "_mark_package_published", lambda package_path, result: None)

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

    async def connect(self):
        return None

    async def is_user_authorized(self):
        return True

    async def disconnect(self):
        return None

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

    async def send_file(self, entity, file, caption, parse_mode, supports_streaming):
        self.sent_file = {
            "entity": entity,
            "file": file,
            "caption": caption,
            "parse_mode": parse_mode,
            "supports_streaming": supports_streaming,
        }
        return FakeMessage()


def test_caption_truncation_respects_limit_and_html_boundaries() -> None:
    from html.parser import HTMLParser

    class StrictParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.tags = []

        def handle_starttag(self, tag, attrs):
            self.tags.append(tag)

        def handle_endtag(self, tag):
            assert self.tags.pop() == tag

    for text in ("x" * 50, "a" * 16 + "&amp;" * 20, "<b>" + "x" * 50 + "</b>"):
        result = publisher._trim_caption(text, 20)
        assert len(result) <= 20
        parser = StrictParser()
        parser.feed(result)
        parser.close()
        assert parser.tags == []
        assert not result.rstrip(".").endswith("&am")


def test_publisher_rejects_already_published_package_before_connecting(tmp_path, monkeypatch):
    import pytest

    (tmp_path / "audio.mp3").write_bytes(b"audio")
    (tmp_path / "telegram_publish.json").write_text('{"message_id": 42}')
    monkeypatch.setattr(publisher.settings, "podcast_cover_image", None)

    def unexpected_client():
        pytest.fail("Already published package must not connect to Telegram")

    monkeypatch.setattr(publisher, "create_telegram_client", unexpected_client)
    with pytest.raises(RuntimeError, match="already published"):
        asyncio.run(publish_episode_package(tmp_path, channel_id="-1001"))


def test_publisher_serializes_concurrent_attempts_and_allows_explicit_republish(
    tmp_path, monkeypatch
):

    (tmp_path / "audio.mp3").write_bytes(b"audio")
    client = FakeTelegramClient()
    sends = []

    async def send_file(entity, **kwargs):
        sends.append(kwargs)
        await asyncio.sleep(0)
        return FakeMessage()

    client.send_file = send_file
    monkeypatch.setattr(publisher, "create_telegram_client", lambda: client)
    monkeypatch.setattr(publisher.settings, "podcast_cover_image", None)
    monkeypatch.setattr(publisher, "_mark_package_published", lambda *args: None)

    async def publish_twice():
        return await asyncio.gather(
            publish_episode_package(tmp_path, channel_id="-1001"),
            publish_episode_package(tmp_path, channel_id="-1001"),
            return_exceptions=True,
        )

    results = asyncio.run(publish_twice())
    assert sum(isinstance(result, RuntimeError) for result in results) == 1
    assert len(sends) == 1
    asyncio.run(publish_episode_package(tmp_path, channel_id="-1001", republish=True))
    assert len(sends) == 2


def test_publish_receipt_survives_disconnect_error(tmp_path, monkeypatch):
    import pytest

    class DisconnectFailure(FakeTelegramClient):
        async def disconnect(self):
            raise OSError("disconnect failed")

    (tmp_path / "audio.mp3").write_bytes(b"audio")
    client = DisconnectFailure()
    monkeypatch.setattr(publisher, "create_telegram_client", lambda: client)
    monkeypatch.setattr(publisher.settings, "podcast_cover_image", None)
    monkeypatch.setattr(publisher, "_mark_package_published", lambda *args: None)
    with pytest.raises(OSError, match="disconnect failed"):
        asyncio.run(publish_episode_package(tmp_path, channel_id="-1001"))
    receipt = json.loads((tmp_path / "telegram_publish.json").read_text())
    assert receipt["message_id"] == 42
    with pytest.raises(RuntimeError, match="already published"):
        asyncio.run(publish_episode_package(tmp_path, channel_id="-1001"))


def test_caption_does_not_turn_speculation_into_a_release(tmp_path):
    import json
    from app.telegram_publisher.publisher import build_episode_caption

    original = "НовыйВендор обсуждает voice realtime API; выпуск пока не подтверждён."
    (tmp_path / "episode_metadata.json").write_text(
        json.dumps(
            {
                "sources": [{"summary": original}],
            }
        ),
        encoding="utf-8",
    )
    caption = build_episode_caption(tmp_path)
    assert original in caption
    assert "выпустил" not in caption


def test_caption_omits_oversized_optional_topic_whole(tmp_path):
    import json
    from app.telegram_publisher.publisher import build_episode_caption

    long = "Важная оговорка: " + "полный текст " * 150 + "выпуска не было."
    short = "ДругойВендор изменил условия лицензии."
    (tmp_path / "episode_metadata.json").write_text(
        json.dumps(
            {
                "sources": [{"summary": long}, {"summary": short}],
            }
        ),
        encoding="utf-8",
    )
    caption = build_episode_caption(tmp_path)
    assert "Важная оговорка" not in caption
    assert short in caption
    assert len(caption.encode("utf-16-le")) // 2 <= 1024
