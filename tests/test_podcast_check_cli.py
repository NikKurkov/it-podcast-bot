import json
import sys
from pathlib import Path

import pytest

import scripts.podcast_check as podcast_check


def test_podcast_check_parse_strict(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["podcast_check.py", "--episode", "latest", "--strict"])

    args = podcast_check.parse_args()

    assert args.episode == "latest"
    assert args.strict is True


def test_tts_risks_reports_missing_script(tmp_path: Path) -> None:
    risks = podcast_check._tts_risks(tmp_path / "missing.md")

    assert risks == ["llm_script.md is missing"]


def test_tts_risks_reports_no_dialogue_lines(tmp_path: Path) -> None:
    script_path = tmp_path / "llm_script.md"
    script_path.write_text("# заголовок\n\n---\n", encoding="utf-8")

    risks = podcast_check._tts_risks(script_path)

    assert "script has no speakable dialogue lines" in risks


def test_selected_count_reads_selected_posts(tmp_path: Path) -> None:
    selected_posts_path = tmp_path / "selected_posts.json"
    selected_posts_path.write_text(
        json.dumps([{"post_id": 1}, {"post_id": 2}]),
        encoding="utf-8",
    )

    assert podcast_check._selected_count(selected_posts_path) == 2


def test_podcast_check_strict_exits_for_bad_episode(tmp_path: Path, monkeypatch, capsys) -> None:
    episode_path = tmp_path / "episode"
    episode_path.mkdir()
    (episode_path / "selected_posts.json").write_text("[]", encoding="utf-8")
    (episode_path / "llm_script.md").write_text(
        "mark: Слишком коротко.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "argv", ["podcast_check.py", "--episode", str(episode_path), "--strict"])

    with pytest.raises(SystemExit) as exc_info:
        podcast_check.main()

    assert exc_info.value.code == 1
    assert "TTS gate:" in capsys.readouterr().out
