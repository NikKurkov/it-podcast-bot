import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.podcast.script_quality import (
    build_script_quality_report,
    ensure_opening_and_rundown,
    quality_gate_allows_tts,
    write_script_quality_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check dialogue script quality before TTS.")
    parser.add_argument("--episode", default="latest", help="Episode directory or `latest`.")
    parser.add_argument("--fix", action="store_true", help="Write deterministic opening/rundown fixes.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if TTS quality gate fails.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    episode_path = _resolve_episode_path(args.episode)
    script_path = episode_path / "llm_script.md"
    if not script_path.exists():
        raise SystemExit(f"Script does not exist: {script_path}")

    script_text = script_path.read_text(encoding="utf-8")
    if args.fix:
        script_text = ensure_opening_and_rundown(
            script_text,
            topic_summaries=_topic_summaries(episode_path / "selected_posts.json"),
        )
        script_path.write_text(script_text.rstrip() + "\n", encoding="utf-8")

    report = build_script_quality_report(script_text)
    report_path = episode_path / "script_quality_report.json"
    write_script_quality_report(report, report_path)
    allowed, blocking = quality_gate_allows_tts(report)

    print(f"Script quality report: {report_path}")
    print(f"  lines: {report['lines_count']}")
    print(f"  opening: {report['opening_present']}")
    print(f"  rundown: {report['rundown_present']}")
    print(f"  transitions: {report['transition_lines']}")
    print(f"  warnings: {', '.join(report['warnings']) if report['warnings'] else 'none'}")
    print(f"  tts_ready: {allowed}")
    if blocking:
        print(f"  blocking: {', '.join(blocking)}")
    if args.strict and not allowed:
        raise SystemExit(1)


def _resolve_episode_path(value: str) -> Path:
    if value != "latest":
        path = Path(value)
        return path if path.is_absolute() else PROJECT_ROOT / path

    episodes_dir = PROJECT_ROOT / "data" / "episodes"
    candidates = [path for path in episodes_dir.iterdir() if path.is_dir()]
    if not candidates:
        raise SystemExit("No episode packages found in data/episodes.")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _topic_summaries(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        posts = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return [str(post.get("text", "")) for post in posts]


if __name__ == "__main__":
    main()
