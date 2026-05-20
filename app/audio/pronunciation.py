import re
from functools import lru_cache
from pathlib import Path

DEFAULT_PRONUNCIATION_PATH = Path("config/pronunciation_ru.txt")


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
    return result
