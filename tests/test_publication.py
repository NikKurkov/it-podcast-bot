from datetime import datetime

from app.pipeline.daily_digest import DigestItem
from app.pipeline.publication import estimate_topic_timestamps, write_episode_metadata, write_show_notes


def test_estimate_topic_timestamps_uses_duration() -> None:
    timestamps = estimate_topic_timestamps(3, 300)

    assert timestamps[0] == "00:00"
    assert len(timestamps) == 4
    assert timestamps[1] != timestamps[2]


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
    assert "security" in content


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

    assert "заплан" not in content
    assert "..." not in content
