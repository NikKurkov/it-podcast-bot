import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import TelegramPost
from app.db.repositories.posts import get_posts_for_digest


@dataclass(frozen=True)
class DigestItem:
    source: str
    title: str | None
    message_date: datetime
    text: str
    url: str | None
    views: int | None
    forwards: int | None


def build_digest_items(
    session: Session,
    limit: int = 50,
    source_username: str | None = None,
    only_unprocessed: bool = False,
) -> list[DigestItem]:
    posts = get_posts_for_digest(
        session,
        limit=limit,
        source_username=source_username,
        only_unprocessed=only_unprocessed,
    )
    return [_post_to_digest_item(post) for post in posts]


def export_digest_markdown(items: list[DigestItem], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# IT news digest",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
    ]

    current_source: str | None = None
    for item in items:
        if item.source != current_source:
            current_source = item.source
            title = f" ({item.title})" if item.title else ""
            lines.extend([f"## @{item.source}{title}", ""])

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
            "title": item.title,
            "message_date": item.message_date.isoformat(),
            "text": item.text,
            "url": item.url,
            "views": item.views,
            "forwards": item.forwards,
        }
        for item in items
    ]
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _post_to_digest_item(post: TelegramPost) -> DigestItem:
    return DigestItem(
        source=post.source_channel.username,
        title=post.source_channel.title,
        message_date=post.message_date,
        text=post.text,
        url=post.url,
        views=post.views,
        forwards=post.forwards,
    )


def _format_metrics(item: DigestItem) -> str:
    metrics = []
    if item.views is not None:
        metrics.append(f"views: {item.views}")
    if item.forwards is not None:
        metrics.append(f"forwards: {item.forwards}")

    return f" ({', '.join(metrics)})" if metrics else ""
