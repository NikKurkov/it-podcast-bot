from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class SourceChannel(Base):
    __tablename__ = "source_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    posts: Mapped[list["TelegramPost"]] = relationship(
        back_populates="source_channel",
        cascade="all, delete-orphan",
    )


class TelegramPost(Base):
    __tablename__ = "telegram_posts"
    __table_args__ = (
        UniqueConstraint(
            "source_channel_id",
            "telegram_message_id",
            name="uq_telegram_post_source_message",
        ),
        Index("ix_telegram_posts_text_hash", "text_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_channel_id: Mapped[int] = mapped_column(ForeignKey("source_channels.id"), nullable=False)
    telegram_message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    message_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    forwards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    raw_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_selected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_rejected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    editor_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    source_channel: Mapped[SourceChannel] = relationship(back_populates="posts")
    episode_links: Mapped[list["EpisodePost"]] = relationship(
        back_populates="telegram_post",
        cascade="all, delete-orphan",
    )


class EpisodeDraft(Base):
    __tablename__ = "episode_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    source_post_ids: Mapped[str] = mapped_column(Text, nullable=False)
    markdown_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    json_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class Episode(Base):
    __tablename__ = "episodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    package_path: Mapped[str] = mapped_column(String(512), nullable=False)
    audio_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    metadata_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    telegram_channel_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telegram_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    posts: Mapped[list["EpisodePost"]] = relationship(
        back_populates="episode",
        cascade="all, delete-orphan",
        order_by="EpisodePost.position",
    )


class EpisodePost(Base):
    __tablename__ = "episode_posts"
    __table_args__ = (
        UniqueConstraint("episode_id", "telegram_post_id", name="uq_episode_post_episode_post"),
        UniqueConstraint("episode_id", "position", name="uq_episode_post_position"),
        Index("ix_episode_posts_telegram_post_id", "telegram_post_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    episode_id: Mapped[int] = mapped_column(ForeignKey("episodes.id"), nullable=False)
    telegram_post_id: Mapped[int] = mapped_column(ForeignKey("telegram_posts.id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    episode: Mapped[Episode] = relationship(back_populates="posts")
    telegram_post: Mapped[TelegramPost] = relationship(back_populates="episode_links")
