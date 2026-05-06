from datetime import datetime
from typing import TypedDict

from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

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


class SavePostResult(TypedDict):
    post: TelegramPost
    created: bool
    updated: bool


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
    result = save_or_update_post(session, source_channel, post_data)
    return result["post"] if result["created"] else None


def save_or_update_post(
    session: Session,
    source_channel: SourceChannel,
    post_data: TelegramPostData,
) -> SavePostResult:
    telegram_message_id = int(post_data["telegram_message_id"])
    existing_post = session.scalar(
        select(TelegramPost).where(
            TelegramPost.source_channel_id == source_channel.id,
            TelegramPost.telegram_message_id == telegram_message_id,
        ),
    )
    if existing_post:
        updated = _update_post_metrics(existing_post, post_data)
        if updated:
            session.commit()
            session.refresh(existing_post)
        return {"post": existing_post, "created": False, "updated": updated}

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
        existing_post = session.scalar(
            select(TelegramPost).where(
                TelegramPost.source_channel_id == source_channel.id,
                TelegramPost.telegram_message_id == telegram_message_id,
            ),
        )
        if existing_post is None:
            raise
        return {"post": existing_post, "created": False, "updated": False}

    session.refresh(post)
    return {"post": post, "created": True, "updated": False}


def _update_post_metrics(post: TelegramPost, post_data: TelegramPostData) -> bool:
    updated = False
    for field in ("views", "forwards", "raw_json"):
        new_value = post_data.get(field)
        if new_value is not None and getattr(post, field) != new_value:
            setattr(post, field, new_value)
            updated = True
    return updated


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


def get_post_by_id(session: Session, post_id: int) -> TelegramPost | None:
    return session.get(TelegramPost, post_id)


def get_post_by_source_message_id(
    session: Session,
    source_username: str,
    telegram_message_id: int,
) -> TelegramPost | None:
    return session.scalar(
        select(TelegramPost)
        .join(TelegramPost.source_channel)
        .where(
            SourceChannel.username == source_username.strip().lstrip("@"),
            TelegramPost.telegram_message_id == telegram_message_id,
        ),
    )


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
    only_selected: bool = False,
    include_rejected: bool = False,
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
    if only_selected:
        statement = statement.where(TelegramPost.is_selected.is_(True))
    if not include_rejected:
        statement = statement.where(TelegramPost.is_rejected.is_(False))

    return list(session.scalars(statement).all())


def count_posts_by_source(session: Session) -> list[tuple[str, str | None, int]]:
    statement = (
        select(SourceChannel.username, SourceChannel.title, func.count(TelegramPost.id))
        .join(TelegramPost, TelegramPost.source_channel_id == SourceChannel.id, isouter=True)
        .group_by(SourceChannel.id)
        .order_by(SourceChannel.username)
    )
    return [(username, title, count) for username, title, count in session.execute(statement).all()]


def get_source_report(session: Session) -> list[dict[str, object]]:
    statement = (
        select(
            SourceChannel.username,
            SourceChannel.title,
            func.count(TelegramPost.id).label("posts_count"),
            func.max(TelegramPost.message_date).label("latest_message_date"),
            func.avg(TelegramPost.views).label("avg_views"),
            func.avg(TelegramPost.forwards).label("avg_forwards"),
        )
        .join(TelegramPost, TelegramPost.source_channel_id == SourceChannel.id, isouter=True)
        .group_by(SourceChannel.id)
        .order_by(SourceChannel.username)
    )
    return [
        {
            "username": username,
            "title": title,
            "posts_count": posts_count,
            "latest_message_date": latest_message_date,
            "avg_views": avg_views,
            "avg_forwards": avg_forwards,
        }
        for username, title, posts_count, latest_message_date, avg_views, avg_forwards
        in session.execute(statement).all()
    ]


def mark_posts_processed(session: Session, post_ids: list[int]) -> int:
    if not post_ids:
        return 0

    posts = list(session.scalars(select(TelegramPost).where(TelegramPost.id.in_(post_ids))).all())
    for post in posts:
        post.is_processed = True
    session.commit()
    return len(posts)


def mark_posts_unprocessed(session: Session, post_ids: list[int] | None = None) -> int:
    statement = select(TelegramPost)
    if post_ids is not None:
        if not post_ids:
            return 0
        statement = statement.where(TelegramPost.id.in_(post_ids))

    posts = list(session.scalars(statement).all())
    for post in posts:
        post.is_processed = False
    session.commit()
    return len(posts)


def update_editorial_state(
    session: Session,
    post_ids: list[int],
    *,
    selected: bool | None = None,
    rejected: bool | None = None,
    category: str | None = None,
    editor_note: str | None = None,
) -> int:
    if not post_ids:
        return 0

    posts = list(session.scalars(select(TelegramPost).where(TelegramPost.id.in_(post_ids))).all())
    for post in posts:
        if selected is not None:
            post.is_selected = selected
            if selected:
                post.is_rejected = False
        if rejected is not None:
            post.is_rejected = rejected
            if rejected:
                post.is_selected = False
        if category is not None:
            post.category = category.strip() or None
        if editor_note is not None:
            post.editor_note = editor_note.strip() or None

    session.commit()
    return len(posts)


def get_selected_posts(session: Session, limit: int = 50) -> list[TelegramPost]:
    return list(
        session.scalars(
            select(TelegramPost)
            .options(selectinload(TelegramPost.source_channel))
            .join(TelegramPost.source_channel)
            .where(TelegramPost.is_selected.is_(True), TelegramPost.is_rejected.is_(False))
            .order_by(TelegramPost.category, desc(TelegramPost.message_date), desc(TelegramPost.id))
            .limit(limit),
        ).all(),
    )
