from datetime import datetime
from typing import TypedDict

from sqlalchemy import func, select
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
