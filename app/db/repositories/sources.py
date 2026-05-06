from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import SourceChannel


def normalize_username(username: str) -> str:
    return username.strip().lstrip("@")


def get_or_create_source(
    session: Session,
    username: str,
    title: str | None = None,
) -> SourceChannel:
    normalized_username = normalize_username(username)

    source = session.scalar(
        select(SourceChannel).where(SourceChannel.username == normalized_username),
    )
    if source:
        if title and source.title != title:
            source.title = title
            session.commit()
            session.refresh(source)
        return source

    source = SourceChannel(username=normalized_username, title=title)
    session.add(source)
    session.commit()
    session.refresh(source)
    return source


def count_sources(session: Session) -> int:
    return session.scalar(select(func.count(SourceChannel.id))) or 0
