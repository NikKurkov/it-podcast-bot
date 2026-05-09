import json
from pathlib import Path

from app.pipeline.episode_package import EpisodePackage


def format_episode_report(
    package: EpisodePackage,
    *,
    collect_stats: dict[str, int],
    selected_count: int,
) -> str:
    lines = [
        f"  package: {package.path}",
        f"  selected_posts: {selected_count}",
        "",
        "Collection:",
    ]
    for key, value in collect_stats.items():
        lines.append(f"  {key}: {value}")

    files = _existing_files(package)
    if files:
        lines.extend(["", "Files:"])
        for label, path in files:
            lines.append(f"  {label}: {path}")

    audio_summary = _audio_summary(package.path / "audio_report.json")
    if audio_summary:
        lines.extend(["", "Audio:"])
        lines.extend(f"  {line}" for line in audio_summary)

    selected_posts = _selected_posts_summary(package.selected_posts_path)
    if selected_posts:
        lines.extend(["", "Selected news:"])
        lines.extend(f"  {line}" for line in selected_posts)

    quality_summary = _script_quality_summary(package.path / "script_quality_report.json")
    if quality_summary:
        lines.extend(["", "Script quality:"])
        lines.extend(f"  {line}" for line in quality_summary)

    return "\n".join(lines)


def _existing_files(package: EpisodePackage) -> list[tuple[str, Path]]:
    candidates = [
        ("digest", package.digest_markdown_path),
        ("script_draft", package.script_draft_path),
        ("llm_script", package.llm_script_path),
        ("audio_mp3", package.audio_mp3_path),
        ("audio_voice", package.audio_voice_wav_path),
        ("script_quality", package.path / "script_quality_report.json"),
        ("show_notes", package.path / "show_notes.md"),
        ("episode_metadata", package.path / "episode_metadata.json"),
        ("metadata", package.metadata_path),
    ]
    return [(label, path) for label, path in candidates if path and path.exists()]


def _audio_summary(report_path: Path) -> list[str]:
    if not report_path.exists():
        return []

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    lines = []
    for item in report:
        path = item.get("path")
        duration = _format_duration(float(item.get("duration_seconds") or 0))
        sample_rate = item.get("sample_rate")
        codec = item.get("codec")
        lines.append(f"{path}: {duration}, {sample_rate} Hz, {codec}")
    return lines


def _script_quality_summary(report_path: Path) -> list[str]:
    if not report_path.exists():
        return []

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    lines = [
        f"lines: {report.get('lines_count', 0)}",
        f"opening: {report.get('opening_present')}",
        f"rundown: {report.get('rundown_present')}",
        f"transitions: {report.get('transition_lines', 0)}",
    ]
    warnings = report.get("warnings") or []
    if warnings:
        lines.append(f"warnings: {', '.join(warnings)}")
    postprocess = report.get("postprocess") or {}
    if postprocess:
        lines.append(
            "postprocess: "
            f"changed={postprocess.get('changed')}, "
            f"changed_lines={postprocess.get('changed_lines', 0)}",
        )
    return lines


def _selected_posts_summary(selected_posts_path: Path, limit: int = 8) -> list[str]:
    if not selected_posts_path.exists():
        return []

    try:
        posts = json.loads(selected_posts_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    lines = []
    for index, post in enumerate(posts[:limit], start=1):
        source = post.get("source", "unknown")
        text = " ".join(str(post.get("text", "")).split())
        if len(text) > 120:
            text = f"{text[:117]}..."
        lines.append(f"{index}. @{source}: {text}")
    return lines


def _format_duration(duration_seconds: float) -> str:
    total_seconds = int(round(duration_seconds))
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"
