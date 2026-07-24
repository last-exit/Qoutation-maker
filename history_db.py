"""Local SQLite history of every generated quotation, for the Client & Quotation History tab."""
import json
import os
import sqlite3
from datetime import datetime

DB_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "history.db"))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS quotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_name TEXT NOT NULL,
    client_phone TEXT,
    venue TEXT,
    quote_date TEXT NOT NULL,
    items_json TEXT NOT NULL,
    discount_type TEXT,
    discount_value REAL DEFAULT 0,
    subtotal REAL DEFAULT 0,
    vat REAL DEFAULT 0,
    grand_total REAL DEFAULT 0,
    xlsx_path TEXT,
    docx_path TEXT,
    pdf_path TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

# Valid lifecycle values for the `status` column, in the order they'd typically progress.
QUOTE_STATUSES = ["Sent", "Won", "Lost"]


def _connect():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def _migrate(conn):
    """Adds columns introduced after the original schema, without disturbing existing rows.
    SQLite's ALTER TABLE ADD COLUMN is safe to call repeatedly guarded by a column-existence check."""
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(quotations)").fetchall()}
    if "status" not in existing_cols:
        conn.execute("ALTER TABLE quotations ADD COLUMN status TEXT DEFAULT 'Sent'")
    if "valid_until" not in existing_cols:
        conn.execute("ALTER TABLE quotations ADD COLUMN valid_until TEXT")
    conn.commit()


def init_db():
    conn = _connect()
    try:
        conn.execute(_SCHEMA)
        conn.commit()
        _migrate(conn)
    finally:
        conn.close()


def save_quotation_history(record):
    """record: dict with client_name, client_phone, venue, quote_date, items (list),
    discount_type, discount_value, subtotal, vat, grand_total, xlsx_path, docx_path, pdf_path,
    valid_until (optional). New quotes start in 'Sent' status — the PM updates it to Won/Lost
    once the client responds."""
    conn = _connect()
    try:
        cur = conn.execute(
            """
            INSERT INTO quotations
                (client_name, client_phone, venue, quote_date, items_json, discount_type,
                 discount_value, subtotal, vat, grand_total, xlsx_path, docx_path, pdf_path,
                 status, valid_until, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.get("client_name", ""),
                record.get("client_phone", ""),
                record.get("venue", ""),
                record.get("quote_date", datetime.now().strftime("%Y-%m-%d")),
                json.dumps(record.get("items", [])),
                record.get("discount_type"),
                float(record.get("discount_value") or 0),
                float(record.get("subtotal") or 0),
                float(record.get("vat") or 0),
                float(record.get("grand_total") or 0),
                record.get("xlsx_path", ""),
                record.get("docx_path", ""),
                record.get("pdf_path", ""),
                "Sent",
                record.get("valid_until", ""),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def peek_next_quotation_id():
    """Returns the id the next saved quotation will receive.

    The documents need to carry their own reference number, but the id is only assigned on
    insert — and the insert records the generated file paths, so it has to happen after
    generation. Reading the next id up front keeps the printed ref and the stored record in
    agreement. Safe here because this is a single-user desktop app with no concurrent writer.
    """
    conn = _connect()
    try:
        row = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM quotations").fetchone()
        return int(row["next_id"]) if row else 1
    except Exception:
        return 1
    finally:
        conn.close()


def update_quotation_status(quotation_id, status):
    """Moves a quote through its lifecycle (Sent -> Won/Lost). Also used to correct a
    misclick, so any value in QUOTE_STATUSES is accepted at any time."""
    if status not in QUOTE_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of {QUOTE_STATUSES}.")
    conn = _connect()
    try:
        conn.execute("UPDATE quotations SET status = ? WHERE id = ?", (status, quotation_id))
        conn.commit()
    finally:
        conn.close()


def get_quotation_history(limit=200):
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM quotations ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            try:
                d["items"] = json.loads(d.pop("items_json"))
            except Exception:
                d["items"] = []
            results.append(d)
        return results
    finally:
        conn.close()


def get_quotation_by_id(quotation_id):
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM quotations WHERE id = ?", (quotation_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["items"] = json.loads(d.pop("items_json"))
        except Exception:
            d["items"] = []
        return d
    finally:
        conn.close()


def delete_quotation_history(quotation_id):
    conn = _connect()
    try:
        conn.execute("DELETE FROM quotations WHERE id = ?", (quotation_id,))
        conn.commit()
        return True
    finally:
        conn.close()


init_db()
