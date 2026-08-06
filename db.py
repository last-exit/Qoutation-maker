"""Shared SQLite plumbing: connections, versioned migrations, and backups.

Each store used to open raw `sqlite3.connect()` handles in journal_mode=delete with no busy
timeout, while pywebview dispatches every JS API call on its own thread — so two overlapping
calls could surface a bare "database is locked" to the user. They also had no migration path:
`history_db` hand-rolled a PRAGMA table_info check, and catalog/corrections had nothing at
all, meaning any future schema change would break whoever already had data.

This module centralizes all three concerns so a new store gets them for free.
"""
import os
import shutil
import sqlite3
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKUP_DIR = ROOT / "backups"

# How long a writer waits for a competing write before giving up. Generous because the
# alternative the user sees is a failed save.
BUSY_TIMEOUT_MS = 5000
# Timestamped copies kept per database. Small files; the safety is worth the disk.
BACKUPS_KEPT = 10


def connect(db_file):
    """Opens a connection configured for concurrent readers and a single writer.

    WAL matters here beyond performance: in the default rollback journal a reader blocks a
    writer, which on a threaded UI shows up as a save silently failing while a list is being
    rendered.
    """
    conn = sqlite3.connect(db_file, timeout=BUSY_TIMEOUT_MS / 1000.0)
    conn.row_factory = sqlite3.Row
    # Explicit transaction control. The default mode opens transactions implicitly before
    # DML and commits at unpredictable points, which collides with the explicit BEGIN/COMMIT
    # the migration runner needs. `conn.commit()` stays valid, it just becomes a no-op.
    conn.isolation_level = None
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA journal_mode = WAL")
    # Durability/throughput tradeoff appropriate for WAL: a power loss can cost the last
    # transaction but can never corrupt the database.
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate(conn, migrations):
    """Applies pending migrations in order, tracked by `PRAGMA user_version`.

    `migrations` is a list of (version, step). A step is a SQL string, a callable taking the
    connection, or a sequence mixing both — schema changes that need real logic (backfilling
    a new column from existing rows) sit alongside plain DDL in one ordered unit.

    Each step runs inside its own transaction together with the version bump. SQLite makes
    DDL transactional, so a failure leaves the database on the previous version rather than
    half-migrated.

    Statements are listed individually rather than given as one script on purpose:
    `executescript()` issues an implicit COMMIT before it runs, which would silently drop the
    surrounding transaction and allow a half-applied migration to stick.
    """
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    applied = []
    for version, step in sorted(migrations, key=lambda m: m[0]):
        if version <= current:
            continue
        try:
            conn.execute("BEGIN")
            steps = [step] if (callable(step) or isinstance(step, str)) else list(step)
            for one in steps:
                if callable(one):
                    one(conn)
                else:
                    conn.execute(one)
            # PRAGMA does not accept bind parameters; version is an int literal we control.
            conn.execute(f"PRAGMA user_version = {int(version)}")
            conn.execute("COMMIT")
            applied.append(version)
        except Exception:
            conn.execute("ROLLBACK")
            raise
    return applied


def backup(db_file, tag="auto", keep=BACKUPS_KEPT):
    """Takes a consistent online snapshot of a database and prunes old ones.

    Uses sqlite3's backup API rather than copying the file: with WAL enabled, a plain file
    copy can miss committed transactions still sitting in the -wal sidecar and produce a
    snapshot that will not open.
    """
    db_path = Path(db_file)
    if not db_path.exists():
        return None

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    # Milliseconds, not seconds: two backups taken in the same second — which happens when a
    # migration and a pre-index snapshot land together — would otherwise resolve to the same
    # filename and the second would silently overwrite the first.
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    dest = BACKUP_DIR / f"{db_path.stem}_{tag}_{stamp}.db"

    source = sqlite3.connect(db_file)
    try:
        target = sqlite3.connect(str(dest))
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()

    prune_backups(db_path.stem, keep=keep)
    return dest


def prune_backups(stem, keep=BACKUPS_KEPT):
    if not BACKUP_DIR.exists():
        return 0
    snapshots = sorted(
        BACKUP_DIR.glob(f"{stem}_*.db"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    removed = 0
    for old in snapshots[keep:]:
        try:
            old.unlink()
            removed += 1
        except OSError:
            pass
    return removed


def list_backups(stem=None):
    if not BACKUP_DIR.exists():
        return []
    pattern = f"{stem}_*.db" if stem else "*.db"
    return sorted(BACKUP_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)


def vacuum(db_file):
    """Reclaims free pages. Worth running after a bulk delete or a blob migration, both of
    which leave a large freelist that SQLite will otherwise hold on to indefinitely."""
    if not Path(db_file).exists():
        return 0
    before = Path(db_file).stat().st_size
    conn = sqlite3.connect(db_file)
    try:
        conn.execute("VACUUM")
        conn.commit()
    finally:
        conn.close()
    return before - Path(db_file).stat().st_size


def integrity_check(db_file):
    if not Path(db_file).exists():
        return "missing"
    conn = sqlite3.connect(db_file)
    try:
        return conn.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        conn.close()
