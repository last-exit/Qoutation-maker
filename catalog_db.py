"""Persistent, PM-editable item catalog — the "easy database for adding items" the Compiler
never had. Unlike the historical index (rebuilt from parsed quote files on every sync, keyed
only by description text), catalog items are entered once and stick around. They also carry a
cost_price the historical pipeline never captured, which is what makes margin reporting
possible.

Two things had to change before margin reporting could work at all:

*Descriptions are unique.* There was no constraint, `add_catalog_item` always INSERTed, and
the lookup returned whichever duplicate SQLite happened to reach first — so the cost behind a
margin figure was nondeterministic.

*Lookup is no longer exact-string-only.* Quote lines are multi-line free text
("Jungle Gym Playhouse\\n10m Height x 5m Length"), so an equality test against a catalog title
essentially never matched and every quote recorded cost_price: None. Matching now works down
a ladder — exact, then title-line, then containment — with semantic matching layered on top
by the caller, which owns the embedding model.
"""
import os
import re
from datetime import datetime

import db

DB_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "catalog.db"))

_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]")


def normalize_description(description):
    """Identity key for a catalog description: case-folded, punctuation and whitespace
    collapsed. Newlines included, so a multi-line spec block still normalizes stably."""
    text = _PUNCT_RE.sub(" ", str(description or "").lower())
    return _WS_RE.sub(" ", text).strip()


def title_line(description):
    """First non-empty line of a description.

    Quote lines carry the product name on line one and dimensions/features below it, so this
    is the part that actually corresponds to a catalog entry.
    """
    for line in str(description or "").splitlines():
        if line.strip():
            return line.strip()
    return ""


def _dedupe_before_unique_index(conn):
    """Collapses pre-existing duplicate descriptions so the unique index can be built.

    Keeps the most recently updated row of each group — it is the one a PM most likely
    intended — and preserves a cost_price from an older sibling if the survivor lacks one,
    since losing a captured cost silently breaks margin reporting.
    """
    groups = conn.execute("""
        SELECT LOWER(TRIM(description)) AS k, COUNT(*) AS n
        FROM catalog_items GROUP BY k HAVING n > 1
    """).fetchall()
    for group in groups:
        rows = conn.execute(
            """SELECT * FROM catalog_items WHERE LOWER(TRIM(description)) = ?
               ORDER BY COALESCE(updated_at, created_at) DESC, id DESC""",
            (group["k"],),
        ).fetchall()
        survivor = rows[0]
        if survivor["cost_price"] is None:
            inherited = next((r["cost_price"] for r in rows[1:] if r["cost_price"] is not None), None)
            if inherited is not None:
                conn.execute("UPDATE catalog_items SET cost_price = ? WHERE id = ?",
                             (inherited, survivor["id"]))
        for row in rows[1:]:
            conn.execute("DELETE FROM catalog_items WHERE id = ?", (row["id"],))


def _backfill_normalized(conn):
    for row in conn.execute("SELECT id, description FROM catalog_items").fetchall():
        conn.execute(
            "UPDATE catalog_items SET normalized_description = ? WHERE id = ?",
            (normalize_description(row["description"]), row["id"]),
        )


def _add_normalized_column(conn):
    existing = {r[1] for r in conn.execute("PRAGMA table_info(catalog_items)").fetchall()}
    if "normalized_description" not in existing:
        conn.execute("ALTER TABLE catalog_items ADD COLUMN normalized_description TEXT")


_MIGRATIONS = [
    (1, [
        """CREATE TABLE IF NOT EXISTS catalog_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            unit TEXT DEFAULT 'Pcs',
            rate REAL DEFAULT 0,
            cost_price REAL,
            category TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )""",
    ]),
    (2, [
        _dedupe_before_unique_index,
        _add_normalized_column,
        _backfill_normalized,
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_catalog_normalized
               ON catalog_items(normalized_description)""",
        "CREATE INDEX IF NOT EXISTS idx_catalog_category ON catalog_items(category)",
    ]),
]


def _connect():
    return db.connect(DB_FILE)


def init_db():
    conn = _connect()
    try:
        return db.migrate(conn, _MIGRATIONS)
    finally:
        conn.close()


def add_catalog_item(description, unit="Pcs", rate=0, cost_price=None, category=None):
    """Inserts, or updates in place if that description already exists.

    Upsert rather than error: a PM re-adding an item they already entered means "make it look
    like this", and failing the save would just leave them to hunt for the existing row.
    """
    description = str(description).strip()
    if not description:
        raise ValueError("Description is required.")
    norm = normalize_description(description)
    conn = _connect()
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = conn.execute(
            """
            INSERT INTO catalog_items
                (description, normalized_description, unit, rate, cost_price, category, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(normalized_description) DO UPDATE SET
                description = excluded.description,
                unit = excluded.unit,
                rate = excluded.rate,
                cost_price = excluded.cost_price,
                category = excluded.category,
                updated_at = excluded.updated_at
            """,
            (description, norm, unit or "Pcs", float(rate or 0),
             float(cost_price) if cost_price not in (None, "") else None,
             category, now, now),
        )
        conn.commit()
        if cur.lastrowid:
            return cur.lastrowid
        row = conn.execute(
            "SELECT id FROM catalog_items WHERE normalized_description = ?", (norm,)
        ).fetchone()
        return row["id"] if row else None
    finally:
        conn.close()


def update_catalog_item(item_id, description=None, unit=None, rate=None, cost_price=None, category=None):
    conn = _connect()
    try:
        existing = conn.execute("SELECT * FROM catalog_items WHERE id = ?", (item_id,)).fetchone()
        if not existing:
            raise ValueError(f"Catalog item {item_id} not found.")
        new_desc = str(description).strip() if description is not None else existing["description"]
        conn.execute(
            """
            UPDATE catalog_items SET
                description = ?, normalized_description = ?, unit = ?, rate = ?,
                cost_price = ?, category = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                new_desc,
                normalize_description(new_desc),
                unit if unit is not None else existing["unit"],
                float(rate) if rate is not None else existing["rate"],
                # An explicit empty string clears the cost; None means "leave it alone".
                None if cost_price == "" else (
                    float(cost_price) if cost_price is not None else existing["cost_price"]
                ),
                category if category is not None else existing["category"],
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                item_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def delete_catalog_item(item_id):
    conn = _connect()
    try:
        conn.execute("DELETE FROM catalog_items WHERE id = ?", (item_id,))
        conn.commit()
    finally:
        conn.close()


def get_catalog_items():
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM catalog_items ORDER BY description COLLATE NOCASE"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def find_catalog_item_by_description(description):
    """Best catalog match for a quote line, without needing the embedding model.

    Tries progressively looser keys and stops at the first hit, so a confident match is never
    displaced by a fuzzy one:
      1. the whole description, normalized
      2. its title line — the usual shape, where a quote line adds a spec block under the name
      3. containment either way, longest match wins, for "Pirate Ship" vs "Pirate Ship Large"

    Returns the row dict with a `match` key naming which rung matched, or None.
    """
    norm = normalize_description(description)
    if not norm:
        return None

    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM catalog_items WHERE normalized_description = ?", (norm,)
        ).fetchone()
        if row:
            return dict(row, match="exact")

        title_norm = normalize_description(title_line(description))
        if title_norm and title_norm != norm:
            row = conn.execute(
                "SELECT * FROM catalog_items WHERE normalized_description = ?", (title_norm,)
            ).fetchone()
            if row:
                return dict(row, match="title")

        # Containment, longest first. Short catalog names are excluded because a 3-character
        # entry is contained in almost anything and would match indiscriminately.
        candidates = conn.execute(
            """SELECT * FROM catalog_items
               WHERE LENGTH(normalized_description) >= 6
                 AND (? LIKE '%' || normalized_description || '%'
                      OR normalized_description LIKE '%' || ? || '%')
               ORDER BY LENGTH(normalized_description) DESC LIMIT 1""",
            (norm, title_norm or norm),
        ).fetchone()
        if candidates:
            return dict(candidates, match="contains")
        return None
    finally:
        conn.close()


def count_items():
    conn = _connect()
    try:
        return int(conn.execute("SELECT COUNT(*) AS n FROM catalog_items").fetchone()["n"])
    finally:
        conn.close()


init_db()
