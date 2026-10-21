import re
from functools import lru_cache
from pathlib import Path

DEFAULT_PRONUNCIATION_PATH = Path("config/pronunciation_ru.txt")
_LETTER_NAMES = dict(
    zip(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        "эй би си ди и эф джи эйч ай джей кей эл эм эн оу пи кью ар эс ти ю ви дабл-ю экс уай зэд".split(),
    )
)
_ACRONYM_RE = re.compile(r"(?<![A-Za-zА-Яа-яЁё])[A-Z]{2,}(?![A-Za-zА-Яа-яЁё])")


@lru_cache(maxsize=8)
def load_pronunciation_map(path: str | Path = DEFAULT_PRONUNCIATION_PATH) -> dict[str, str]:
    pronunciation_path = Path(path)
    if not pronunciation_path.exists():
        return {}

    entries: dict[str, str] = {}
    for raw_line in pronunciation_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        source, replacement = (part.strip() for part in line.split("=", 1))
        if source and replacement:
            entries[source] = replacement
    return entries


def apply_pronunciation_map(
    text: str,
    pronunciation_map: dict[str, str] | None = None,
) -> str:
    result = text
    entries = pronunciation_map if pronunciation_map is not None else load_pronunciation_map()
    for source, replacement in sorted(
        entries.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        pattern = re.compile(
            rf"(?<![A-Za-zА-Яа-яЁё]){re.escape(source)}(?![A-Za-zА-Яа-яЁё])",
            flags=re.IGNORECASE,
        )
        result = pattern.sub(replacement, result)
    explicit = {key.casefold() for key in entries}

    def spell(match: re.Match) -> str:
        token = match.group()
        # A pronounceable uppercase word may be a name, not an initialism.
        if token.casefold() in explicit or any(vowel in token for vowel in "AEIOUY"):
            return token
        before = " " if match.start() and result[match.start() - 1].isdigit() else ""
        after = " " if match.end() < len(result) and result[match.end()].isdigit() else ""
        return before + "-".join(_LETTER_NAMES[letter] for letter in token) + after

    return _ACRONYM_RE.sub(spell, result)
