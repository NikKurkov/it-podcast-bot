from datetime import datetime
import json

import pytest

from app.config.settings import settings
from app.pipeline.daily_digest import DigestItem
from app.pipeline.publication import (
    estimate_topic_timestamps,
    write_episode_metadata,
    write_show_notes,
)


def test_estimate_topic_timestamps_uses_duration() -> None:
    timestamps = estimate_topic_timestamps(3, 300)

    assert timestamps[0] == "00:00"
    assert len(timestamps) == 4
    assert timestamps[1] != timestamps[2]


@pytest.mark.parametrize(
    "participants, expected",
    [
        ("mark,nika", ["mark", "nika"]),
        (None, ["mark", "gleb", "nika", "artem"]),
    ],
)
def test_episode_metadata_uses_configured_cast(tmp_path, monkeypatch, participants, expected):
    monkeypatch.setattr(settings, "podcast_participants", participants)
    path = write_episode_metadata(
        title="Test",
        created_at="2026-10-21T09:00:00+03:00",
        digest_items=[],
        output_path=tmp_path / "episode_metadata.json",
    )
    assert json.loads(path.read_text())["characters"] == expected


def test_write_show_notes_contains_sources_and_timestamps(tmp_path) -> None:
    item = DigestItem(
        post_id=1,
        source="example",
        title="Example",
        message_date=datetime(2026, 5, 9, 12, 0),
        text="GitHub API outage affected production releases.",
        url="https://t.me/example/1",
        views=100,
        forwards=5,
        score=None,
    )
    output_path = tmp_path / "show_notes.md"

    write_show_notes(title="Test episode", digest_items=[item], output_path=output_path)
    content = output_path.read_text(encoding="utf-8")

    assert "# Test episode" in content
    assert "00:00" in content
    assert "@example" in content
    assert "https://t.me/example/1" in content


def test_write_episode_metadata_contains_publication_fields(tmp_path) -> None:
    item = DigestItem(
        post_id=1,
        source="example",
        title="Example",
        message_date=datetime(2026, 5, 9, 12, 0),
        text="Security incident in production infrastructure.",
        url="https://t.me/example/1",
        views=100,
        forwards=5,
        score=None,
    )
    output_path = tmp_path / "episode_metadata.json"

    write_episode_metadata(
        title="Test episode",
        created_at="2026-05-09T12:00:00+00:00",
        digest_items=[item],
        output_path=output_path,
        audio_path=tmp_path / "audio.mp3",
        llm_model="local-model",
        tts_provider="xtts",
        background_music=True,
    )
    content = output_path.read_text(encoding="utf-8")

    assert "Test episode" in content
    assert "local-model" in content
    assert "xtts" in content
    assert "Security" in content


def test_write_episode_metadata_uses_clean_short_summaries(tmp_path) -> None:
    item = DigestItem(
        post_id=1,
        source="example",
        title="Example",
        message_date=datetime(2026, 5, 9, 12, 0),
        text=(
            "Crocs и Red Bull выпустят коллекцию сабо в виде болидов Формулы-1 "
            "Старт продаж запланирован на 21 мая."
        ),
        url="https://t.me/example/1",
        views=100,
        forwards=5,
        score=None,
    )
    output_path = tmp_path / "episode_metadata.json"

    write_episode_metadata(
        title="Test episode",
        created_at="2026-05-09T12:00:00+00:00",
        digest_items=[item],
        output_path=output_path,
    )
    content = output_path.read_text(encoding="utf-8")

    assert "Старт продаж запланирован на 21 мая." in content
    assert "..." not in content


def test_separate_render_refreshes_duration_without_changing_source_date(tmp_path):
    import json
    from app.pipeline.publication import refresh_rendered_package

    created = "2026-10-20T05:00:00+00:00"
    (tmp_path / "metadata.json").write_text(
        json.dumps({"title": "Existing", "created_at": created})
    )
    (tmp_path / "selected_posts.json").write_text("[]")
    (tmp_path / "audio_report.json").write_text(
        json.dumps([{"path": "audio.mp3", "duration_seconds": 720}])
    )
    refresh_rendered_package(tmp_path, provider="xtts", with_music=True, music_volume=0.04)
    metadata = json.loads((tmp_path / "metadata.json").read_text())
    episode = json.loads((tmp_path / "episode_metadata.json").read_text())
    assert metadata["created_at"] == episode["created_at"] == created
    assert episode["duration_seconds"] == 720 and episode["duration"] == "12:00"
    assert episode["audio_path"] == str(tmp_path / "audio.mp3")
    assert metadata["background_music_volume"] == 0.04
