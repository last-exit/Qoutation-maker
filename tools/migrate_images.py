"""One-time migration of inline base64 photos into the content-addressed image store.

Moves image data out of two places:

  * `chroma_db` metadata — where every blob also cost a copy in Chroma's B-tree index over
    metadata string values, and a third in its never-purged write log.
  * `history.db` items_json — where a two-line quotation occupied 690 KB.

Both are rewritten to carry a 64-character ref instead. Safe to re-run: an item already
holding a ref is skipped, and identical images collapse onto one file by hash.

    python tools/migrate_images.py --dry-run     # report only
    python tools/migrate_images.py               # migrate, after backing up
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import db  # noqa: E402
import history_db  # noqa: E402
import image_store  # noqa: E402
import maintenance  # noqa: E402

CHROMA_SQLITE = ROOT / "chroma_db" / "chroma.sqlite3"


def migrate_chroma(dry_run=False):
    """Rewrites embedding_metadata rows keyed 'image_base64' to 'image_ref'."""
    if not CHROMA_SQLITE.exists():
        return {"rows": 0, "stored": 0, "skipped": 0, "note": "no chroma database"}

    conn = sqlite3.connect(str(CHROMA_SQLITE))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, key, string_value FROM embedding_metadata WHERE key = 'image_base64'"
        ).fetchall()

        stored, skipped, failed = 0, 0, 0
        for row in rows:
            value = row["string_value"]
            if not value:
                skipped += 1
                continue
            if image_store.is_ref(value):
                skipped += 1
                continue
            ref = image_store.store_data_uri(value)
            if not ref:
                failed += 1
                continue
            stored += 1
            if not dry_run:
                # Written as a new key rather than in place, so a failure part-way leaves the
                # original blobs intact and the migration can simply be re-run.
                conn.execute(
                    """INSERT INTO embedding_metadata (id, key, string_value)
                       VALUES (?, 'image_ref', ?)
                       ON CONFLICT(id, key) DO UPDATE SET string_value = excluded.string_value""",
                    (row["id"], ref),
                )

        if not dry_run:
            conn.execute("DELETE FROM embedding_metadata WHERE key = 'image_base64'")
            conn.commit()

        return {"rows": len(rows), "stored": stored, "skipped": skipped, "failed": failed}
    finally:
        conn.close()


def migrate_history(dry_run=False):
    """Rewrites items_json in every saved quotation to carry refs."""
    conn = db.connect(history_db.DB_FILE)
    try:
        rows = conn.execute("SELECT id, items_json FROM quotations").fetchall()
        quotes_changed, images_stored = 0, 0

        for row in rows:
            try:
                items = json.loads(row["items_json"])
            except Exception:
                continue

            changed = False
            for item in items:
                if not isinstance(item, dict):
                    continue
                value = item.pop("image_base64", None)
                if not value:
                    continue
                if image_store.is_ref(value):
                    item["image_ref"] = value
                    changed = True
                    continue
                ref = image_store.store_data_uri(value)
                if ref:
                    item["image_ref"] = ref
                    images_stored += 1
                    changed = True

            if changed:
                quotes_changed += 1
                if not dry_run:
                    conn.execute(
                        "UPDATE quotations SET items_json = ? WHERE id = ?",
                        (json.dumps(items), row["id"]),
                    )

        if not dry_run:
            conn.commit()
        return {"quotes": len(rows), "quotes_changed": quotes_changed, "images_stored": images_stored}
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report what would change")
    parser.add_argument("--skip-vacuum", action="store_true", help="leave freed pages in place")
    args = parser.parse_args()

    def size(path):
        return path.stat().st_size if path.exists() else 0

    before = {"chroma": size(CHROMA_SQLITE), "history": size(Path(history_db.DB_FILE))}

    if not args.dry_run:
        print("Backing up databases ...")
        for path in maintenance.backup_all(tag="preimagemigration"):
            print(f"  {path}")

    print("\nMigrating ChromaDB metadata ...")
    chroma_result = migrate_chroma(dry_run=args.dry_run)
    print(f"  {chroma_result}")

    print("\nMigrating quotation history ...")
    history_result = migrate_history(dry_run=args.dry_run)
    print(f"  {history_result}")

    if not args.dry_run and not args.skip_vacuum:
        print("\nReclaiming space ...")
        print(f"  chroma: {maintenance.compact_chroma()}")
        print(f"  sqlite vacuum: {maintenance.vacuum_all()} bytes")

    after = {"chroma": size(CHROMA_SQLITE), "history": size(Path(history_db.DB_FILE))}
    stats = image_store.stats()

    print("\n--- Result ---")
    for name in ("chroma", "history"):
        print(f"  {name}: {before[name] / 1e6:8.1f} MB -> {after[name] / 1e6:8.1f} MB")
    print(f"  image store: {stats['count']} files, {stats['bytes'] / 1e6:.1f} MB")
    total_before = sum(before.values())
    total_after = sum(after.values()) + stats["bytes"]
    print(f"  total: {total_before / 1e6:.1f} MB -> {total_after / 1e6:.1f} MB")
    if args.dry_run:
        print("\n(dry run — nothing was written to the databases)")


if __name__ == "__main__":
    main()
