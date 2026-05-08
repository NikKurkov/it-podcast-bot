import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.settings import settings
from app.maintenance.cleanup import (
    clean_workspace,
    discover_cleanup_targets,
    format_cleanup_targets,
    init_empty_database,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Clean generated local data: episodes, temporary audio, raw data, logs, "
            "database and database backups. Keeps voices, background music, .env and config files."
        ),
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Actually delete files. Without this flag the script only prints what would be removed.",
    )
    parser.add_argument(
        "--keep-backups",
        action="store_true",
        help="Keep files in data/backups.",
    )
    parser.add_argument(
        "--no-init-db",
        action="store_true",
        help="Do not recreate an empty SQLite schema after cleanup.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    targets = discover_cleanup_targets(
        PROJECT_ROOT,
        settings.database_url,
        keep_backups=args.keep_backups,
    )
    print(format_cleanup_targets(targets))

    if not args.yes:
        print("\nDry run only. Re-run with --yes to delete these files.")
        return

    removed_targets = clean_workspace(
        PROJECT_ROOT,
        settings.database_url,
        keep_backups=args.keep_backups,
    )
    print(f"\nRemoved {len(removed_targets)} target(s).")

    if not args.no_init_db:
        init_empty_database()
        print("Initialized empty SQLite database schema.")

    print("Kept: data/voices, data/audio/music, .env, config files and source code.")


if __name__ == "__main__":
    main()
