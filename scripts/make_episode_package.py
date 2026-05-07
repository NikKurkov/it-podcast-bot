import argparse
import sys
from pathlib import Path

from openai import APIConnectionError, InternalServerError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import SessionLocal, init_db
from app.config.settings import settings
from app.pipeline.episode_package import create_episode_package


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create an episode package directory.")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--title", default=None)
    parser.add_argument("--slug", default=None)
    parser.add_argument(
        "--llm-profile",
        choices=("default", "fast", "final"),
        default=None,
        help="Also generate llm_script.md with the selected model profile.",
    )
    parser.add_argument("--with-audio", action="store_true", help="Also create audio.wav and audio.mp3.")
    parser.add_argument("--tts-provider", choices=("silero", "espeak"), default=settings.tts_provider)
    parser.add_argument(
        "--dialogue-script",
        action="store_true",
        help="Use the four-character LLM prompt when --llm-profile is set.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as session:
            package = create_episode_package(
                session,
                limit=args.limit,
                title=args.title,
                slug=args.slug,
                llm_profile=args.llm_profile,
                dialogue_script=args.dialogue_script,
                with_audio=args.with_audio,
                tts_provider=args.tts_provider,
                tts_voice=settings.tts_voice,
                tts_speed=settings.tts_speed,
            )
    except APIConnectionError as exc:
        raise SystemExit(
            "Could not connect to local LLM server. Run `make ollama-cpu` in another terminal "
            "or omit --llm-profile."
        ) from exc
    except InternalServerError as exc:
        if "architectural feature absent" in str(exc) or "CUDA error" in str(exc):
            raise SystemExit(
                "Local LLM server failed inside CUDA. Run `make ollama-cpu` in another terminal."
            ) from exc
        raise

    print(f"Created episode package: {package.path}")
    print(f"  digest: {package.digest_markdown_path}")
    print(f"  selected_posts: {package.selected_posts_path}")
    print(f"  script_draft: {package.script_draft_path}")
    if package.llm_script_path:
        print(f"  llm_script: {package.llm_script_path}")
    if package.audio_mp3_path:
        print(f"  audio_mp3: {package.audio_mp3_path}")
    print(f"  metadata: {package.metadata_path}")


if __name__ == "__main__":
    main()
