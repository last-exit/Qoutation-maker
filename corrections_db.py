"""Persistent PM corrections to parsed line items.

Keyed by (file_name, original_description) so a correction made once in the Needs Review
queue is automatically re-applied the next time that source file gets re-parsed/re-synced —
without this, every re-index would silently forget the fix and re-flag the same item.
"""
import os
import sqlite3
from datetime import datetime

DB_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "corrections.db"))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS corrections (
    file_name TEXT NOT NULL,
    original_description TEXT NOT NULL,
    rate REAL,
    unit TEXT,
    venue TEXT,
    corrected_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (file_name, original_description)
);
"""


def _connect():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _connect()
    try:
        conn.execute(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def _norm_key(file_name, original_description):
    return (str(file_name).strip(), str(original_description).strip().lower())


def save_correction(file_name, original_description, rate=None, unit=None, venue=None):
    """Upserts a correction. Only non-None fields overwrite; pass all three for a full fix."""
    file_name_k, desc_k = _norm_key(file_name, original_description)
    conn = _connect()
    try:
        existing = conn.execute(
            "SELECT * FROM corrections WHERE file_name = ? AND original_description = ?",
            (file_name_k, desc_k),
        ).fetchone()

        final_rate = rate if rate is not None else (existing["rate"] if existing else None)
        final_unit = unit if unit is not None else (existing["unit"] if existing else None)
        final_venue = venue if venue is not None else (existing["venue"] if existing else None)

        conn.execute(
            """
            INSERT INTO corrections (file_name, original_description, rate, unit, venue, corrected_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(file_name, original_description) DO UPDATE SET
                rate = excluded.rate,
                unit = excluded.unit,
                venue = excluded.venue,
                corrected_at = excluded.corrected_at
            """,
            (file_name_k, desc_k, final_rate, final_unit, final_venue,
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
    """Returns {(file_name, original_description_lower): {rate, unit, venue}} for bulk lookup during indexing."""
    conn = _connect()
    try:
        rows = conn.execute("SELECT * FROM corrections").fetchall()
        result = {}
        for row in rows:
            result[(row["file_name"], row["original_description"])] = {
                "rate": row["rate"], "unit": row["unit"], "venue": row["venue"],
            }
        return result
    finally:
        conn.close()


init_db()
