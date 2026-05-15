import json
from pathlib import Path
from typing import Any


def get_recent_episode_post_ids(
    episodes_dir: Path = Path("data/episodes"),
    *,
    limit: int = 1,
    require_completed: bool = True,
) -> set[int]:
    """Return DB post ids used in recent completed episode packages."""
    if limit < 1 or not episodes_dir.exists():
        return set()

    post_ids: set[int] = set()
    packages = sorted(
        (path for path in episodes_dir.iterdir() if path.is_dir()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    matched = 0
    for package_path in packages:
        selected_posts_path = package_path / "selected_posts.json"
        if not selected_posts_path.exists():
            continue
        if require_completed and not _is_completed_episode(package_path):
            continue

        post_ids.update(_read_selected_post_ids(selected_posts_path))
        matched += 1
        if matched >= limit:
            break

    return post_ids


def _is_completed_episode(package_path: Path) -> bool:
    return (package_path / "audio.mp3").exists() or (package_path / "telegram_publish.json").exists()


def _read_selected_post_ids(path: Path) -> set[int]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    if not isinstance(payload, list):
        return set()

    post_ids: set[int] = set()
    for item in payload:
        post_id = _extract_post_id(item)
        if post_id is not None:
            post_ids.add(post_id)
    return post_ids


def _extract_post_id(item: Any) -> int | None:
    if not isinstance(item, dict):
        return None
    try:
        return int(item["post_id"])
    except (KeyError, TypeError, ValueError):
        return None
