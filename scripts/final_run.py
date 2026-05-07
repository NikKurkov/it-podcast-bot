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
from app.pipeline.filters import filter_excluded_items, load_exclude_keywords
from app.pipeline.scoring import rank_posts
from app.telegram_reader.collector import collect_latest_posts
from app.utils.logger import setup_logging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full local episode pipeline.")
    parser.add_argument("--collect-limit", type=int, default=20)
    parser.add_argument("--pool-limit", type=int, default=50)
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--llm-profile", choices=("default", "fast", "final"), default=None)
    parser.add_argument("--with-audio", action="store_true")
    parser.add_argument("--tts-provider", choices=("silero", "espeak"), default=settings.tts_provider)
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
                with_audio=args.with_audio,
                tts_provider=args.tts_provider,
                tts_voice=settings.tts_voice,
                tts_speed=settings.tts_speed,
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
    for key, value in collect_stats.items():
        print(f"  {key}: {value}")
    print(f"  selected_posts: {selected_count}")
    print(f"  package: {package.path}")


def _auto_select_posts(session, pool_limit: int, top: int) -> int:
    existing_posts = get_posts_for_digest(session, limit=10_000, include_rejected=True)
    update_editorial_state(session, [post.id for post in existing_posts], selected=False)

    posts = get_posts_for_digest(session, limit=pool_limit)
    ranked_posts = [ranked_post.post for ranked_post in rank_posts(posts)]
    ranked_posts = filter_excluded_items(ranked_posts, load_exclude_keywords())
    selected_posts = ranked_posts[:top]
    update_editorial_state(
        session,
        [post.id for post in selected_posts],
        selected=True,
        category="top news",
        editor_note="Auto-selected by final run",
    )
    return len(selected_posts)


if __name__ == "__main__":
    main()
