import json
from dataclasses import dataclass
from datetime import datetime
from itertools import groupby
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import TelegramPost
from app.db.repositories.posts import get_posts_for_digest
from app.pipeline.scoring import score_post


@dataclass(frozen=True)
class DigestItem:
    post_id: int
    source: str
    title: str | None
    message_date: datetime
    text: str
    url: str | None
    views: int | None
    forwards: int | None
    score: float | None = None


def build_digest_items(
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
    ranked: bool = False,
) -> list[DigestItem]:
    posts = get_posts_for_digest(
        session,
        limit=limit,
        source_username=source_username,
        only_unprocessed=only_unprocessed,
        since=since,
        until=until,
        min_views=min_views,
        min_forwards=min_forwards,
        contains=contains,
        exclude=exclude,
        only_selected=only_selected,
        include_rejected=include_rejected,
    )
    if ranked:
        posts = sorted(posts, key=score_post, reverse=True)

    return [_post_to_digest_item(post, include_score=ranked) for post in posts]


def export_digest_markdown(items: list[DigestItem], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# IT news digest",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
    ]

    grouped_items = sorted(items, key=lambda item: (item.source, item.message_date), reverse=True)
    for source, source_items in groupby(grouped_items, key=lambda item: item.source):
        source_items = list(source_items)
        title = f" ({source_items[0].title})" if source_items[0].title else ""
        lines.extend([f"## @{source}{title}", ""])

        for item in source_items:
            date_text = item.message_date.isoformat(timespec="minutes")
            metrics = _format_metrics(item)
            lines.append(f"### {date_text}{metrics}")
            lines.append("")
            lines.append(item.text)
            if item.url:
                lines.extend(["", f"Link: {item.url}"])
            lines.append("")

    output_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def export_digest_json(items: list[DigestItem], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "source": item.source,
            "post_id": item.post_id,
            "title": item.title,
            "message_date": item.message_date.isoformat(),
            "text": item.text,
            "url": item.url,
            "views": item.views,
            "forwards": item.forwards,
            "score": item.score,
        }
        for item in items
    ]
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _post_to_digest_item(post: TelegramPost, include_score: bool = False) -> DigestItem:
    return DigestItem(
        post_id=post.id,
        source=post.source_channel.username,
        title=post.source_channel.title,
        message_date=post.message_date,
        text=post.text,
        url=post.url,
        views=post.views,
        forwards=post.forwards,
        score=score_post(post) if include_score else None,
    )


def _format_metrics(item: DigestItem) -> str:
    metrics = []
    if item.views is not None:
        metrics.append(f"views: {item.views}")
    if item.forwards is not None:
        metrics.append(f"forwards: {item.forwards}")
    if item.score is not None:
        metrics.append(f"score: {item.score:.2f}")

    return f" ({', '.join(metrics)})" if metrics else ""
