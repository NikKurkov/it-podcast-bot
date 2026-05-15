import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.audio.dialogue import script_to_dialogue_lines
from app.pipeline.episode_package import EpisodePackage
from app.pipeline.episode_report import format_episode_report
from app.podcast.script_quality import build_script_quality_report, quality_gate_allows_tts

MAX_TTS_TEXT_CHARS = 170


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show a pre-TTS quality report for an episode package.")
    parser.add_argument("--episode", default="latest", help="Episode directory or `latest`.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if quality gate or TTS risk fails.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    episode_path = _resolve_episode_path(args.episode)
    package = _package_from_path(episode_path)
    selected_count = _selected_count(package.selected_posts_path)
    report = format_episode_report(
        package,
        collect_stats={
            "channels_total": 0,
            "channels_ok": 0,
            "channels_failed": 0,
            "posts_seen": 0,
            "posts_saved": 0,
            "posts_skipped": 0,
        },
        selected_count=selected_count,
    )
    script_report = _script_report(package.llm_script_path)
    tts_risks = _tts_risks(package.llm_script_path)

    print("Podcast check:")
    print(report)
    if script_report:
        allowed, blocking = quality_gate_allows_tts(script_report)
        print("")
        print("TTS gate:")
        print(f"  ready: {allowed}")
        print(f"  blocking: {', '.join(blocking) if blocking else 'none'}")
    if tts_risks:
        print("")
        print("TTS risks:")
        for risk in tts_risks:
            print(f"  - {risk}")

    if args.strict:
        blocking = []
        if script_report:
            allowed, gate_blocking = quality_gate_allows_tts(script_report)
            if not allowed:
                blocking.extend(gate_blocking)
        if tts_risks:
            blocking.append("tts_risks")
        if blocking:
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


def _package_from_path(path: Path) -> EpisodePackage:
    return EpisodePackage(
        path=path,
        digest_markdown_path=path / "digest.md",
        selected_posts_path=path / "selected_posts.json",
        script_draft_path=path / "script_draft.md",
        llm_script_path=path / "llm_script.md",
        audio_wav_path=path / "audio.wav",
        audio_mp3_path=path / "audio.mp3",
        audio_voice_wav_path=path / "audio_voice.wav",
        metadata_path=path / "metadata.json",
    )


def _selected_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return 0
    return len(payload) if isinstance(payload, list) else 0


def _script_report(script_path: Path | None) -> dict | None:
    if not script_path or not script_path.exists():
        return None
    return build_script_quality_report(script_path.read_text(encoding="utf-8"))


def _tts_risks(script_path: Path | None) -> list[str]:
    if not script_path or not script_path.exists():
        return ["llm_script.md is missing"]

    risks = []
    lines = script_to_dialogue_lines(script_path.read_text(encoding="utf-8"))
    for index, line in enumerate(lines, start=1):
        if len(line.text) > MAX_TTS_TEXT_CHARS:
            risks.append(
                f"line {index} by {line.speaker} is {len(line.text)} chars "
                f"(>{MAX_TTS_TEXT_CHARS})",
            )
    if not lines:
        risks.append("script has no speakable dialogue lines")
    return risks


if __name__ == "__main__":
    main()
