import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.pipeline.episode_paths import resolve_episode_path

from app.pipeline.episode_package import EpisodePackage
from app.pipeline.episode_report import format_episode_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show a compact report for an episode package.")
    parser.add_argument("--episode", default="latest", help="Episode directory or `latest`.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    episode_path = _resolve_episode_path(args.episode)
    package = _package_from_path(episode_path)
    selected_count = _selected_count(package.selected_posts_path)
    print(
        format_episode_report(
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
        ),
    )


def _resolve_episode_path(value: str) -> Path:
    return resolve_episode_path(value, PROJECT_ROOT)


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
        return len(json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError:
        return 0


if __name__ == "__main__":
    main()
