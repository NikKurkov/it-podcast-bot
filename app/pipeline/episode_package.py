import json
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import TelegramPost
from app.db.repositories.episodes import record_episode_package
from app.db.repositories.posts import get_selected_posts
from app.audio.assembler import assemble_podcast
from app.audio.dialogue import script_to_dialogue_lines
from app.audio.inspection import write_audio_report
from app.audio.music import mix_background_music
from app.audio.tts import convert_wav_to_mp3, synthesize_dialogue_lines, synthesize_with_espeak
from app.config.settings import settings
from app.llm.scriptwriter import (
    edit_validated_dialogue_script,
    model_for_profile,
    rewrite_chunked_dialogue_script_draft,
    rewrite_script_draft,
    rewrite_validated_dialogue_script_draft,
)
from app.pipeline.daily_digest import (
    DigestItem,
    export_digest_json,
    export_digest_markdown,
)
from app.pipeline.script_draft import export_script_markdown
from app.pipeline.publication import write_episode_metadata, write_show_notes
from app.podcast.script_quality import (
    ensure_opening_and_rundown,
    postprocess_dialogue_script,
    write_script_quality_report,
)


@dataclass(frozen=True)
class EpisodePackage:
    path: Path
    digest_markdown_path: Path
    selected_posts_path: Path
    script_draft_path: Path
    llm_script_path: Path | None
    audio_wav_path: Path | None
    audio_mp3_path: Path | None
    audio_voice_wav_path: Path | None
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
    with_music: bool = False,
    music_volume: float | None = None,
    music_path: Path | None = None,
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
    audio_voice_wav_path = package_path / "audio_voice.wav" if with_audio and with_music else None
    audio_report_path = package_path / "audio_report.json" if with_audio else None
    script_quality_report_path = package_path / "script_quality_report.json" if llm_profile else None
    show_notes_path = package_path / "show_notes.md"
    episode_metadata_path = package_path / "episode_metadata.json"
    metadata_path = package_path / "metadata.json"

    export_digest_markdown(digest_items, digest_markdown_path)
    export_digest_json(digest_items, selected_posts_path)
    export_script_markdown(posts, script_draft_path, package_title)

    llm_model = None
    script_validation_issues = []
    script_editor_validation_issues = []
    script_editor_applied = False
    if llm_profile:
        llm_model = model_for_profile(llm_profile)
        draft_text = script_draft_path.read_text(encoding="utf-8")
        if dialogue_script:
            script_generation_model = llm_model
            if settings.llm_chunked_script_enabled:
                script_generation_model = settings.llm_chunked_model or llm_model
                llm_text, validation = rewrite_chunked_dialogue_script_draft(
                    draft_text,
                    model=script_generation_model,
                    chunk_size=settings.llm_script_chunk_size,
                )
            else:
                llm_text, validation = rewrite_validated_dialogue_script_draft(
                    draft_text,
                    model=llm_model,
                    attempts=4,
                    allow_quality_fallback=True,
                )
            script_validation_issues = [
                {
                    "severity": issue.severity,
                    "message": issue.message,
                    "line_number": issue.line_number,
                }
                for issue in validation.issues
            ]
            if validation.has_structural_blocking_issues:
                messages = "; ".join(issue.message for issue in validation.issues)
                raise RuntimeError(f"Generated dialogue script failed validation: {messages}")
            if settings.llm_script_editor_enabled and not settings.llm_chunked_script_enabled:
                edited_text, editor_validation = edit_validated_dialogue_script(
                    llm_text,
                    source_draft=draft_text,
                    model=script_generation_model,
                    attempts=2,
                )
                script_editor_applied = edited_text != llm_text
                script_editor_validation_issues = [
                    {
                        "severity": issue.severity,
                        "message": issue.message,
                        "line_number": issue.line_number,
                    }
                    for issue in editor_validation.issues
                ]
                llm_text = edited_text
            llm_text = ensure_opening_and_rundown(
                llm_text,
                topic_summaries=[item.text for item in digest_items],
            )
            postprocess_result = postprocess_dialogue_script(llm_text)
            llm_text = postprocess_result.script_text
            write_script_quality_report(postprocess_result.report, script_quality_report_path)
        else:
            llm_text = rewrite_script_draft(draft_text, model=llm_model)
        llm_script_path.write_text(llm_text + "\n", encoding="utf-8")

    if with_audio:
        audio_source_path = llm_script_path if llm_script_path and llm_script_path.exists() else script_draft_path
        provider_name = (tts_provider or settings.tts_provider).strip().lower()
        if provider_name in {"silero", "xtts"}:
            dialogue_lines = script_to_dialogue_lines(audio_source_path.read_text(encoding="utf-8"))
            rendered_lines = asyncio.run(
                synthesize_dialogue_lines(
                    dialogue_lines,
                    package_path / "audio_lines",
                    provider_name=provider_name,
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
        if with_music:
            clean_voice_path = audio_voice_wav_path
            audio_wav_path.replace(audio_voice_wav_path)
            mix_background_music(
                clean_voice_path,
                audio_wav_path,
                music_path=music_path,
                music_volume=music_volume or settings.audio_background_music_volume,
                sample_rate=settings.tts_sample_rate,
            )
        convert_wav_to_mp3(audio_wav_path, audio_mp3_path)
        report_paths = [audio_wav_path, audio_mp3_path]
        if audio_voice_wav_path and audio_voice_wav_path.exists():
            report_paths.append(audio_voice_wav_path)
        write_audio_report(report_paths, audio_report_path)

    metadata = {
        "title": package_title,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "posts_count": len(posts),
        "post_ids": [post.id for post in posts],
        "llm_profile": llm_profile,
        "llm_model": llm_model,
        "llm_script_generation_model": script_generation_model if llm_profile and dialogue_script else llm_model,
        "llm_chunked_script_enabled": settings.llm_chunked_script_enabled if dialogue_script else None,
        "llm_script_chunk_size": settings.llm_script_chunk_size if dialogue_script else None,
        "dialogue_script": dialogue_script,
        "script_validation_issues": script_validation_issues,
        "script_editor_enabled": settings.llm_script_editor_enabled if dialogue_script else None,
        "script_editor_applied": script_editor_applied if dialogue_script else None,
        "script_editor_validation_issues": script_editor_validation_issues
        if dialogue_script
        else None,
        "tts_provider": (tts_provider or settings.tts_provider) if with_audio else None,
        "background_music": with_music if with_audio else None,
        "background_music_volume": (music_volume or settings.audio_background_music_volume)
        if with_audio and with_music
        else None,
        "background_music_path": str(music_path) if with_audio and with_music and music_path else None,
        "files": {
            "digest_markdown": str(digest_markdown_path),
            "selected_posts": str(selected_posts_path),
            "script_draft": str(script_draft_path),
            "llm_script": str(llm_script_path) if llm_script_path else None,
            "audio_wav": str(audio_wav_path) if audio_wav_path else None,
            "audio_mp3": str(audio_mp3_path) if audio_mp3_path else None,
            "audio_voice_wav": str(audio_voice_wav_path) if audio_voice_wav_path else None,
            "audio_report": str(audio_report_path) if audio_report_path else None,
            "script_quality_report": str(script_quality_report_path)
            if script_quality_report_path
            else None,
            "show_notes": str(show_notes_path),
            "episode_metadata": str(episode_metadata_path),
        },
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_show_notes(
        title=package_title,
        digest_items=digest_items,
        output_path=show_notes_path,
        audio_report_path=audio_report_path,
    )
    write_episode_metadata(
        title=package_title,
        created_at=metadata["created_at"],
        digest_items=digest_items,
        output_path=episode_metadata_path,
        audio_path=audio_mp3_path,
        audio_report_path=audio_report_path,
        llm_model=llm_model,
        tts_provider=(tts_provider or settings.tts_provider) if with_audio else None,
        background_music=with_music if with_audio else None,
    )
    record_episode_package(
        session,
        slug=package_path.name,
        title=package_title,
        package_path=str(package_path),
        post_ids=[post.id for post in posts],
        audio_path=str(audio_mp3_path) if audio_mp3_path and audio_mp3_path.exists() else None,
        metadata_path=str(metadata_path),
    )

    return EpisodePackage(
        path=package_path,
        digest_markdown_path=digest_markdown_path,
        selected_posts_path=selected_posts_path,
        script_draft_path=script_draft_path,
        llm_script_path=llm_script_path,
        audio_wav_path=audio_wav_path,
        audio_mp3_path=audio_mp3_path,
        audio_voice_wav_path=audio_voice_wav_path,
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
