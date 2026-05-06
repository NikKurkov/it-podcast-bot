import re


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def is_meaningful_text(text: str) -> bool:
    return bool(normalize_text(text))
