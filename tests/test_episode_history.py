import json
import os
from pathlib import Path

from app.pipeline.episode_history import get_recent_episode_post_ids, get_recent_episode_post_texts


def test_get_recent_episode_post_ids_reads_latest_completed_episode(tmp_path: Path) -> None:
    old_episode = tmp_path / "old"
    old_episode.mkdir()
    (old_episode / "audio.mp3").write_bytes(b"old")
    (old_episode / "telegram_publish.json").write_text('{"message_id": 1}')
    (old_episode / "selected_posts.json").write_text(
        json.dumps([{"post_id": 1}, {"post_id": 2}]),
        encoding="utf-8",
    )

    latest_episode = tmp_path / "latest"
    latest_episode.mkdir()
    (latest_episode / "audio.mp3").write_bytes(b"latest")
    (latest_episode / "telegram_publish.json").write_text('{"message_id": 1}')
    (latest_episode / "selected_posts.json").write_text(
        json.dumps([{"post_id": 10}, {"post_id": "11"}]),
        encoding="utf-8",
    )

    os.utime(old_episode, (100, 100))
    os.utime(latest_episode, (200, 200))

    assert get_recent_episode_post_ids(tmp_path, limit=1) == {10, 11}


def test_get_recent_episode_post_ids_skips_unfinished_episode(tmp_path: Path) -> None:
    unfinished_episode = tmp_path / "unfinished"
    unfinished_episode.mkdir()
    (unfinished_episode / "selected_posts.json").write_text(
        json.dumps([{"post_id": 99}]),
        encoding="utf-8",
    )

    completed_episode = tmp_path / "completed"
    completed_episode.mkdir()
    (completed_episode / "telegram_publish.json").write_text('{"message_id": 1}', encoding="utf-8")
    (completed_episode / "selected_posts.json").write_text(
        json.dumps([{"post_id": 7}]),
        encoding="utf-8",
    )

    os.utime(completed_episode, (100, 100))
    os.utime(unfinished_episode, (200, 200))

    assert get_recent_episode_post_ids(tmp_path, limit=1) == {7}


def test_get_recent_episode_post_ids_skips_blocked_episode(tmp_path: Path) -> None:
    blocked_episode = tmp_path / "blocked"
    blocked_episode.mkdir()
    (blocked_episode / "audio.mp3").write_bytes(b"blocked")
    (blocked_episode / "run_report.json").write_text(
        json.dumps({"status": "blocked"}),
        encoding="utf-8",
    )
    (blocked_episode / "selected_posts.json").write_text(
        json.dumps([{"post_id": 99}]),
        encoding="utf-8",
    )

    published_episode = tmp_path / "published"
    published_episode.mkdir()
    (published_episode / "run_report.json").write_text(
        json.dumps({"status": "published"}),
        encoding="utf-8",
    )
    (published_episode / "selected_posts.json").write_text(
        json.dumps([{"post_id": 7}]),
        encoding="utf-8",
    )

    os.utime(published_episode, (100, 100))
    os.utime(blocked_episode, (200, 200))

    assert get_recent_episode_post_ids(tmp_path, limit=1) == {7}


def test_get_recent_episode_post_texts_reads_recent_completed_episodes(tmp_path: Path) -> None:
    older_episode = tmp_path / "older"
    older_episode.mkdir()
    (older_episode / "audio.mp3").write_bytes(b"older")
    (older_episode / "telegram_publish.json").write_text('{"message_id": 1}')
    (older_episode / "selected_posts.json").write_text(
        json.dumps([{"post_id": 1, "text": "Older GitHub story"}]),
        encoding="utf-8",
    )

    latest_episode = tmp_path / "latest"
    latest_episode.mkdir()
    (latest_episode / "audio.mp3").write_bytes(b"latest")
    (latest_episode / "telegram_publish.json").write_text('{"message_id": 1}')
    (latest_episode / "selected_posts.json").write_text(
        json.dumps([{"post_id": 2, "text": "Latest Discord story"}]),
        encoding="utf-8",
    )

    os.utime(older_episode, (100, 100))
    os.utime(latest_episode, (200, 200))

    assert get_recent_episode_post_texts(tmp_path, limit=2) == [
        "Latest Discord story",
        "Older GitHub story",
    ]


def test_previews_and_malformed_reports_do_not_suppress_news(tmp_path):
    for name, report in [("preview", {"status": "complete"}), ("malformed", []), ("audio", None)]:
        path = tmp_path / name
        path.mkdir()
        (path / "audio.mp3").write_bytes(b"preview")
        (path / "selected_posts.json").write_text(json.dumps([{"post_id": 1, "text": "Not aired"}]))
        if report is not None:
            (path / "run_report.json").write_text(json.dumps(report))
    assert get_recent_episode_post_texts(tmp_path) == []


def test_recent_history_uses_publication_date_not_draft_age(tmp_path):
    for name, created, published, text in [
        ("old_draft", "2026-01-01", "2026-10-21", "Aired today"),
        ("new_draft", "2026-10-20", "2026-10-20", "Aired yesterday"),
    ]:
        path = tmp_path / name
        path.mkdir()
        (path / "metadata.json").write_text(json.dumps({"created_at": created}))
        (path / "telegram_publish.json").write_text(
            json.dumps({"message_id": 1, "published_at": published})
        )
        (path / "selected_posts.json").write_text(json.dumps([{"text": text}]))
    assert get_recent_episode_post_texts(tmp_path, limit=1) == ["Aired today"]
