"""Shared episode selection for CLI commands and file-based history."""

import json
from datetime import datetime, timezone
from pathlib import Path


def episode_packages(episodes_dir: Path, required_file: str | None = None) -> list[Path]:
    if not episodes_dir.is_dir():
        return []
    return sorted(
        (
            path
            for path in episodes_dir.iterdir()
            if path.is_dir() and (required_file is None or (path / required_file).is_file())
        ),
        key=lambda path: (_created_at(path), path.name),
        reverse=True,
    )


def resolve_episode_path(
    value: str,
    project_root: Path,
    required_file: str | None = None,
) -> Path:
    """Resolve a CLI selector, exiting with a readable error if latest is absent."""
    episodes_dir = project_root / "data" / "episodes"
    if value != "latest":
        path = Path(value)
        if path.is_absolute():
            return path
        candidate = project_root / path
        return candidate if candidate.exists() else episodes_dir / path

    packages = episode_packages(episodes_dir, required_file)
    if not packages:
        detail = f" with {required_file}" if required_file else ""
        raise SystemExit(f"No episode packages{detail} found in {episodes_dir}.")
    return packages[0]


def _created_at(path: Path) -> float:
    for filename in ("metadata.json", "episode_metadata.json"):
        try:
            payload = json.loads((path / filename).read_text(encoding="utf-8"))
            created_at = datetime.fromisoformat(payload["created_at"].replace("Z", "+00:00"))
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            return created_at.timestamp()
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            continue
    return path.stat().st_mtime
