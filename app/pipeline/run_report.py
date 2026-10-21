import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.pipeline.episode_package import EpisodePackage
from app.podcast.script_quality import quality_gate_allows_tts


def write_run_report(
    *,
    status: str,
    output_dir: Path,
    collect_stats: dict[str, int] | None = None,
    selected_count: int | None = None,
    requested_top: int | None = None,
    package: EpisodePackage | None = None,
    publish_result: dict[str, Any] | None = None,
    publication_checks: list[dict[str, str]] | None = None,
    selection_diagnostics: dict[str, Any] | None = None,
    error: str | None = None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "collect_stats": collect_stats or {},
        "selected_count": selected_count,
        "requested_top": requested_top,
        "package": str(package.path) if package else None,
        "publish_result": publish_result,
        "publication_checks": publication_checks or [],
        "selection_diagnostics": selection_diagnostics or {},
        "error": error,
    }
    if package:
        report["files"] = {
            "metadata": str(package.metadata_path),
            "selected_posts": str(package.selected_posts_path),
            "llm_script": str(package.llm_script_path) if package.llm_script_path else None,
            "audio_mp3": str(package.audio_mp3_path) if package.audio_mp3_path else None,
            "script_quality": str(package.path / "script_quality_report.json"),
            "audio_report": str(package.path / "audio_report.json"),
        }
    output_path = output_dir / "run_report.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_path = Path("data/logs/latest_run_report.json")
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def publication_gate_checks(
    package: EpisodePackage,
    *,
    selected_count: int,
    requested_top: int,
) -> list[dict[str, str]]:
    checks = [
        _selected_count_check(selected_count=selected_count, requested_top=requested_top),
        _audio_check(package),
        _script_quality_check(package),
    ]
    return checks


def publication_allowed(checks: list[dict[str, str]]) -> bool:
    return not any(check["status"] == "error" for check in checks)


def format_publication_checks(checks: list[dict[str, str]]) -> str:
    lines = ["Publication checks:"]
    for check in checks:
        lines.append(f"  [{check['status'].upper()}] {check['name']} - {check['detail']}")
    return "\n".join(lines)


def _selected_count_check(*, selected_count: int, requested_top: int) -> dict[str, str]:
    if selected_count > 0:
        return {
            "name": "selected_posts",
            "status": "warning" if selected_count < requested_top else "ok",
            "detail": f"{selected_count} selected out of up to {requested_top}",
        }
    return {
        "name": "selected_posts",
        "status": "error",
        "detail": "no suitable fresh stories selected",
    }


def _audio_check(package: EpisodePackage) -> dict[str, str]:
    audio_path = package.audio_mp3_path
    if not audio_path or not audio_path.exists():
        return {"name": "audio_mp3", "status": "error", "detail": "missing"}
    size_mb = audio_path.stat().st_size / 1024 / 1024
    if size_mb < 0.2:
        return {"name": "audio_mp3", "status": "error", "detail": f"too small: {size_mb:.2f} MB"}
    return {"name": "audio_mp3", "status": "ok", "detail": f"{size_mb:.2f} MB"}


def _script_quality_check(package: EpisodePackage) -> dict[str, str]:
    report_path = package.path / "script_quality_report.json"
    if not report_path.exists():
        return {"name": "script_quality", "status": "warning", "detail": "report missing"}
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"name": "script_quality", "status": "error", "detail": "invalid json"}
    allowed, blocking = quality_gate_allows_tts(report)
    if allowed:
        return {"name": "script_quality", "status": "ok", "detail": "passes quality gate"}
    return {"name": "script_quality", "status": "error", "detail": ", ".join(blocking)}
