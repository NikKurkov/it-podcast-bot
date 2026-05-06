from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.config.settings import settings
from app.db.models import Base


def _ensure_sqlite_parent_dir(database_url: str) -> None:
    if not database_url.startswith("sqlite:///"):
        return

    db_path = database_url.replace("sqlite:///", "", 1)
    if db_path and db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_parent_dir(settings.database_url)

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    _ensure_sqlite_parent_dir(settings.database_url)
    Base.metadata.create_all(bind=engine)
    _run_lightweight_migrations()


def _run_lightweight_migrations() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    if not inspector.has_table("telegram_posts"):
        return

    columns = {column["name"] for column in inspector.get_columns("telegram_posts")}

    with engine.begin() as connection:
        if "collected_at" not in columns:
            connection.execute(text("ALTER TABLE telegram_posts ADD COLUMN collected_at DATETIME"))
            connection.execute(
                text("UPDATE telegram_posts SET collected_at = COALESCE(created_at, CURRENT_TIMESTAMP)"),
            )
        if "is_processed" not in columns:
            connection.execute(
                text("ALTER TABLE telegram_posts ADD COLUMN is_processed BOOLEAN NOT NULL DEFAULT 0"),
            )
