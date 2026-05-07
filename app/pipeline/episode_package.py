import json
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import TelegramPost
from app.db.repositories.posts import get_selected_posts
from app.audio.assembler import assemble_podcast
from app.audio.dialogue import script_to_dialogue_lines
from app.audio.tts import convert_wav_to_mp3, synthesize_dialogue_lines, synthesize_with_espeak
from app.config.settings import settings
from app.llm.scriptwriter import (
    model_for_profile,
    rewrite_dialogue_script_draft,
    rewrite_script_draft,
)
from app.pipeline.daily_digest import (
    DigestItem,
    export_digest_json,
    export_digest_markdown,
)
from app.pipeline.script_draft import export_script_markdown


@dataclass(frozen=True)
class EpisodePackage:
    path: Path
    digest_markdown_path: Path
    selected_posts_path: Path
    script_draft_path: Path
    llm_script_path: Path | None
    audio_wav_path: Path | None
    audio_mp3_path: Path | None
    metadata_path: Path


def create_episode_package(
    session: Session,
    limit: int = 10,
    title: str | None = None,
    slug: str | None = None,
    llm_profile: str | None = None,
    dialogue_script: bool = False,
    with_audio: bool = False,
    tts_provider: str | None = None,
    tts_voice: str = "ru",
    tts_speed: int = 160,
) -> EpisodePackage:
    package_title = title or f"IT podcast {datetime.now(timezone.utc).date().isoformat()}"
    package_path = Path("data/episodes") / _build_package_slug(slug)
    package_path.mkdir(parents=True, exist_ok=True)

    posts = get_selected_posts(session, limit=limit)
    digest_items = [_post_to_digest_item(post) for post in posts]

    digest_markdown_path = package_path / "digest.md"
    selected_posts_path = package_path / "selected_posts.json"
    script_draft_path = package_path / "script_draft.md"
    llm_script_path = package_path / "llm_script.md" if llm_profile else None
    audio_wav_path = package_path / "audio.wav" if with_audio else None
    audio_mp3_path = package_path / "audio.mp3" if with_audio else None
    metadata_path = package_path / "metadata.json"

    export_digest_markdown(digest_items, digest_markdown_path)
    export_digest_json(digest_items, selected_posts_path)
    export_script_markdown(posts, script_draft_path, package_title)

    llm_model = None
    if llm_profile:
        llm_model = model_for_profile(llm_profile)
        draft_text = script_draft_path.read_text(encoding="utf-8")
        if dialogue_script:
            llm_text = rewrite_dialogue_script_draft(draft_text, model=llm_model)
        else:
            llm_text = rewrite_script_draft(draft_text, model=llm_model)
        llm_script_path.write_text(llm_text + "\n", encoding="utf-8")

    if with_audio:
        audio_source_path = llm_script_path if llm_script_path and llm_script_path.exists() else script_draft_path
        provider_name = (tts_provider or settings.tts_provider).strip().lower()
        if provider_name == "silero":
            dialogue_lines = script_to_dialogue_lines(audio_source_path.read_text(encoding="utf-8"))
            rendered_lines = asyncio.run(
                synthesize_dialogue_lines(
                    dialogue_lines,
                    package_path / "audio_lines",
                ),
            )
            assemble_podcast(
                rendered_lines,
                audio_wav_path,
                pauses_ms=[line.pause_after_ms for line in dialogue_lines],
            )
        elif provider_name == "espeak":
            synthesize_with_espeak(
                audio_source_path.read_text(encoding="utf-8"),
                audio_wav_path,
                voice=tts_voice,
                speed=tts_speed,
            )
        else:
            raise ValueError(f"Unsupported episode audio provider: {provider_name}")
        convert_wav_to_mp3(audio_wav_path, audio_mp3_path)

    metadata = {
        "title": package_title,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "posts_count": len(posts),
        "post_ids": [post.id for post in posts],
        "llm_profile": llm_profile,
        "llm_model": llm_model,
        "dialogue_script": dialogue_script,
        "tts_provider": (tts_provider or settings.tts_provider) if with_audio else None,
        "files": {
            "digest_markdown": str(digest_markdown_path),
            "selected_posts": str(selected_posts_path),
            "script_draft": str(script_draft_path),
            "llm_script": str(llm_script_path) if llm_script_path else None,
            "audio_wav": str(audio_wav_path) if audio_wav_path else None,
            "audio_mp3": str(audio_mp3_path) if audio_mp3_path else None,
        },
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return EpisodePackage(
        path=package_path,
        digest_markdown_path=digest_markdown_path,
        selected_posts_path=selected_posts_path,
        script_draft_path=script_draft_path,
        llm_script_path=llm_script_path,
        audio_wav_path=audio_wav_path,
        audio_mp3_path=audio_mp3_path,
        metadata_path=metadata_path,
    )


def _build_package_slug(slug: str | None) -> str:
    if slug:
        return slug

    return datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")


def _post_to_digest_item(post: TelegramPost) -> DigestItem:
    return DigestItem(
        post_id=post.id,
        source=post.source_channel.username,
        title=post.source_channel.title,
        message_date=post.message_date,
        text=post.text,
        url=post.url,
        views=post.views,
        forwards=post.forwards,
        score=None,
    )
