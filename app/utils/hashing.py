import hashlib

from app.utils.text import normalize_text


def make_text_hash(text: str) -> str:
    normalized_text = normalize_text(text)
    return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()
