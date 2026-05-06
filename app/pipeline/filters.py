from pathlib import Path

from app.config.settings import settings


def load_exclude_keywords(path: str | None = None) -> list[str]:
    keywords_path = Path(path or settings.exclude_keywords_file)
    if not keywords_path.exists():
        return []

    keywords: list[str] = []
    for raw_line in keywords_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if line:
            keywords.append(line.casefold())

    return _deduplicate(keywords)


def contains_excluded_keyword(text: str, keywords: list[str]) -> bool:
    normalized_text = text.casefold()
    return any(keyword in normalized_text for keyword in keywords)


def filter_excluded_items(items, keywords: list[str]):
    if not keywords:
        return list(items)

    return [
        item
        for item in items
        if not contains_excluded_keyword(item.text, keywords)
    ]


def _deduplicate(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)

    return result
