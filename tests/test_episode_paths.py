import importlib
import json
import os

import pytest


@pytest.mark.parametrize(
    "module",
    [
        "scripts.episode_info",
        "scripts.podcast_check",
        "scripts.check_script_quality",
        "scripts.render_episode_audio",
        "scripts.publish_latest",
    ],
)
def test_latest_uses_creation_time_instead_of_directory_changes(tmp_path, monkeypatch, module):
    command = importlib.import_module(module)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(command, "PROJECT_ROOT", tmp_path)
    episodes = tmp_path / "data/episodes"
    for name, date in (("older", "2026-05-01"), ("newer", "2026-05-02")):
        path = episodes / name
        path.mkdir(parents=True)
        (path / "metadata.json").write_text(json.dumps({"created_at": date + "T07:00:00+00:00"}))
        (path / "audio.mp3").touch()
    os.utime(episodes / "older", (2000000000, 2000000000))
    assert command._resolve_episode_path("latest").resolve() == episodes / "newer"
    assert command._resolve_episode_path("newer").resolve() == episodes / "newer"


@pytest.mark.parametrize(
    "module",
    [
        "scripts.episode_info",
        "scripts.podcast_check",
        "scripts.check_script_quality",
        "scripts.render_episode_audio",
        "scripts.publish_latest",
    ],
)
def test_latest_missing_directory_has_actionable_error(tmp_path, monkeypatch, module):
    command = importlib.import_module(module)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(command, "PROJECT_ROOT", tmp_path)
    with pytest.raises(SystemExit, match="No episode packages"):
        command._resolve_episode_path("latest")
