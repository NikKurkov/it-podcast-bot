import shutil
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.settings import settings


def main() -> None:
    db_path = _sqlite_path_from_url(settings.database_url)
    if not db_path.exists():
        raise SystemExit(f"Database file does not exist: {db_path}")

    backup_dir = Path("data/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{db_path.stem}_{timestamp}{db_path.suffix}"
    shutil.copy2(db_path, backup_path)
    print(f"Created backup: {backup_path}")


def _sqlite_path_from_url(database_url: str) -> Path:
    if not database_url.startswith("sqlite:///"):
        raise SystemExit("Only sqlite:/// DATABASE_URL backups are supported.")

    return Path(database_url.replace("sqlite:///", "", 1))


if __name__ == "__main__":
    main()
