import json
import os
from pathlib import Path

from app.pipeline.episode_history import get_recent_episode_post_ids


def test_get_recent_episode_post_ids_reads_latest_completed_episode(tmp_path: Path) -> None:
    old_episode = tmp_path / "old"
    old_episode.mkdir()
    (old_episode / "audio.mp3").write_bytes(b"old")
    (old_episode / "selected_posts.json").write_text(
        json.dumps([{"post_id": 1}, {"post_id": 2}]),
        encoding="utf-8",
    )

    latest_episode = tmp_path / "latest"
    latest_episode.mkdir()
    (latest_episode / "audio.mp3").write_bytes(b"latest")
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
    (completed_episode / "telegram_publish.json").write_text("{}", encoding="utf-8")
    (completed_episode / "selected_posts.json").write_text(
        json.dumps([{"post_id": 7}]),
        encoding="utf-8",
    )

    os.utime(completed_episode, (100, 100))
    os.utime(unfinished_episode, (200, 200))

    assert get_recent_episode_post_ids(tmp_path, limit=1) == {7}
