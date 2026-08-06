"""The migration runner and backup machinery every store depends on."""
import sqlite3

import pytest

import db


def test_migrations_apply_in_order_and_record_version(tmp_path):
    path = tmp_path / "t.db"
    conn = db.connect(str(path))
    applied = db.migrate(conn, [
        (1, ["CREATE TABLE a (x INTEGER)"]),
        (2, ["ALTER TABLE a ADD COLUMN y TEXT"]),
    ])
    assert applied == [1, 2]
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
    conn.close()


def test_migrations_are_not_reapplied(tmp_path):
    path = tmp_path / "t.db"
    migrations = [(1, ["CREATE TABLE a (x INTEGER)"])]

    conn = db.connect(str(path))
    db.migrate(conn, migrations)
    conn.close()

    conn = db.connect(str(path))
    # Re-running must be a no-op; CREATE TABLE without IF NOT EXISTS would raise otherwise.
    assert db.migrate(conn, migrations) == []
    conn.close()


def test_callables_run_alongside_sql(tmp_path):
    def seed(conn):
        conn.execute("INSERT INTO a (x) VALUES (42)")

    conn = db.connect(str(tmp_path / "t.db"))
    db.migrate(conn, [(1, ["CREATE TABLE a (x INTEGER)", seed])])
    assert conn.execute("SELECT x FROM a").fetchone()[0] == 42
    conn.close()


def test_a_failed_migration_rolls_back_entirely(tmp_path):
    """A half-applied schema change is far worse than a failed startup: it leaves the version
    counter claiming work that did not happen."""
    path = tmp_path / "t.db"
    conn = db.connect(str(path))
    with pytest.raises(sqlite3.Error):
        db.migrate(conn, [(1, [
            "CREATE TABLE a (x INTEGER)",
            "CREATE TABLE a (x INTEGER)",  # duplicate — fails
        ])])

    assert conn.execute("PRAGMA user_version").fetchone()[0] == 0
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "a" not in tables
    conn.close()


def test_connection_uses_wal(tmp_path):
    """In the default rollback journal a reader blocks a writer, which on a threaded UI shows
    up as a save failing while a list renders."""
    conn = db.connect(str(tmp_path / "t.db"))
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    conn.close()


def test_backup_is_a_readable_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "BACKUP_DIR", tmp_path / "backups")
    path = tmp_path / "t.db"

    conn = db.connect(str(path))
    conn.execute("CREATE TABLE a (x INTEGER)")
    conn.execute("INSERT INTO a VALUES (7)")
    conn.commit()
    conn.close()

    dest = db.backup(str(path), tag="test")
    assert dest.exists()
    restored = sqlite3.connect(str(dest))
    assert restored.execute("SELECT x FROM a").fetchone()[0] == 7
    restored.close()


def test_backups_are_pruned_to_the_keep_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "BACKUP_DIR", tmp_path / "backups")
    path = tmp_path / "t.db"
    conn = db.connect(str(path))
    conn.execute("CREATE TABLE a (x INTEGER)")
    conn.commit()
    conn.close()

    for _ in range(5):
        db.backup(str(path), tag="test", keep=3)
    assert len(db.list_backups("t")) == 3


def test_backup_of_a_missing_database_is_a_no_op(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "BACKUP_DIR", tmp_path / "backups")
    assert db.backup(str(tmp_path / "nope.db")) is None


def test_integrity_check_reports_ok(tmp_path):
    path = tmp_path / "t.db"
    conn = db.connect(str(path))
    conn.execute("CREATE TABLE a (x INTEGER)")
    conn.commit()
    conn.close()
    assert db.integrity_check(str(path)) == "ok"
