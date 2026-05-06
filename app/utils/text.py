import re


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def is_meaningful_text(text: str) -> bool:
    return bool(normalize_text(text))


def shorten_text(text: str, max_length: int = 200) -> str:
    normalized_text = normalize_text(text)
    if len(normalized_text) <= max_length:
        return normalized_text

    return normalized_text[: max_length - 3].rstrip() + "..."
