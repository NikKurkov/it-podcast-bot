from pathlib import Path

import scripts.publish_latest as publish_latest


def test_resolve_latest_episode_ignores_packages_without_audio(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    older = tmp_path / "data" / "episodes" / "older"
    broken_newer = tmp_path / "data" / "episodes" / "broken-newer"
    newer_with_audio = tmp_path / "data" / "episodes" / "newer-with-audio"
    older.mkdir(parents=True)
    broken_newer.mkdir()
    newer_with_audio.mkdir()
    (older / "audio.mp3").write_bytes(b"older")
    (newer_with_audio / "audio.mp3").write_bytes(b"newer")

    assert publish_latest._resolve_episode_path("latest").resolve() == newer_with_audio


def test_publish_latest_parse_dry_run_and_skip_quality_gate(monkeypatch) -> None:
    monkeypatch.setattr(
        publish_latest.sys,
        "argv",
        ["publish_latest.py", "--dry-run", "--skip-quality-gate"],
    )

    args = publish_latest.parse_args()

    assert args.dry_run is True
    assert args.skip_quality_gate is True
