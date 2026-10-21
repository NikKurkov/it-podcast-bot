import json
from pathlib import Path

from app.pipeline.episode_package import EpisodePackage
from app.pipeline.run_report import (
    publication_allowed,
    publication_gate_checks,
    write_run_report,
)


def test_publication_gate_blocks_missing_audio(tmp_path: Path) -> None:
    package = _package(tmp_path)
    (package.path / "script_quality_report.json").write_text(
        json.dumps(
            {
                "validation_issues": [],
                "opening_present": True,
                "rundown_present": True,
                "lines_count": 4,
                "speaker_counts": {"mark": 2, "nika": 2, "gleb": 2, "artem": 2},
            },
        ),
        encoding="utf-8",
    )

    checks = publication_gate_checks(package, selected_count=3, requested_top=5)

    assert publication_allowed(checks) is False
    assert any(check["name"] == "audio_mp3" and check["status"] == "error" for check in checks)


def test_write_run_report_writes_package_and_latest_report(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    package = _package(tmp_path / "episode")

    report_path = write_run_report(
        status="complete",
        output_dir=package.path,
        selected_count=3,
        requested_top=5,
        package=package,
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    latest = json.loads(Path("data/logs/latest_run_report.json").read_text(encoding="utf-8"))
    assert report["status"] == "complete"
    assert report["selected_count"] == 3
    assert latest["package"] == str(package.path)


def _package(root: Path) -> EpisodePackage:
    root.mkdir(parents=True, exist_ok=True)
    return EpisodePackage(
        path=root,
        digest_markdown_path=root / "digest.md",
        selected_posts_path=root / "selected_posts.json",
        script_draft_path=root / "script_draft.md",
        llm_script_path=root / "llm_script.md",
        audio_wav_path=root / "audio.wav",
        audio_mp3_path=root / "audio.mp3",
        audio_voice_wav_path=root / "audio_voice.wav",
        metadata_path=root / "metadata.json",
    )
