import json

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import EpisodeDraft


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
