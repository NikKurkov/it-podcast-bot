import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convenience runner for the local podcast pipeline.")
    parser.add_argument("--fresh", action="store_true", help="Clean generated data before running.")
    parser.add_argument("--no-collect", action="store_true", help="Reuse already collected posts.")
    parser.add_argument("--script-only", action="store_true", help="Generate package and script without audio.")
    parser.add_argument("--audio-only", action="store_true", help="Render audio for the latest package.")
    parser.add_argument("--remix-only", action="store_true", help="Only remix music for the latest package.")
    parser.add_argument("--audio", action="store_true", help="Generate audio too.")
    parser.add_argument("--with-music", action="store_true", help="Mix background music into audio.")
    parser.add_argument("--tts-provider", choices=("silero", "xtts", "espeak"), default="xtts")
    parser.add_argument("--llm-profile", choices=("default", "fast", "final"), default="final")
    parser.add_argument("--collect-limit", type=int, default=None)
    parser.add_argument("--pool-limit", type=int, default=None)
    parser.add_argument("--top", type=int, default=None)
    parser.add_argument("--slug", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    python = PROJECT_ROOT / ".venv" / "bin" / "python"

    if args.audio_only or args.remix_only:
        render_args = [
            str(python),
            "scripts/render_episode_audio.py",
            "--episode",
            "latest",
            "--provider",
            args.tts_provider,
        ]
        if args.with_music or args.remix_only:
            render_args.append("--with-music")
        if args.remix_only:
            render_args.append("--remix-only")
        _run(render_args)
        return

    if args.fresh:
        _run([str(python), "scripts/clean_workspace.py", "--yes"])

    final_args = [
        str(python),
        "scripts/final_run.py",
        "--llm-profile",
        args.llm_profile,
        "--dialogue-script",
    ]
    if args.no_collect:
        final_args.append("--no-collect")
    if args.audio or args.with_music or not args.script_only:
        final_args.extend(["--with-audio", "--tts-provider", args.tts_provider])
    if args.with_music:
        final_args.append("--with-music")
    if args.collect_limit is not None:
        final_args.extend(["--collect-limit", str(args.collect_limit)])
    if args.pool_limit is not None:
        final_args.extend(["--pool-limit", str(args.pool_limit)])
    if args.top is not None:
        final_args.extend(["--top", str(args.top)])
    if args.slug:
        final_args.extend(["--slug", args.slug])

    _run(final_args)


def _run(args: list[str]) -> None:
    subprocess.run(args, cwd=PROJECT_ROOT, check=True)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc
