import json
from datetime import datetime, timezone

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Episode, EpisodeDraft, EpisodePost


def create_episode_draft(
    session: Session,
    title: str,
    source_post_ids: list[int],
    markdown_path: str | None = None,
    json_path: str | None = None,
) -> EpisodeDraft:
    episode = EpisodeDraft(
        title=title,
        source_post_ids=json.dumps(source_post_ids),
        markdown_path=markdown_path,
        json_path=json_path,
    )
    session.add(episode)
    session.commit()
    session.refresh(episode)
    return episode


def get_latest_episode_drafts(session: Session, limit: int = 10) -> list[EpisodeDraft]:
    return list(
        session.scalars(
            select(EpisodeDraft).order_by(desc(EpisodeDraft.created_at), desc(EpisodeDraft.id)).limit(limit),
        ).all(),
    )


def get_episode_draft(session: Session, episode_id: int) -> EpisodeDraft | None:
    return session.get(EpisodeDraft, episode_id)


def delete_episode_draft(session: Session, episode_id: int) -> EpisodeDraft | None:
    episode = get_episode_draft(session, episode_id)
    if episode is None:
        return None

    session.delete(episode)
    session.commit()
    return episode


def record_episode_package(
    session: Session,
    *,
    slug: str,
    title: str,
    package_path: str,
    post_ids: list[int],
    audio_path: str | None = None,
    metadata_path: str | None = None,
) -> Episode:
    episode = get_episode_by_slug(session, slug)
    if episode is None:
        episode = Episode(
            slug=slug,
            title=title,
            package_path=package_path,
        )
        session.add(episode)

    episode.title = title
    episode.package_path = package_path
    episode.audio_path = audio_path
    episode.metadata_path = metadata_path
    episode.status = "completed" if audio_path else "draft"

    session.flush()
    for link in list(episode.posts):
        session.delete(link)
    session.flush()
    for position, post_id in enumerate(dict.fromkeys(post_ids), start=1):
        episode.posts.append(
            EpisodePost(
                telegram_post_id=post_id,
                position=position,
            ),
        )
    session.commit()
    session.refresh(episode)
    return episode


def get_episode_by_slug(session: Session, slug: str) -> Episode | None:
    return session.scalar(
        select(Episode)
        .options(selectinload(Episode.posts))
        .where(Episode.slug == slug),
    )


def get_recent_episode_post_ids(
    session: Session,
    *,
    limit: int = 1,
    require_completed: bool = True,
) -> set[int]:
    if limit < 1:
        return set()

    statement = (
        select(Episode)
        .options(selectinload(Episode.posts))
        .order_by(desc(Episode.created_at), desc(Episode.id))
        .limit(limit)
    )
    if require_completed:
        statement = statement.where(Episode.status.in_(("completed", "published")))

    post_ids: set[int] = set()
    for episode in session.scalars(statement).all():
        post_ids.update(link.telegram_post_id for link in episode.posts)
    return post_ids


def mark_episode_published(
    session: Session,
    *,
    slug: str,
    channel_id: str,
    message_id: int,
    published_at: datetime | None = None,
) -> Episode | None:
    episode = get_episode_by_slug(session, slug)
    if episode is None:
        return None

    episode.status = "published"
    episode.telegram_channel_id = channel_id
    episode.telegram_message_id = message_id
    episode.published_at = published_at or datetime.now(timezone.utc)
    session.commit()
    session.refresh(episode)
    return episode
