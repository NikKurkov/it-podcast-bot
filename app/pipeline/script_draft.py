from datetime import datetime
from itertools import groupby
from pathlib import Path

from app.db.models import TelegramPost


def export_script_markdown(posts: list[TelegramPost], output_path: Path, title: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {title}",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Intro",
        "",
        "Коротко рассказываем, какие IT-новости сегодня попали в выпуск.",
        "",
    ]

    grouped_posts = sorted(posts, key=lambda post: (post.category or "uncategorized", post.message_date))
    for category, category_posts in groupby(grouped_posts, key=lambda post: post.category or "uncategorized"):
        lines.extend([f"## {category}", ""])
        for index, post in enumerate(category_posts, start=1):
            lines.append(f"### {index}. @{post.source_channel.username} #{post.telegram_message_id}")
            lines.append("")
            lines.append(post.text)
            if post.url:
                lines.extend(["", f"Source: {post.url}"])
            lines.append("")

    lines.extend(
        [
            "## Outro",
            "",
            "На этом всё. В следующем этапе этот черновик можно превратить в полноценный сценарий.",
            "",
        ],
    )

    output_path.write_text("\n".join(lines), encoding="utf-8")
