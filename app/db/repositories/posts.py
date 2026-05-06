from datetime import datetime
from typing import TypedDict

from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import SourceChannel, TelegramPost
from app.utils.hashing import make_text_hash
from app.utils.text import normalize_text


class TelegramPostData(TypedDict, total=False):
    telegram_message_id: int
    message_date: datetime
    text: str
    views: int | None
    forwards: int | None
    url: str | None
    raw_json: str | None


def post_exists(
    session: Session,
    source_channel_id: int,
    telegram_message_id: int,
) -> bool:
    return session.scalar(
        select(TelegramPost.id).where(
            TelegramPost.source_channel_id == source_channel_id,
            TelegramPost.telegram_message_id == telegram_message_id,
        ),
    ) is not None


def save_post(
    session: Session,
    source_channel: SourceChannel,
    post_data: TelegramPostData,
) -> TelegramPost | None:
    telegram_message_id = int(post_data["telegram_message_id"])
    if post_exists(session, source_channel.id, telegram_message_id):
        return None

    text = normalize_text(post_data["text"])
    post = TelegramPost(
        source_channel_id=source_channel.id,
        telegram_message_id=telegram_message_id,
        message_date=post_data["message_date"],
        text=text,
        text_hash=make_text_hash(text),
        views=post_data.get("views"),
        forwards=post_data.get("forwards"),
        url=post_data.get("url"),
        raw_json=post_data.get("raw_json"),
    )

    session.add(post)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return None

    session.refresh(post)
    return post


def count_posts(session: Session) -> int:
    return session.scalar(select(func.count(TelegramPost.id))) or 0


def count_unprocessed_posts(session: Session) -> int:
    return session.scalar(
        select(func.count(TelegramPost.id)).where(TelegramPost.is_processed.is_(False)),
    ) or 0


def count_sources(session: Session) -> int:
    return session.scalar(select(func.count(SourceChannel.id))) or 0


def get_latest_posts(
    session: Session,
    limit: int = 20,
    source_username: str | None = None,
) -> list[TelegramPost]:
    statement = (
        select(TelegramPost)
        .join(TelegramPost.source_channel)
        .order_by(desc(TelegramPost.message_date), desc(TelegramPost.id))
        .limit(limit)
    )
    if source_username:
        statement = statement.where(SourceChannel.username == source_username.strip().lstrip("@"))

    return list(session.scalars(statement).all())


def get_posts_for_digest(
    session: Session,
    limit: int = 50,
    source_username: str | None = None,
    only_unprocessed: bool = False,
    since: datetime | None = None,
    until: datetime | None = None,
    min_views: int | None = None,
    min_forwards: int | None = None,
    contains: str | None = None,
    exclude: str | None = None,
) -> list[TelegramPost]:
    statement = (
        select(TelegramPost)
        .join(TelegramPost.source_channel)
        .order_by(desc(TelegramPost.message_date), desc(TelegramPost.id))
        .limit(limit)
    )
    if source_username:
        statement = statement.where(SourceChannel.username == source_username.strip().lstrip("@"))
    if only_unprocessed:
        statement = statement.where(TelegramPost.is_processed.is_(False))
    if since:
        statement = statement.where(TelegramPost.message_date >= since)
    if until:
        statement = statement.where(TelegramPost.message_date <= until)
    if min_views is not None:
        statement = statement.where(TelegramPost.views >= min_views)
    if min_forwards is not None:
        statement = statement.where(TelegramPost.forwards >= min_forwards)
    if contains:
        statement = statement.where(TelegramPost.text.ilike(f"%{contains}%"))
    if exclude:
        statement = statement.where(TelegramPost.text.not_ilike(f"%{exclude}%"))

    return list(session.scalars(statement).all())


def count_posts_by_source(session: Session) -> list[tuple[str, str | None, int]]:
    statement = (
        select(SourceChannel.username, SourceChannel.title, func.count(TelegramPost.id))
        .join(TelegramPost, TelegramPost.source_channel_id == SourceChannel.id, isouter=True)
        .group_by(SourceChannel.id)
        .order_by(SourceChannel.username)
    )
    return [(username, title, count) for username, title, count in session.execute(statement).all()]


def mark_posts_processed(session: Session, post_ids: list[int]) -> int:
    if not post_ids:
        return 0

    posts = list(session.scalars(select(TelegramPost).where(TelegramPost.id.in_(post_ids))).all())
    for post in posts:
        post.is_processed = True
    session.commit()
    return len(posts)
