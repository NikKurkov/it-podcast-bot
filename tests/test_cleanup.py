from pathlib import Path

from app.maintenance.cleanup import clean_workspace, discover_cleanup_targets


def test_discover_cleanup_targets_keeps_music_and_voices(tmp_path: Path) -> None:
    _write(tmp_path / "data/audio/music/chill_loop.mp3")
    _write(tmp_path / "data/audio/latest_episode.mp3")
    _write(tmp_path / "data/voices/xtts/nika.wav")
    _write(tmp_path / "data/episodes/demo/audio.mp3")
    _write(tmp_path / "data/it_podcast_bot.sqlite3")

    targets = discover_cleanup_targets(tmp_path, "sqlite:///data/it_podcast_bot.sqlite3")
    target_paths = {target.path.relative_to(tmp_path) for target in targets}

    assert Path("data/audio/latest_episode.mp3") in target_paths
    assert Path("data/episodes/demo") in target_paths
    assert Path("data/it_podcast_bot.sqlite3") in target_paths
    assert Path("data/audio/music") not in target_paths
    assert Path("data/audio/music/chill_loop.mp3") not in target_paths
    assert Path("data/voices/xtts/nika.wav") not in target_paths


def test_clean_workspace_removes_generated_data_and_preserves_assets(tmp_path: Path) -> None:
    _write(tmp_path / "data/audio/music/chill_loop.mp3")
    _write(tmp_path / "data/audio/latest_episode.mp3")
    _write(tmp_path / "data/voices/xtts/nika.wav")
    _write(tmp_path / "data/episodes/demo/audio.mp3")
    _write(tmp_path / "data/raw/raw.json")
    _write(tmp_path / "data/logs/app.log")
    _write(tmp_path / "data/backups/old.sqlite3")
    _write(tmp_path / "data/it_podcast_bot.sqlite3")

    removed_targets = clean_workspace(tmp_path, "sqlite:///data/it_podcast_bot.sqlite3")

    assert removed_targets
    assert not (tmp_path / "data/audio/latest_episode.mp3").exists()
    assert not (tmp_path / "data/episodes/demo").exists()
    assert not (tmp_path / "data/raw/raw.json").exists()
    assert not (tmp_path / "data/logs/app.log").exists()
    assert not (tmp_path / "data/backups/old.sqlite3").exists()
    assert not (tmp_path / "data/it_podcast_bot.sqlite3").exists()
    assert (tmp_path / "data/audio/music/chill_loop.mp3").exists()
    assert (tmp_path / "data/voices/xtts/nika.wav").exists()
    assert (tmp_path / "data/episodes").is_dir()
    assert (tmp_path / "data/raw").is_dir()


def test_clean_workspace_can_keep_backups(tmp_path: Path) -> None:
    _write(tmp_path / "data/backups/old.sqlite3")

    clean_workspace(tmp_path, "sqlite:///data/it_podcast_bot.sqlite3", keep_backups=True)

    assert (tmp_path / "data/backups/old.sqlite3").exists()


def _write(path: Path, content: bytes = b"data") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
