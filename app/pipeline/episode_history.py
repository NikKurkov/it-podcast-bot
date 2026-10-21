import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.pipeline.episode_paths import episode_packages


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
    packages = sorted(episode_packages(episodes_dir), key=_published_at, reverse=True)
    matched = 0
    for package_path in packages:
        selected_posts_path = package_path / "selected_posts.json"
        if not selected_posts_path.exists():
            continue
        if require_completed and not is_published_episode(package_path):
            continue

        post_ids.update(_read_selected_post_ids(selected_posts_path))
        matched += 1
        if matched >= limit:
            break

    return post_ids


def get_recent_episode_post_texts(
    episodes_dir: Path = Path("data/episodes"),
    *,
    limit: int = 5,
    require_completed: bool = True,
) -> list[str]:
    """Return selected post texts from recent completed episode packages."""
    if limit < 1 or not episodes_dir.exists():
        return []

    texts: list[str] = []
    packages = sorted(episode_packages(episodes_dir), key=_published_at, reverse=True)
    matched = 0
    for package_path in packages:
        selected_posts_path = package_path / "selected_posts.json"
        if not selected_posts_path.exists():
            continue
        if require_completed and not is_published_episode(package_path):
            continue

        texts.extend(_read_selected_post_texts(selected_posts_path))
        matched += 1
        if matched >= limit:
            break

    return texts


def _read_object(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def is_published_episode(package_path: Path) -> bool:
    # Preview audio and a successful local build have never been aired.
    receipt = _read_object(package_path / "telegram_publish.json")
    return (
        bool(receipt) or _read_object(package_path / "run_report.json").get("status") == "published"
    )


def _published_at(package_path: Path) -> float:
    for filename in ("telegram_publish.json", "run_report.json"):
        payload = _read_object(package_path / filename)
        value = payload.get("published_at") or payload.get("created_at")
        if isinstance(value, str):
            try:
                stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return stamp.replace(tzinfo=stamp.tzinfo or timezone.utc).timestamp()
            except ValueError:
                pass
    # Legacy receipts may not contain a timestamp.
    return package_path.stat().st_mtime


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


def _read_selected_post_texts(path: Path) -> list[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, list):
        return []

    texts: list[str] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if text:
            texts.append(text)
    return texts


def _extract_post_id(item: Any) -> int | None:
    if not isinstance(item, dict):
        return None
    try:
        return int(item["post_id"])
    except (KeyError, TypeError, ValueError):
        return None
