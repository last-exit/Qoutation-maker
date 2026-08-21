"""Local SQLite history of every generated quotation, plus the client records they hang off.

Two structural changes matter here beyond the obvious CRUD:

*Clients are rows, not strings.* The ledger used to match quotes by comparing the free-text
`client_name` column, so "Acme360", "Acme 360" and "Acme360 LLC" were three unrelated clients
with three unrelated outstanding balances. Quotes now carry a `client_id`; the name on the
document is still stored for the record, but money is aggregated by identity.

*Quote numbers come from a counter, not from MAX(id)+1.* The old scheme read the next id
before inserting, so deleting the most recent quote made the next one reuse its number — two
different documents in a client's inbox both labelled Q-7. Numbers are now allocated from a
dedicated counter that only ever moves forward. Gaps are expected and harmless; collisions
are not.

Line-item photos are stored as `image_ref` hashes into the image store rather than inline
base64. A two-line quote used to occupy 690 KB of this database, of which 690,016 bytes were
image and 106 bytes were quotation.
"""
import json
import re
from datetime import datetime, timedelta

import db
import paths

DB_FILE = str(paths.data_path("history.db"))

# Valid lifecycle values for the `status` column, in the order they'd typically progress.
QUOTE_STATUSES = ["Sent", "Won", "Lost"]
# A quote only becomes an invoice once it's Won — payment tracking is meaningless before that.
PAYMENT_STATUSES = ["Unpaid", "Partial", "Paid"]

_PUNCT_RE = re.compile(r"[^\w\s]")
_WS_RE = re.compile(r"\s+")
# Trailing legal/company suffixes carry no identifying information and are the single most
# common reason the same client got typed two different ways.
_SUFFIXES = {"llc", "l l c", "fzc", "fze", "fz llc", "ltd", "limited", "inc", "co", "company",
             "corp", "corporation", "est", "establishment", "trading", "general trading"}


def normalize_client_name(name):
    """Identity key for a client name: case-folded, punctuation-stripped, suffix-trimmed,
    with whitespace removed entirely.

    Spacing inside a name is a typing difference, not a different company — "Acme360",
    "Acme 360" and "Acme360 L.L.C." are one client and all collapse to "acme360". Suffixes
    are stripped before the spaces so " llc" is still recognizable as a trailing word.

    Beyond that it stays deliberately literal: no abbreviation expansion, no fuzzy matching.
    A false merge silently combines two companies' balances and is much harder to notice than
    a false split, which `find_duplicate_clients` surfaces and the merge tool fixes by hand.
    """
    text = _PUNCT_RE.sub(" ", str(name or "").lower())
    text = _WS_RE.sub(" ", text).strip()
    changed = True
    while changed and text:
        changed = False
        for suffix in sorted(_SUFFIXES, key=len, reverse=True):
            if text.endswith(" " + suffix):
                text = text[: -(len(suffix) + 1)].strip()
                changed = True
                break
    return text.replace(" ", "")


def normalize_phone(phone):
    """Comparable form of a phone number: digits only, last 9 kept.

    Local, international and WhatsApp-pasted forms of the same UAE number differ only in
    country code and leading zero, so the trailing significant digits are what identify it.
    """
    digits = re.sub(r"\D", "", str(phone or ""))
    return digits[-9:] if len(digits) >= 9 else digits


def _connect():
    return db.connect(DB_FILE)


def _add_column(conn, table, column, definition):
    """ALTER TABLE ADD COLUMN, skipped if the column is already there.

    Needed because installs that ran the pre-migration-framework build already have the
    lifecycle columns, but report user_version 0 — so the migration that introduces them has
    to be safe to re-run against a database that already went through the old code path.
    """
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _add_lifecycle_columns(conn):
    _add_column(conn, "quotations", "status", "TEXT DEFAULT 'Sent'")
    _add_column(conn, "quotations", "valid_until", "TEXT")
    _add_column(conn, "quotations", "payment_status", "TEXT DEFAULT 'Unpaid'")
    _add_column(conn, "quotations", "amount_paid", "REAL DEFAULT 0")
    _add_column(conn, "quotations", "due_date", "TEXT")


def _add_client_column(conn):
    _add_column(conn, "quotations", "client_id", "INTEGER REFERENCES clients(id)")


def _add_quote_number_column(conn):
    _add_column(conn, "quotations", "quote_number", "TEXT")


def _backfill_clients(conn):
    """Creates a client row per distinct (normalized name, phone) already in history and
    points existing quotations at it."""
    rows = conn.execute(
        "SELECT id, client_name, client_phone FROM quotations ORDER BY id"
    ).fetchall()
    cache = {}
    for row in rows:
        norm = normalize_client_name(row["client_name"])
        phone_norm = normalize_phone(row["client_phone"])
        if not norm and not phone_norm:
            continue
        key = (norm, phone_norm)
        client_id = cache.get(key)
        if client_id is None:
            existing = conn.execute(
                "SELECT id FROM clients WHERE normalized_name = ? AND normalized_phone = ?",
                (norm, phone_norm),
            ).fetchone()
            if existing:
                client_id = existing["id"]
            else:
                cur = conn.execute(
                    """INSERT INTO clients (name, normalized_name, phone, normalized_phone, created_at, updated_at)
                       VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))""",
                    (row["client_name"] or "", norm, row["client_phone"] or "", phone_norm),
                )
                client_id = cur.lastrowid
            cache[key] = client_id
        conn.execute("UPDATE quotations SET client_id = ? WHERE id = ?", (client_id, row["id"]))


def _seed_quote_counter(conn):
    """Starts the counter above every number already handed out, so no historical document
    reference can ever be issued a second time."""
    row = conn.execute("SELECT COALESCE(MAX(id), 0) AS max_id FROM quotations").fetchone()
    conn.execute(
        "INSERT OR REPLACE INTO quote_counter (id, next_number) VALUES (1, ?)",
        (int(row["max_id"]) + 1,),
    )


def _backfill_quote_numbers(conn):
    conn.execute(
        "UPDATE quotations SET quote_number = 'Q-' || id WHERE quote_number IS NULL OR quote_number = ''"
    )


_MIGRATIONS = [
    (1, [
        """CREATE TABLE IF NOT EXISTS quotations (
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
        )""",
    ]),
    # Columns the original schema grew after the fact. Guarded individually because an
    # install that ran the old hand-rolled _migrate() already has some of them.
    (2, [_add_lifecycle_columns]),
    (3, [
        """CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            normalized_name TEXT NOT NULL,
            phone TEXT,
            normalized_phone TEXT,
            email TEXT,
            notes TEXT,
            merged_into INTEGER REFERENCES clients(id),
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )""",
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_clients_identity
               ON clients(normalized_name, normalized_phone)""",
        "CREATE INDEX IF NOT EXISTS idx_clients_name ON clients(normalized_name)",
        _add_client_column,
        _backfill_clients,
    ]),
    (4, [
        """CREATE TABLE IF NOT EXISTS quote_counter (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            next_number INTEGER NOT NULL
        )""",
        _add_quote_number_column,
        _seed_quote_counter,
        _backfill_quote_numbers,
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_quotations_number
               ON quotations(quote_number) WHERE quote_number IS NOT NULL""",
    ]),
    # The ledger and margin queries were full table scans over a column wrapped in
    # LOWER(TRIM()), which no index can serve.
    (5, [
        "CREATE INDEX IF NOT EXISTS idx_quotations_client ON quotations(client_id)",
        "CREATE INDEX IF NOT EXISTS idx_quotations_status_date ON quotations(status, quote_date)",
        "CREATE INDEX IF NOT EXISTS idx_quotations_created ON quotations(created_at DESC)",
    ]),
]


def init_db():
    conn = _connect()
    try:
        return db.migrate(conn, _MIGRATIONS)
    finally:
        conn.close()


# --- Clients ------------------------------------------------------------------------

def resolve_client(conn, name, phone=None):
    """Finds or creates the client row for a name/phone pair, following merges.

    Matching is on the normalized name plus the normalized phone. Phone is part of the key
    rather than a tiebreaker because two genuinely different clients sharing a common trading
    name is a real situation, and silently merging their balances would be worse than holding
    two rows a human can merge later.
    """
    norm = normalize_client_name(name)
    phone_norm = normalize_phone(phone)

    row = conn.execute(
        "SELECT * FROM clients WHERE normalized_name = ? AND normalized_phone = ?",
        (norm, phone_norm),
    ).fetchone()

    # A name typed without a phone should attach to the existing client rather than opening a
    # second identity, provided exactly one candidate carries that name.
    if row is None and not phone_norm:
        candidates = conn.execute(
            "SELECT * FROM clients WHERE normalized_name = ? AND merged_into IS NULL", (norm,)
        ).fetchall()
        if len(candidates) == 1:
            row = candidates[0]

    if row is not None:
        client_id = row["id"]
        # Follow a merge chain so quotes never land on a client that has been folded away.
        seen = set()
        while row["merged_into"] and row["merged_into"] not in seen:
            seen.add(row["merged_into"])
            nxt = conn.execute("SELECT * FROM clients WHERE id = ?", (row["merged_into"],)).fetchone()
            if nxt is None:
                break
            row, client_id = nxt, nxt["id"]
        # Fill in a phone learned on a later quote.
        if phone_norm and not row["normalized_phone"]:
            conn.execute(
                "UPDATE clients SET phone = ?, normalized_phone = ?, updated_at = datetime('now') WHERE id = ?",
                (phone or "", phone_norm, client_id),
            )
        return client_id

    cur = conn.execute(
        """INSERT INTO clients (name, normalized_name, phone, normalized_phone, created_at, updated_at)
           VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))""",
        (str(name or "").strip(), norm, str(phone or "").strip(), phone_norm),
    )
    return cur.lastrowid


def get_clients(include_merged=False):
    """Every client with their quote counts and balances — backs the client list screen."""
    conn = _connect()
    try:
        where = "" if include_merged else "WHERE c.merged_into IS NULL"
        rows = conn.execute(f"""
            SELECT c.*,
                   COUNT(q.id) AS quote_count,
                   COALESCE(SUM(CASE WHEN q.status = 'Won' THEN q.grand_total ELSE 0 END), 0) AS total_billed,
                   COALESCE(SUM(CASE WHEN q.status = 'Won' THEN q.amount_paid ELSE 0 END), 0) AS total_paid
            FROM clients c
            LEFT JOIN quotations q ON q.client_id = c.id
            {where}
            GROUP BY c.id
            ORDER BY c.name COLLATE NOCASE
        """).fetchall()
        out = []
        for row in rows:
            d = dict(row)
            d["total_outstanding"] = round(max(0.0, (d["total_billed"] or 0) - (d["total_paid"] or 0)), 2)
            out.append(d)
        return out
    finally:
        conn.close()


def update_client(client_id, name=None, phone=None, email=None, notes=None):
    conn = _connect()
    try:
        existing = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
        if not existing:
            raise ValueError(f"Client {client_id} not found.")
        new_name = str(name).strip() if name is not None else existing["name"]
        new_phone = str(phone).strip() if phone is not None else existing["phone"]
        conn.execute(
            """UPDATE clients SET name = ?, normalized_name = ?, phone = ?, normalized_phone = ?,
                   email = ?, notes = ?, updated_at = datetime('now')
               WHERE id = ?""",
            (new_name, normalize_client_name(new_name), new_phone, normalize_phone(new_phone),
             email if email is not None else existing["email"],
             notes if notes is not None else existing["notes"],
             client_id),
        )
        conn.commit()
    finally:
        conn.close()


def merge_clients(source_id, target_id):
    """Folds one client into another, moving their quotes across.

    The source row is kept and flagged rather than deleted so that anything still holding the
    old id resolves forward instead of dangling.
    """
    if int(source_id) == int(target_id):
        raise ValueError("Cannot merge a client into itself.")
    conn = _connect()
    try:
        conn.execute("BEGIN")
        for cid in (source_id, target_id):
            if not conn.execute("SELECT 1 FROM clients WHERE id = ?", (cid,)).fetchone():
                conn.execute("ROLLBACK")
                raise ValueError(f"Client {cid} not found.")
        moved = conn.execute(
            "UPDATE quotations SET client_id = ? WHERE client_id = ?", (target_id, source_id)
        ).rowcount
        conn.execute(
            "UPDATE clients SET merged_into = ?, updated_at = datetime('now') WHERE id = ?",
            (target_id, source_id),
        )
        conn.execute("COMMIT")
        return moved
    finally:
        conn.close()


def find_duplicate_clients():
    """Clients whose names normalize to the same key but are held apart by differing phone
    numbers — the merge screen's suggestion list."""
    conn = _connect()
    try:
        rows = conn.execute("""
            SELECT normalized_name, COUNT(*) AS n
            FROM clients WHERE merged_into IS NULL AND normalized_name <> ''
            GROUP BY normalized_name HAVING n > 1
        """).fetchall()
        groups = []
        for row in rows:
            members = conn.execute(
                "SELECT id, name, phone, email FROM clients WHERE normalized_name = ? AND merged_into IS NULL",
                (row["normalized_name"],),
            ).fetchall()
            groups.append({"normalized_name": row["normalized_name"],
                           "clients": [dict(m) for m in members]})
        return groups
    finally:
        conn.close()


# --- Quote numbering ------------------------------------------------------------------

def allocate_quote_number():
    """Reserves the next quote number and advances the counter, atomically.

    BEGIN IMMEDIATE takes the write lock up front so two concurrent compiles cannot read the
    same value. A number handed out here is spent even if document generation later fails —
    a gap in the sequence is invisible to clients, a duplicate reference is not.
    """
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT next_number FROM quote_counter WHERE id = 1").fetchone()
        if row is None:
            start = conn.execute(
                "SELECT COALESCE(MAX(id), 0) + 1 AS n FROM quotations"
            ).fetchone()["n"]
            conn.execute("INSERT INTO quote_counter (id, next_number) VALUES (1, ?)", (start,))
            number = int(start)
        else:
            number = int(row["next_number"])
        conn.execute("UPDATE quote_counter SET next_number = ? WHERE id = 1", (number + 1,))
        conn.execute("COMMIT")
        return f"Q-{number}"
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def peek_quote_number():
    """The number the next allocation will return, without consuming it. For display only."""
    conn = _connect()
    try:
        row = conn.execute("SELECT next_number FROM quote_counter WHERE id = 1").fetchone()
        if row:
            return f"Q-{int(row['next_number'])}"
        nxt = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 AS n FROM quotations").fetchone()["n"]
        return f"Q-{int(nxt)}"
    finally:
        conn.close()


# --- Quotations ------------------------------------------------------------------------

def save_quotation_history(record):
    """Persists a generated quotation and links it to a client record.

    `items` carry `image_ref` hashes, never inline image bytes.
    """
    conn = _connect()
    try:
        conn.execute("BEGIN")
        client_id = resolve_client(conn, record.get("client_name", ""), record.get("client_phone", ""))
        cur = conn.execute(
            """
            INSERT INTO quotations
                (client_id, client_name, client_phone, venue, quote_date, items_json, discount_type,
                 discount_value, subtotal, vat, grand_total, xlsx_path, docx_path, pdf_path,
                 status, valid_until, quote_number, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                client_id,
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
                # NULL, not "": the uniqueness index is partial (WHERE quote_number IS NOT
                # NULL), and an empty string is a value under it — so two quotes saved
                # without a number would collide and the second would fail to save.
                (record.get("quote_number") or None),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        conn.execute("COMMIT")
        return cur.lastrowid
    except Exception:
        conn.execute("ROLLBACK")
        raise
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


def update_payment(quotation_id, payment_status, amount_paid):
    """A quote's invoice/payment state — status defaults to Unpaid at Won, and this is how a
    PM records partial or full payment against it. Any status/amount can be set at any time,
    same as update_quotation_status, so a misclick is easy to correct."""
    if payment_status not in PAYMENT_STATUSES:
        raise ValueError(f"Invalid payment status '{payment_status}'. Must be one of {PAYMENT_STATUSES}.")
    conn = _connect()
    try:
        conn.execute(
            "UPDATE quotations SET payment_status = ?, amount_paid = ? WHERE id = ?",
            (payment_status, float(amount_paid or 0), quotation_id),
        )
        conn.commit()
    finally:
        conn.close()


def _row_to_quote(row, include_items=True):
    d = dict(row)
    raw = d.pop("items_json", None)
    try:
        parsed = json.loads(raw) if raw else []
    except Exception:
        parsed = []
    # `item_count` is always present, even when the line items themselves are omitted. The
    # history table shows a per-quote line count, and dropping `items` without providing a
    # count left the UI reading `.length` off undefined, which broke the whole table.
    d["item_count"] = len(parsed)
    if include_items:
        d["items"] = parsed
    return d


def get_client_ledger(client_name, client_phone=None, client_id=None):
    """Every quotation for a client, plus running totals.

    Resolves to a client_id first rather than string-matching names, so a ledger stays
    correct when the same company was typed differently on different quotes.
    """
    conn = _connect()
    try:
        if client_id is None:
            norm = normalize_client_name(client_name)
            phone_norm = normalize_phone(client_phone)
            row = conn.execute(
                "SELECT id FROM clients WHERE normalized_name = ? AND normalized_phone = ?",
                (norm, phone_norm),
            ).fetchone()
            if row is None:
                row = conn.execute(
                    "SELECT id FROM clients WHERE normalized_name = ? AND merged_into IS NULL LIMIT 1",
                    (norm,),
                ).fetchone()
            if row is None:
                return {"items": [], "total_billed": 0.0, "total_paid": 0.0, "total_outstanding": 0.0}
            client_id = row["id"]

        rows = conn.execute(
            "SELECT * FROM quotations WHERE client_id = ? ORDER BY id DESC", (client_id,)
        ).fetchall()

        items, total_billed, total_paid = [], 0.0, 0.0
        for row in rows:
            d = _row_to_quote(row)
            items.append(d)
            if d.get("status") == "Won":
                total_billed += float(d.get("grand_total") or 0)
                total_paid += float(d.get("amount_paid") or 0)
        return {
            "client_id": client_id,
            "items": items,
            "total_billed": round(total_billed, 2),
            "total_paid": round(total_paid, 2),
            "total_outstanding": round(max(0.0, total_billed - total_paid), 2),
        }
    finally:
        conn.close()


def get_margin_summary(period_days=30):
    """Sum of (rate - cost_price) * qty across Won quotes over the trailing period_days.
    Only counts line items where a catalog cost was actually captured at compile time —
    quotes with no catalog match contribute nothing, rather than a misleading estimate."""
    conn = _connect()
    try:
        cutoff = (datetime.now() - timedelta(days=period_days)).strftime("%Y-%m-%d")
        rows = conn.execute(
            "SELECT items_json FROM quotations WHERE status = 'Won' AND quote_date >= ?", (cutoff,)
        ).fetchall()
        total_margin = 0.0
        total_revenue = 0.0
        items_with_cost = 0
        items_without_cost = 0
        for row in rows:
            try:
                items = json.loads(row["items_json"])
            except Exception:
                continue
            for it in items:
                if not isinstance(it, dict):
                    continue
                cost = it.get("cost_price")
                qty = float(it.get("qty") or 0)
                rate = float(it.get("rate") or 0)
                if cost is None:
                    items_without_cost += 1
                    continue
                total_margin += (rate - float(cost)) * qty
                total_revenue += rate * qty
                items_with_cost += 1
        margin_pct = round(100.0 * total_margin / total_revenue, 1) if total_revenue else 0.0
        return {
            "total_margin": round(total_margin, 2),
            "margin_pct": margin_pct,
            "items_with_cost": items_with_cost,
            # Surfaced so the dashboard can say how much of the period this number actually
            # covers — a small margin over 2 of 90 line items is not a business figure.
            "items_without_cost": items_without_cost,
            "period_days": period_days,
        }
    finally:
        conn.close()


def get_quotation_history(limit=200, include_items=False):
    """Recent quotations. Items are omitted by default: the history list only renders client,
    date and total, and deserializing every line item of 200 quotes to show that was the
    single most expensive call in the app."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM quotations ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_row_to_quote(row, include_items=include_items) for row in rows]
    finally:
        conn.close()


def get_quotation_by_id(quotation_id):
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM quotations WHERE id = ?", (quotation_id,)).fetchone()
        return _row_to_quote(row) if row else None
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


def all_image_refs():
    """Every image ref referenced by a stored quotation — used by orphan collection so a
    photo still cited by an old quote is never swept up."""
    conn = _connect()
    try:
        refs = set()
        for row in conn.execute("SELECT items_json FROM quotations").fetchall():
            try:
                items = json.loads(row["items_json"])
            except Exception:
                continue
            for it in items:
                if isinstance(it, dict) and it.get("image_ref"):
                    refs.add(it["image_ref"])
        return refs
    finally:
        conn.close()


init_db()
