"""Housekeeping the app has to do for itself, because nobody administers a desktop install.

Two things grow without bound if left alone:

  * SQLite free pages after a bulk delete or a re-index. SQLite never returns them to the
    filesystem without an explicit VACUUM.
  * Orphaned photos in the image store, left behind when the item citing them was re-parsed
    away or a quotation was deleted.

Deliberately *not* here: truncating `chroma_db/embeddings_queue`. That table is Chroma's
write-ahead log and looks like pure waste — it held a duplicate of every record and accounted
for 57 MB of a 176 MB index. It is not waste. The local HNSW vector segment replays from it,
and emptying it leaves the vector index unable to resolve ids: `count()` still reports every
row, but any `get()` or `query()` fails with "Error finding id". It has to be rebuilt from
source after that. The queue is only large when the records are large, and records no longer
carry image blobs — so with refs in place it costs roughly 1 MB, not 57.

None of this runs implicitly on a schedule the user cannot see; `run_all` is called from the
maintenance action in the UI and after a full re-index.
"""
import sqlite3
from pathlib import Path

import catalog_db
import corrections_db
import db
import history_db
import image_store
import logging_setup

ROOT = Path(__file__).resolve().parent
CHROMA_SQLITE = ROOT / "chroma_db" / "chroma.sqlite3"

DATABASES = [history_db.DB_FILE, catalog_db.DB_FILE, corrections_db.DB_FILE]

log = logging_setup.get_logger("maintenance")


def backup_all(tag="auto"):
    """Snapshots every database. Called before anything destructive."""
    made = []
    for path in DATABASES:
        try:
            dest = db.backup(path, tag=tag)
            if dest:
                made.append(str(dest))
        except Exception as e:
            log.exception("Backup of %s failed: %s", path, e)
    return made


def compact_chroma():
    """Reclaims free pages in the Chroma database, without touching its contents.

    VACUUM only: the write log is left alone for the reason given in the module docstring.
    Space genuinely freed by a re-index (which drops and recreates the collection) shows up
    as free pages, and this is what returns them to the filesystem.
    """
    if not CHROMA_SQLITE.exists():
        return {"reclaimed_bytes": 0}

    before = CHROMA_SQLITE.stat().st_size
    conn = sqlite3.connect(str(CHROMA_SQLITE))
    try:
        conn.execute("VACUUM")
        conn.commit()
    finally:
        conn.close()

    reclaimed = before - CHROMA_SQLITE.stat().st_size
    log.info("Compacted Chroma, reclaimed %.1f MB", reclaimed / 1e6)
    return {"reclaimed_bytes": reclaimed}


def vacuum_all():
    reclaimed = 0
    for path in DATABASES:
        try:
            reclaimed += db.vacuum(path)
        except Exception as e:
            log.exception("VACUUM of %s failed: %s", path, e)
    return reclaimed


def collect_image_orphans(live_refs):
    """Photos no longer cited by the index or by any saved quotation.

    Refused when `live_refs` is empty: that means the caller found no references at all,
    which in practice signals a failed index read rather than a genuinely empty library — and
    acting on it would delete every photo the business owns.
    """
    if not live_refs:
        log.warning("Refusing orphan sweep: caller supplied no live refs.")
        return []
    return image_store.collect_orphans(live_refs)


def delete_orphans(paths):
    freed = 0
    for path in paths:
        try:
            freed += path.stat().st_size
            path.unlink()
        except OSError as e:
            log.warning("Could not remove %s: %s", path, e)
    return freed


def run_all(live_refs=None, remove_orphans=False):
    """Full housekeeping pass. Returns a summary the UI can show verbatim."""
    summary = {"backups": backup_all(tag="maintenance")}
    summary["chroma"] = compact_chroma()
    summary["vacuum_reclaimed_bytes"] = vacuum_all()

    if remove_orphans and live_refs is not None:
        orphans = collect_image_orphans(live_refs)
        summary["orphans_removed"] = len(orphans)
        summary["orphan_bytes_freed"] = delete_orphans(orphans)
    else:
        orphans = collect_image_orphans(live_refs) if live_refs else []
        summary["orphans_found"] = len(orphans)

    summary["image_store"] = image_store.stats()
    summary["integrity"] = {Path(p).name: db.integrity_check(p) for p in DATABASES}
    return summary
