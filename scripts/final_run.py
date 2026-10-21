import argparse
import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

from openai import APIConnectionError, InternalServerError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.settings import settings
from app.llm.news_ranker import select_editorial_posts
from app.llm.scriptwriter import model_for_profile
from app.db.repositories.episodes import (
    mark_episode_blocked,
)
from app.db.repositories.posts import get_posts_for_digest, update_editorial_state
from app.db.session import SessionLocal, init_db
from app.pipeline.episode_package import create_episode_package
from app.pipeline.episode_history import get_recent_episode_post_texts
from app.pipeline.episode_report import format_episode_report
from app.pipeline.run_report import (
    format_publication_checks,
    publication_allowed,
    publication_gate_checks,
    write_run_report,
)
from app.pipeline.scoring import (
    diversify_ranked_posts,
    is_podcast_candidate,
    is_similar_to_any_text,
    rank_posts,
)
from app.pipeline.source_weights import load_source_weights
from app.telegram_publisher.publisher import publish_episode_package
from app.telegram_reader.collector import collect_latest_posts
from app.utils.logger import setup_logging
from app.utils.locking import exclusive_lock

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full local episode pipeline.")
    parser.add_argument("--collect-limit", type=int, default=settings.final_collect_limit)
    parser.add_argument("--pool-limit", type=int, default=settings.final_pool_limit)
    parser.add_argument("--top", type=int, default=settings.final_top_posts)
    parser.add_argument("--history-limit", type=int, default=5)
    parser.add_argument("--llm-profile", choices=("default", "fast", "final"), default=None)
    parser.add_argument("--with-audio", action="store_true")
    parser.add_argument(
        "--tts-provider", choices=("silero", "xtts", "espeak"), default=settings.tts_provider
    )
    parser.add_argument(
        "--with-music", action="store_true", default=settings.audio_background_music
    )
    parser.add_argument(
        "--music-volume", type=float, default=settings.audio_background_music_volume
    )
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
    parser.add_argument(
        "--no-research", action="store_true", help="Do not fetch linked source articles."
    )
    parser.add_argument("--slug", default=None)
    parser.add_argument("--target-minutes", type=float, default=settings.podcast_target_minutes)
    parser.add_argument("--lookback-hours", type=float, default=24.0)
    return parser.parse_args()


def main() -> int | None:
    args = parse_args()
    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    with exclusive_lock(log_dir / "pipeline.lock", "Another podcast pipeline is already running."):
        return _run_final(args)


def _run_final(args: argparse.Namespace) -> int | None:
    setup_logging()
    package = None
    collect_stats = {}
    selected_count = None
    selection_diagnostics = {}
    publication_checks = []
    publish_result = None

    try:
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
            collect_stats = asyncio.run(
                collect_latest_posts(
                    limit_per_channel=args.collect_limit,
                    interactive=False,
                    since=datetime.now(timezone.utc) - timedelta(hours=args.lookback_hours),
                ),
            )

        with SessionLocal() as session:
            selected_count = _auto_select_posts(
                session,
                pool_limit=args.pool_limit,
                top=args.top,
                history_limit=args.history_limit,
                lookback_hours=args.lookback_hours,
                llm_profile=args.llm_profile,
                diagnostics=selection_diagnostics,
            )
            if selected_count == 0:
                write_run_report(
                    status="blocked",
                    output_dir=Path("data/logs"),
                    collect_stats=collect_stats,
                    selected_count=selected_count,
                    requested_top=args.top,
                    selection_diagnostics=selection_diagnostics,
                    error="Publication blocked before audio: not enough selected posts.",
                )
                print("Publication blocked before audio:")
                print(f"  selected_posts: {selected_count}/{args.top}")
                print("  need at least: 1 meaningful fresh story")
                return 2
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
                    target_minutes=args.target_minutes,
                    research=False if args.no_research else None,
                    ordered_post_ids=selection_diagnostics.get("selected_post_ids"),
                )
            except APIConnectionError as exc:
                raise SystemExit(
                    "Could not connect to local LLM server. Run `make ollama-cpu` in another terminal "
                    "or run without --llm-profile."
                ) from exc
            except InternalServerError as exc:
                if "architectural feature absent" in str(exc) or "CUDA error" in str(exc):
                    raise SystemExit(
                        "Ollama CUDA failed. Run `make ollama-cpu` in another terminal."
                    ) from exc
                raise

        print("Final run complete:")
        print(
            format_episode_report(
                package, collect_stats=collect_stats, selected_count=selected_count
            )
        )
        if args.publish:
            publication_checks = publication_gate_checks(
                package,
                selected_count=selected_count,
                requested_top=args.top,
            )
            print(format_publication_checks(publication_checks))
            if not publication_allowed(publication_checks):
                write_run_report(
                    status="blocked",
                    output_dir=package.path,
                    collect_stats=collect_stats,
                    selected_count=selected_count,
                    requested_top=args.top,
                    package=package,
                    publication_checks=publication_checks,
                    selection_diagnostics=selection_diagnostics,
                    error="Publication blocked by safety checks.",
                )
                _mark_package_blocked(package.path)
                print("Publication blocked by safety checks.")
                return 2
            result = asyncio.run(
                publish_episode_package(package.path, channel_id=args.publish_channel_id),
            )
            publish_result = {
                "channel_id": result.channel_id,
                "message_id": result.message_id,
                "audio_path": str(result.audio_path),
            }
            print("Telegram publish complete:")
            print(f"  channel_id: {result.channel_id}")
            print(f"  message_id: {result.message_id}")
            print(f"  audio: {result.audio_path}")
        write_run_report(
            status="published" if publish_result else "complete",
            output_dir=package.path,
            collect_stats=collect_stats,
            selected_count=selected_count,
            requested_top=args.top,
            package=package,
            publish_result=publish_result,
            publication_checks=publication_checks,
            selection_diagnostics=selection_diagnostics,
        )
    except BaseException as exc:
        write_run_report(
            status="failed",
            output_dir=package.path if package else Path("data/logs"),
            collect_stats=collect_stats,
            selected_count=selected_count,
            requested_top=args.top,
            selection_diagnostics=selection_diagnostics,
            package=package,
            publication_checks=publication_checks,
            publish_result=publish_result,
            error=str(exc),
        )
        raise


def _auto_select_posts(
    session,
    pool_limit: int,
    top: int,
    history_limit: int = 5,
    diagnostics: dict | None = None,
    lookback_hours: float = 24.0,
    llm_profile: str | None = None,
) -> int:
    existing_posts = get_posts_for_digest(
        session, limit=10_000, include_rejected=True, only_selected=True
    )
    update_editorial_state(session, [post.id for post in existing_posts], selected=False)

    best_selected_ranked_posts, best_attempt = _build_selection(
        session,
        pool_limit=pool_limit,
        top=top,
        history_limit=history_limit,
        lookback_hours=lookback_hours,
        editorial_model=model_for_profile(llm_profile) if llm_profile else None,
    )
    attempts = [best_attempt]

    selected_posts = [ranked_post.post for ranked_post in best_selected_ranked_posts]
    for ranked_post in best_selected_ranked_posts:
        update_editorial_state(
            session,
            [ranked_post.post.id],
            selected=True,
            category="top news",
            editor_note=_build_editor_note(ranked_post),
        )
    if diagnostics is not None:
        diagnostics.clear()
        diagnostics.update(
            {
                "minimum_selected": 1,
                "selected_post_ids": [post.id for post in selected_posts],
                "selected_attempt": best_attempt or {},
                "attempts": attempts,
            },
        )
    return len(selected_posts)


def _build_selection(
    session,
    *,
    pool_limit: int,
    top: int,
    history_limit: int,
    lookback_hours: float,
    editorial_model: str | None = None,
) -> tuple[list, dict]:
    previous_episode_texts = get_recent_episode_post_texts(limit=history_limit)
    posts = get_posts_for_digest(
        session,
        limit=pool_limit,
        since=datetime.now(timezone.utc) - timedelta(hours=lookback_hours),
    )
    pool_count = len(posts)
    after_recent_ids_count = len(posts)
    if previous_episode_texts:
        posts = [
            post for post in posts if not is_similar_to_any_text(post.text, previous_episode_texts)
        ]
    after_similarity_count = len(posts)
    ranked_posts = rank_posts(posts, source_weights=load_source_weights())
    candidate_ranked_posts = [
        ranked_post for ranked_post in ranked_posts if is_podcast_candidate(ranked_post)
    ]
    selection_method = "heuristic"
    if editorial_model:
        candidate_ranked_posts = select_editorial_posts(
            ranked_posts, limit=top, model=editorial_model
        )
        selection_method = "llm"
    selected_ranked_posts = diversify_ranked_posts(candidate_ranked_posts, limit=top)
    attempt = {
        "history_limit": history_limit,
        "lookback_hours": lookback_hours,
        "selection_method": selection_method,
        "pool": pool_count,
        "after_recent_ids": after_recent_ids_count,
        "after_similarity": after_similarity_count,
        "candidates": len(candidate_ranked_posts),
        "selected": len(selected_ranked_posts),
    }
    return selected_ranked_posts, attempt


def _mark_package_blocked(package_path: Path) -> None:
    with SessionLocal() as session:
        mark_episode_blocked(session, slug=package_path.name)


def _build_editor_note(ranked_post) -> str:
    reasons = "; ".join(ranked_post.reasons[:3]) if ranked_post.reasons else "no strong reasons"
    topics = f" Topics: {', '.join(ranked_post.topics)}." if ranked_post.topics else ""
    penalties = (
        f" Penalties: {'; '.join(ranked_post.penalties[:2])}." if ranked_post.penalties else ""
    )
    return (
        f"Auto-selected by final run score={ranked_post.score:.2f}. "
        f"Reasons: {reasons}.{topics}{penalties}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
