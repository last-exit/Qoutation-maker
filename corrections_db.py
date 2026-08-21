"""Persistent PM corrections to parsed line items.

Keyed by (file_name, original_description) so a correction made once in the Needs Review
queue is automatically re-applied the next time that source file gets re-parsed/re-synced —
without this, every re-index would silently forget the fix and re-flag the same item.

A correction records *which fields the PM actually changed*, in `corrected_fields`. That
distinction is load-bearing. Previously every review action snapshotted all three fields, so
setting a venue in bulk — or merely dismissing a flag — pinned that item's rate forever, and
a later price change in the source spreadsheet could never reach the app again. Only the
named fields are re-applied now; everything else re-parses fresh on each sync.
"""
from datetime import datetime

import db
import paths

DB_FILE = str(paths.data_path("corrections.db"))

# The fields a PM can pin. Anything not listed here re-parses from the source every sync.
CORRECTABLE_FIELDS = ("rate", "unit", "venue")

_MIGRATIONS = [
    (1, [
        """CREATE TABLE IF NOT EXISTS corrections (
            file_name TEXT NOT NULL,
            original_description TEXT NOT NULL,
            rate REAL,
            unit TEXT,
            venue TEXT,
            corrected_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (file_name, original_description)
        )""",
    ]),
    (2, [
        "ALTER TABLE corrections ADD COLUMN corrected_fields TEXT",
        # Backfill for rows written before this column existed. A pre-existing row could have
        # come from a real edit, from a bulk venue change, or from a plain dismissal — all
        # three stored an identical full snapshot, so intent has to be inferred.
        #
        # Non-empty unit/venue are taken as intentional. `rate` is deliberately excluded when
        # it is NULL or 0: nobody corrects a price *to* zero, so a zero here is the signature
        # of a snapshot rather than an edit, and pinning it would permanently suppress the
        # "missing unit rate" flag on a genuinely broken item.
        """UPDATE corrections SET corrected_fields = TRIM(
            CASE WHEN rate IS NOT NULL AND rate > 0 THEN 'rate,' ELSE '' END ||
            CASE WHEN unit IS NOT NULL AND TRIM(unit) <> '' THEN 'unit,' ELSE '' END ||
            CASE WHEN venue IS NOT NULL AND TRIM(venue) <> '' THEN 'venue' ELSE '' END,
            ','
        )""",
    ]),
    (3, [
        "CREATE INDEX IF NOT EXISTS idx_corrections_file ON corrections(file_name)",
    ]),
]


def _connect():
    return db.connect(DB_FILE)


def init_db():
    conn = _connect()
    try:
        db.migrate(conn, _MIGRATIONS)
    finally:
        conn.close()


def _norm_key(file_name, original_description):
    return (str(file_name).strip(), str(original_description).strip().lower())


def _clean_fields(fields):
    if not fields:
        return []
    if isinstance(fields, str):
        fields = fields.split(",")
    return [f for f in (str(x).strip() for x in fields) if f in CORRECTABLE_FIELDS]


def save_correction(file_name, original_description, rate=None, unit=None, venue=None,
                    corrected_fields=None):
    """Upserts a correction.

    `corrected_fields` names the fields the PM edited and is what gets re-applied on the next
    sync. Passing an empty list is meaningful and supported: it records "a human looked at
    this and left it alone", which clears the review flag without pinning any value.

    Values for un-named fields are still stored, because the review UI shows them as context
    for what the item looked like when it was reviewed — they are simply never re-applied.
    """
    file_name_k, desc_k = _norm_key(file_name, original_description)
    fields = _clean_fields(corrected_fields)

    conn = _connect()
    try:
        existing = conn.execute(
            "SELECT * FROM corrections WHERE file_name = ? AND original_description = ?",
            (file_name_k, desc_k),
        ).fetchone()

        final_rate = rate if rate is not None else (existing["rate"] if existing else None)
        final_unit = unit if unit is not None else (existing["unit"] if existing else None)
        final_venue = venue if venue is not None else (existing["venue"] if existing else None)

        # A second correction adds to what is pinned rather than replacing it, so fixing a
        # venue today does not quietly un-pin a rate corrected last month.
        merged = set(fields)
        if existing and existing["corrected_fields"]:
            merged |= set(_clean_fields(existing["corrected_fields"]))

        conn.execute(
            """
            INSERT INTO corrections
                (file_name, original_description, rate, unit, venue, corrected_fields, corrected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(file_name, original_description) DO UPDATE SET
                rate = excluded.rate,
                unit = excluded.unit,
                venue = excluded.venue,
                corrected_fields = excluded.corrected_fields,
                corrected_at = excluded.corrected_at
            """,
            (file_name_k, desc_k, final_rate, final_unit, final_venue,
             ",".join(sorted(merged)),
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
    finally:
        conn.close()


def get_correction(file_name, original_description):
    file_name_k, desc_k = _norm_key(file_name, original_description)
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM corrections WHERE file_name = ? AND original_description = ?",
            (file_name_k, desc_k),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_all_corrections():
    """Returns {(file_name, description_lower): {...}} for bulk lookup during indexing."""
    conn = _connect()
    try:
        rows = conn.execute("SELECT * FROM corrections").fetchall()
        return {
            (row["file_name"], row["original_description"]): {
                "rate": row["rate"],
                "unit": row["unit"],
                "venue": row["venue"],
                "corrected_fields": _clean_fields(row["corrected_fields"]),
                "corrected_at": row["corrected_at"],
            }
            for row in rows
        }
    finally:
        conn.close()


def apply_correction(item, fix):
    """Applies a stored correction to a freshly parsed item, in place.

    Only fields named in `corrected_fields` overwrite parsed data. The review flag is always
    cleared: the record exists precisely because a human already looked at this item.
    """
    if not fix:
        return item
    fields = set(fix.get("corrected_fields") or [])

    if "rate" in fields and fix.get("rate") is not None:
        item["historical_rate"] = float(fix["rate"])
        item["rate_confidence"] = "high"
    if "unit" in fields and fix.get("unit"):
        item["unit"] = fix["unit"]
    if "venue" in fields and fix.get("venue"):
        item["venue"] = fix["venue"]
        item["venue_confidence"] = "high"

    item["needs_review"] = False
    item["flag_reason"] = (
        "corrected by PM: " + ", ".join(sorted(fields)) if fields else "reviewed by PM - left as-is"
    )
    return item


def list_corrections(limit=500):
    """Every stored correction, newest first — backs the management screen. Without this a
    bad correction could only be undone by hand-editing SQLite."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM corrections ORDER BY corrected_at DESC LIMIT ?", (limit,)
        ).fetchall()
        out = []
        for row in rows:
            d = dict(row)
            d["corrected_fields"] = _clean_fields(d.get("corrected_fields"))
            out.append(d)
        return out
    finally:
        conn.close()


def delete_correction(file_name, original_description):
    """Forgets a correction so the item re-parses from source on the next sync."""
    file_name_k, desc_k = _norm_key(file_name, original_description)
    conn = _connect()
    try:
        cur = conn.execute(
            "DELETE FROM corrections WHERE file_name = ? AND original_description = ?",
            (file_name_k, desc_k),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def count_corrections():
    conn = _connect()
    try:
        return int(conn.execute("SELECT COUNT(*) AS n FROM corrections").fetchone()["n"])
    finally:
        conn.close()


init_db()
