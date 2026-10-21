import json

import pytest

from app.podcast.script_validation import validate_dialogue_script
from scripts import resume_episode_script as cli


def test_resume_uses_immutable_sources_and_saved_parameters(tmp_path, monkeypatch):
    blocks = ["Полная новость. Оговорка в конце."]
    (tmp_path / "source_blocks.json").write_text(json.dumps(blocks))
    (tmp_path / "script_draft.md").write_text("Черновик")
    (tmp_path / "script_generation.json").write_text(
        json.dumps({"model": "saved", "target_minutes": 11})
    )
    calls = []

    def generate(draft, **kwargs):
        calls.append(kwargs)
        text = "nika: Дата запуска пока неизвестна."
        return text, validate_dialogue_script(text)

    monkeypatch.setattr(cli, "rewrite_chunked_dialogue_script_draft", generate)
    output = cli.resume_script(tmp_path)
    assert calls[0]["source_blocks"] == blocks
    assert calls[0]["model"] == "saved" and calls[0]["target_minutes"] == 11
    assert calls[0]["checkpoint_dir"] == tmp_path / "script_scenes"
    assert output.exists() and (tmp_path / "script_quality_report.json").exists()
    assert not (tmp_path / "audio.mp3").exists()


@pytest.mark.parametrize("filename", ["audio.mp3", "telegram_publish.json"])
def test_resume_does_not_modify_finished_or_published_packages(tmp_path, filename):
    (tmp_path / filename).write_text("existing")
    with pytest.raises(ValueError, match="unpublished"):
        cli.resume_script(tmp_path)
    assert not (tmp_path / "llm_script.md").exists()


def test_resume_rejects_legacy_published_report_without_audio(tmp_path):
    (tmp_path / "run_report.json").write_text(json.dumps({"status": "published"}))
    with pytest.raises(ValueError, match="unpublished"):
        cli.resume_script(tmp_path)
    assert not (tmp_path / "script_generation.json").exists()
