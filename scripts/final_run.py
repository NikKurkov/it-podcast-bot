import argparse
import asyncio
import sys
from pathlib import Path

from openai import APIConnectionError, InternalServerError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.settings import settings
from app.db.repositories.posts import get_posts_for_digest, update_editorial_state
from app.db.session import SessionLocal, init_db
from app.pipeline.episode_package import create_episode_package
from app.pipeline.filters import contains_excluded_keyword, load_exclude_keywords
from app.pipeline.episode_report import format_episode_report
from app.pipeline.scoring import diversify_ranked_posts, rank_posts
from app.pipeline.source_weights import load_source_weights
from app.telegram_publisher.publisher import publish_episode_package
from app.telegram_reader.collector import collect_latest_posts
from app.utils.logger import setup_logging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full local episode pipeline.")
    parser.add_argument("--collect-limit", type=int, default=settings.final_collect_limit)
    parser.add_argument("--pool-limit", type=int, default=settings.final_pool_limit)
    parser.add_argument("--top", type=int, default=settings.final_top_posts)
    parser.add_argument("--llm-profile", choices=("default", "fast", "final"), default=None)
    parser.add_argument("--with-audio", action="store_true")
    parser.add_argument("--tts-provider", choices=("silero", "xtts", "espeak"), default=settings.tts_provider)
    parser.add_argument("--with-music", action="store_true", default=settings.audio_background_music)
    parser.add_argument("--music-volume", type=float, default=settings.audio_background_music_volume)
    parser.add_argument("--music-path", default=settings.audio_background_music_path)
    parser.add_argument(
        "--publish",
        action=argparse.BooleanOptionalAction,
        default=settings.publish_telegram_on_final,
        help="Publish generated audio.mp3 to TELEGRAM_PUBLISH_CHANNEL_ID.",
    )
    parser.add_argument("--publish-channel-id", default=settings.telegram_publish_channel_id)
    parser.add_argument(
        "--dialogue-script",
        action="store_true",
        help="Use the four-character LLM prompt when --llm-profile is set.",
    )
    parser.add_argument("--no-collect", action="store_true", help="Skip Telegram collection step.")
    parser.add_argument("--slug", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging()
    init_db()

    if args.no_collect:
        collect_stats = {
            "channels_total": 0,
            "channels_ok": 0,
            "channels_failed": 0,
            "posts_seen": 0,
            "posts_saved": 0,
            "posts_skipped": 0,
        }
    else:
        collect_stats = asyncio.run(collect_latest_posts(limit_per_channel=args.collect_limit))

    with SessionLocal() as session:
        selected_count = _auto_select_posts(session, pool_limit=args.pool_limit, top=args.top)
        try:
            package = create_episode_package(
                session,
                limit=args.top,
                slug=args.slug,
                llm_profile=args.llm_profile,
                dialogue_script=args.dialogue_script,
                with_audio=args.with_audio,
                tts_provider=args.tts_provider,
                tts_voice=settings.tts_voice,
                tts_speed=settings.tts_speed,
                with_music=args.with_music,
                music_volume=args.music_volume,
                music_path=Path(args.music_path) if args.music_path else None,
            )
        except APIConnectionError as exc:
            raise SystemExit(
                "Could not connect to local LLM server. Run `make ollama-cpu` in another terminal "
                "or run without --llm-profile."
            ) from exc
        except InternalServerError as exc:
            if "architectural feature absent" in str(exc) or "CUDA error" in str(exc):
                raise SystemExit("Ollama CUDA failed. Run `make ollama-cpu` in another terminal.") from exc
            raise

    print("Final run complete:")
    print(format_episode_report(package, collect_stats=collect_stats, selected_count=selected_count))
    if args.publish:
        result = asyncio.run(
            publish_episode_package(package.path, channel_id=args.publish_channel_id),
        )
        print("Telegram publish complete:")
        print(f"  channel_id: {result.channel_id}")
        print(f"  message_id: {result.message_id}")
        print(f"  audio: {result.audio_path}")


def _auto_select_posts(session, pool_limit: int, top: int) -> int:
    existing_posts = get_posts_for_digest(session, limit=10_000, include_rejected=True)
    update_editorial_state(session, [post.id for post in existing_posts], selected=False)

    posts = get_posts_for_digest(session, limit=pool_limit)
    ranked_posts = rank_posts(posts, source_weights=load_source_weights())
    keywords = load_exclude_keywords()
    ranked_posts = [
        ranked_post
        for ranked_post in ranked_posts
        if not contains_excluded_keyword(ranked_post.post.text, keywords)
    ]
    selected_ranked_posts = diversify_ranked_posts(ranked_posts, limit=top)
    selected_posts = [ranked_post.post for ranked_post in selected_ranked_posts]
    for ranked_post in selected_ranked_posts:
        update_editorial_state(
            session,
            [ranked_post.post.id],
            selected=True,
            category="top news",
            editor_note=_build_editor_note(ranked_post),
        )
    return len(selected_posts)


def _build_editor_note(ranked_post) -> str:
    reasons = "; ".join(ranked_post.reasons[:3]) if ranked_post.reasons else "no strong reasons"
    topics = f" Topics: {', '.join(ranked_post.topics)}." if ranked_post.topics else ""
    penalties = (
        f" Penalties: {'; '.join(ranked_post.penalties[:2])}."
        if ranked_post.penalties
        else ""
    )
    return (
        f"Auto-selected by final run score={ranked_post.score:.2f}. "
        f"Reasons: {reasons}.{topics}{penalties}"
    )


if __name__ == "__main__":
    main()
