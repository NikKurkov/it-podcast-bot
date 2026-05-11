from itertools import groupby
from pathlib import Path
import re

from app.db.models import TelegramPost


def export_script_markdown(posts: list[TelegramPost], output_path: Path, title: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {title}",
        "",
        "## Selected news",
        "",
    ]

    grouped_posts = sorted(posts, key=lambda post: (post.category or "uncategorized", post.message_date))
    for category, category_posts in groupby(grouped_posts, key=lambda post: post.category or "uncategorized"):
        lines.extend([f"## {category}", ""])
        for index, post in enumerate(category_posts, start=1):
            lines.append(f"### {index}. @{post.source_channel.username} #{post.telegram_message_id}")
            lines.append("")
            lines.extend(_fact_lock_lines(post.text))
            lines.append("")
            lines.append(post.text)
            if post.url:
                lines.extend(["", f"Source: {post.url}"])
            lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def _fact_lock_lines(text: str) -> list[str]:
    clean_text = " ".join(text.replace("\n", " ").split()).strip()
    title = _short_fact_title(clean_text)
    facts = _extract_fact_sentences(clean_text)
    lines = [
        "Fact lock:",
        f"- Main claim: {title}",
    ]
    for fact in facts:
        if fact != title:
            lines.append(f"- Allowed fact: {fact}")
    lines.extend(
        [
            "- Do not add facts that are not explicitly present in this post.",
            "- Do not replace the mechanism with a similar-sounding but different one.",
        ],
    )
    return lines


def _short_fact_title(text: str, max_chars: int = 140) -> str:
    match = re.search(r"\s+[—–-]\s+|[.!?…]+(?:\s+|$)", text)
    title = text[: match.start()].strip(" .,:;!?—-") if match else text.strip(" .,:;!?—-")
    if len(title) <= max_chars:
        return title
    return f"{title[: max_chars - 3].rstrip()}..."


def _extract_fact_sentences(text: str, max_facts: int = 3, max_chars: int = 180) -> list[str]:
    sentences = [
        sentence.strip(" .,:;!?—-")
        for sentence in re.split(r"(?<=[.!?…])\s+", text)
        if sentence.strip(" .,:;!?—-")
    ]
    facts = []
    for sentence in sentences:
        if len(sentence) > max_chars:
            sentence = f"{sentence[: max_chars - 3].rstrip()}..."
        if sentence not in facts:
            facts.append(sentence)
        if len(facts) >= max_facts:
            break
    return facts
