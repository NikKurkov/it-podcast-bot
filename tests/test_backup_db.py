import sqlite3

from scripts import backup_db


def test_backup_includes_committed_wal_transactions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    database = tmp_path / "news.sqlite3"
    monkeypatch.setattr(backup_db.settings, "database_url", f"sqlite:///{database}")
    with sqlite3.connect(database) as source:
        source.execute("PRAGMA journal_mode=WAL")
        source.execute("CREATE TABLE posts (text TEXT)")
        source.execute("INSERT INTO posts VALUES ('committed story')")
        source.commit()
        backup_db.main()
        (backup_path,) = (tmp_path / "data/backups").glob("*.sqlite3")
        with sqlite3.connect(backup_path) as backup:
            assert backup.execute("SELECT text FROM posts").fetchall() == [("committed story",)]
            assert backup.execute("PRAGMA integrity_check").fetchone() == ("ok",)
