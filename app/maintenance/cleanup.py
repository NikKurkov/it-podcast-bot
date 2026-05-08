import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CleanupTarget:
    path: Path
    reason: str
    kind: str


def discover_cleanup_targets(
    project_root: Path,
    database_url: str,
    keep_backups: bool = False,
) -> list[CleanupTarget]:
    root = project_root.resolve()
    targets: list[CleanupTarget] = []

    targets.extend(_children(root / "data" / "episodes", "generated episode package"))
    targets.extend(
        _children_except(
            root / "data" / "audio",
            keep_names={"music"},
            reason="generated audio artifact",
        ),
    )
    targets.extend(_children(root / "data" / "raw", "raw temporary data"))
    targets.extend(_children(root / "data" / "logs", "local log file"))

    db_path = _sqlite_path_from_url(database_url, root)
    targets.extend(_existing_database_files(db_path))

    if not keep_backups:
        targets.extend(_children(root / "data" / "backups", "database backup"))

    return _deduplicate_targets(_safe_targets(root, targets))


def clean_workspace(
    project_root: Path,
    database_url: str,
    keep_backups: bool = False,
) -> list[CleanupTarget]:
    targets = discover_cleanup_targets(
        project_root=project_root,
        database_url=database_url,
        keep_backups=keep_backups,
    )
    for target in targets:
        if target.path.is_dir():
            shutil.rmtree(target.path)
        else:
            target.path.unlink(missing_ok=True)

    _ensure_clean_workspace_dirs(project_root)
    return targets


def init_empty_database() -> None:
    from app.db.session import init_db

    init_db()


def format_cleanup_targets(targets: list[CleanupTarget]) -> str:
    if not targets:
        return "Nothing to clean."

    lines = ["Cleanup targets:"]
    for target in targets:
        lines.append(f"  - {target.path} ({target.reason})")
    return "\n".join(lines)


def _children(directory: Path, reason: str) -> list[CleanupTarget]:
    if not directory.exists():
        return []
    return [
        CleanupTarget(path=child, reason=reason, kind="directory" if child.is_dir() else "file")
        for child in sorted(directory.iterdir())
    ]


def _children_except(directory: Path, keep_names: set[str], reason: str) -> list[CleanupTarget]:
    if not directory.exists():
        return []
    return [
        CleanupTarget(path=child, reason=reason, kind="directory" if child.is_dir() else "file")
        for child in sorted(directory.iterdir())
        if child.name not in keep_names
    ]


def _existing_database_files(db_path: Path) -> list[CleanupTarget]:
    candidates = [
        db_path,
        db_path.with_name(f"{db_path.name}-wal"),
        db_path.with_name(f"{db_path.name}-shm"),
        db_path.with_name(f"{db_path.name}-journal"),
    ]
    return [
        CleanupTarget(path=path, reason="local SQLite news database", kind="file")
        for path in candidates
        if path.exists()
    ]


def _sqlite_path_from_url(database_url: str, project_root: Path) -> Path:
    if not database_url.startswith("sqlite:///"):
        raise ValueError("Only sqlite:/// DATABASE_URL cleanup is supported.")

    raw_path = database_url.replace("sqlite:///", "", 1)
    path = Path(raw_path)
    if not path.is_absolute():
        path = project_root / path
    return path


def _safe_targets(project_root: Path, targets: list[CleanupTarget]) -> list[CleanupTarget]:
    safe_targets = []
    for target in targets:
        resolved = target.path.resolve()
        if resolved == project_root or not resolved.is_relative_to(project_root):
            raise ValueError(f"Refusing to clean path outside project: {target.path}")
        safe_targets.append(
            CleanupTarget(
                path=resolved,
                reason=target.reason,
                kind=target.kind,
            ),
        )
    return safe_targets


def _deduplicate_targets(targets: list[CleanupTarget]) -> list[CleanupTarget]:
    seen: set[Path] = set()
    unique_targets = []
    for target in targets:
        if target.path in seen:
            continue
        seen.add(target.path)
        unique_targets.append(target)
    return unique_targets


def _ensure_clean_workspace_dirs(project_root: Path) -> None:
    for directory in [
        project_root / "data" / "audio" / "music",
        project_root / "data" / "backups",
        project_root / "data" / "episodes",
        project_root / "data" / "logs",
        project_root / "data" / "raw",
        project_root / "data" / "sessions",
        project_root / "data" / "voices" / "xtts",
    ]:
        directory.mkdir(parents=True, exist_ok=True)
