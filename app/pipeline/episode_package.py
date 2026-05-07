import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import TelegramPost
from app.db.repositories.posts import get_selected_posts
from app.llm.scriptwriter import model_for_profile, rewrite_script_draft
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
    metadata_path: Path


def create_episode_package(
    session: Session,
    limit: int = 10,
    title: str | None = None,
    slug: str | None = None,
    llm_profile: str | None = None,
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
    metadata_path = package_path / "metadata.json"

    export_digest_markdown(digest_items, digest_markdown_path)
    export_digest_json(digest_items, selected_posts_path)
    export_script_markdown(posts, script_draft_path, package_title)

    llm_model = None
    if llm_profile:
        llm_model = model_for_profile(llm_profile)
        llm_text = rewrite_script_draft(
            script_draft_path.read_text(encoding="utf-8"),
            model=llm_model,
        )
        llm_script_path.write_text(llm_text + "\n", encoding="utf-8")

    metadata = {
        "title": package_title,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "posts_count": len(posts),
        "post_ids": [post.id for post in posts],
        "llm_profile": llm_profile,
        "llm_model": llm_model,
        "files": {
            "digest_markdown": str(digest_markdown_path),
            "selected_posts": str(selected_posts_path),
            "script_draft": str(script_draft_path),
            "llm_script": str(llm_script_path) if llm_script_path else None,
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
