"""Invoices and the payments made against them.

The app could mark a quotation Paid and store one `amount_paid` number. That is not invoicing.
It cannot express the company's own stated terms — 50% on confirmation, 50% before handover —
because two payments against one document have nowhere to live. It cannot say what is
outstanding across all clients, what is overdue, or how much VAT was charged in a quarter.

So an invoice is its own record, and payments are a ledger against it. `amount_paid` is
derived from that ledger rather than stored, because a stored total and its own payment rows
are two versions of the same fact and they drift.

Workflow status (Draft / Sent / Cancelled) is stored, because it reflects a human decision.
Payment state (Unpaid / Partial / Paid) and overdue are computed, because they are facts about
money that has or has not arrived.
"""
import json
from datetime import datetime, timedelta

import db
import paths

DB_FILE = str(paths.data_path("invoices.db"))

# What a human decides about the document itself.
INVOICE_STATUSES = ["Draft", "Sent", "Cancelled"]
PAYMENT_METHODS = ["Bank Transfer", "Cheque", "Cash", "Card", "Other"]

# UAE standard rate. Kept here so an invoice records the rate it was raised under rather than
# whatever the rate happens to be when a report is run years later.
DEFAULT_VAT_RATE = 0.05


def _connect():
    return db.connect(DB_FILE)


def _seed_counter(conn):
    conn.execute("INSERT OR REPLACE INTO invoice_counter (id, next_number) VALUES (1, 1)")


_MIGRATIONS = [
    (1, [
        """CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT NOT NULL,
            quotation_id INTEGER,
            job_id INTEGER,
            client_name TEXT NOT NULL,
            client_phone TEXT,
            client_email TEXT,
            venue TEXT,
            issue_date TEXT NOT NULL,
            due_date TEXT,
            items_json TEXT NOT NULL,
            subtotal REAL DEFAULT 0,
            discount_amount REAL DEFAULT 0,
            vat_rate REAL DEFAULT 0.05,
            vat REAL DEFAULT 0,
            grand_total REAL DEFAULT 0,
            status TEXT DEFAULT 'Draft',
            notes TEXT,
            xlsx_path TEXT,
            docx_path TEXT,
            pdf_path TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )""",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_invoices_number ON invoices(invoice_number)",
        "CREATE INDEX IF NOT EXISTS idx_invoices_client ON invoices(client_name)",
        "CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status, due_date)",
        # A quotation is invoiced once. Raising two invoices for the same work is a
        # double-billing error that surfaces as an angry client, not as a crash.
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_invoices_quotation
               ON invoices(quotation_id) WHERE quotation_id IS NOT NULL""",

        """CREATE TABLE IF NOT EXISTS invoice_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
            amount REAL NOT NULL,
            paid_date TEXT NOT NULL,
            method TEXT DEFAULT 'Bank Transfer',
            reference TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )""",
        "CREATE INDEX IF NOT EXISTS idx_payments_invoice ON invoice_payments(invoice_id)",

        """CREATE TABLE IF NOT EXISTS invoice_counter (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            next_number INTEGER NOT NULL
        )""",
        _seed_counter,
    ]),
]


def init_db():
    conn = _connect()
    try:
        return db.migrate(conn, _MIGRATIONS)
    finally:
        conn.close()


# --- Numbering --------------------------------------------------------------------------

def allocate_invoice_number():
    """Reserves the next invoice number.

    Never reused, for a harder reason than quotations: an invoice number is a tax record. Two
    invoices sharing one is a filing problem, not just a confusing inbox.
    """
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT next_number FROM invoice_counter WHERE id = 1").fetchone()
        number = int(row["next_number"]) if row else 1
        if row:
            conn.execute("UPDATE invoice_counter SET next_number = ? WHERE id = 1", (number + 1,))
        else:
            conn.execute("INSERT INTO invoice_counter (id, next_number) VALUES (1, ?)",
                         (number + 1,))
        conn.execute("COMMIT")
        return f"INV-{number:04d}"
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def peek_invoice_number():
    conn = _connect()
    try:
        row = conn.execute("SELECT next_number FROM invoice_counter WHERE id = 1").fetchone()
        return f"INV-{int(row['next_number']):04d}" if row else "INV-0001"
    finally:
        conn.close()


# --- Creating ---------------------------------------------------------------------------

def create_invoice(client_name, items, subtotal=0.0, discount_amount=0.0, vat=0.0,
                   grand_total=0.0, quotation_id=None, job_id=None, client_phone="",
                   client_email="", venue="", issue_date=None, payment_terms_days=30,
                   notes="", vat_rate=DEFAULT_VAT_RATE):
    """Raises an invoice. Returns its id."""
    client_name = str(client_name or "").strip()
    if not client_name:
        raise ValueError("An invoice needs a client.")
    if not items:
        raise ValueError("An invoice needs at least one line.")

    issue = issue_date or datetime.now().strftime("%Y-%m-%d")
    due = (datetime.strptime(issue, "%Y-%m-%d") + timedelta(days=int(payment_terms_days or 0))
           ).strftime("%Y-%m-%d")

    conn = _connect()
    try:
        if quotation_id:
            existing = conn.execute(
                "SELECT id FROM invoices WHERE quotation_id = ?", (quotation_id,)
            ).fetchone()
            if existing:
                raise ValueError(
                    f"Quotation {quotation_id} has already been invoiced "
                    f"(invoice id {existing['id']}). Raising a second invoice would bill twice."
                )

        cur = conn.execute(
            """INSERT INTO invoices (invoice_number, quotation_id, job_id, client_name,
                   client_phone, client_email, venue, issue_date, due_date, items_json,
                   subtotal, discount_amount, vat_rate, vat, grand_total, status, notes,
                   created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Draft', ?, ?)""",
            (allocate_invoice_number(), quotation_id, job_id, client_name, client_phone,
             client_email, venue, issue, due, json.dumps(items), float(subtotal or 0),
             float(discount_amount or 0), float(vat_rate or 0), float(vat or 0),
             float(grand_total or 0), notes,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_invoice(invoice_id, **fields):
    allowed = {"client_name", "client_phone", "client_email", "venue", "issue_date",
               "due_date", "status", "notes", "xlsx_path", "docx_path", "pdf_path", "job_id"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if "status" in updates and updates["status"] not in INVOICE_STATUSES:
        raise ValueError(f"Invalid status '{updates['status']}'. Must be one of {INVOICE_STATUSES}.")
    if not updates:
        return
    conn = _connect()
    try:
        assignments = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(f"UPDATE invoices SET {assignments} WHERE id = ?",
                     (*updates.values(), invoice_id))
        conn.commit()
    finally:
        conn.close()


def delete_invoice(invoice_id):
    """Removes an invoice and its payments.

    Cancelling is almost always the right move instead — a deleted invoice number leaves a
    hole in a tax-relevant sequence with no explanation. Kept for genuine mistakes.
    """
    conn = _connect()
    try:
        conn.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
        conn.commit()
    finally:
        conn.close()


# --- Payments ---------------------------------------------------------------------------

def add_payment(invoice_id, amount, paid_date=None, method="Bank Transfer", reference="",
                notes=""):
    """Records money received. Multiple payments per invoice is the normal case here — the
    company's own terms are 50% on confirmation and 50% before handover."""
    amount = float(amount or 0)
    if amount <= 0:
        raise ValueError("A payment must be a positive amount.")
    conn = _connect()
    try:
        if not conn.execute("SELECT 1 FROM invoices WHERE id = ?", (invoice_id,)).fetchone():
            raise ValueError(f"Invoice {invoice_id} not found.")
        cur = conn.execute(
            """INSERT INTO invoice_payments (invoice_id, amount, paid_date, method, reference, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (invoice_id, round(amount, 2),
             paid_date or datetime.now().strftime("%Y-%m-%d"), method, reference, notes),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def delete_payment(payment_id):
    conn = _connect()
    try:
        conn.execute("DELETE FROM invoice_payments WHERE id = ?", (payment_id,))
        conn.commit()
    finally:
        conn.close()


def get_payments(invoice_id):
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM invoice_payments WHERE invoice_id = ? ORDER BY paid_date, id",
            (invoice_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# --- Reading ----------------------------------------------------------------------------

def _enrich(row, today=None):
    """Adds the derived money facts. Never stored, so they cannot drift from the ledger."""
    d = dict(row)
    total = float(d.get("grand_total") or 0)
    paid = round(float(d.get("amount_paid") or 0), 2)
    balance = round(total - paid, 2)

    d["amount_paid"] = paid
    d["balance"] = balance
    if paid <= 0:
        d["payment_state"] = "Unpaid"
    elif balance > 0.01:
        d["payment_state"] = "Partial"
    else:
        d["payment_state"] = "Paid"

    today = today or datetime.now().strftime("%Y-%m-%d")
    due = (d.get("due_date") or "").strip()
    # Overdue is about money, not paperwork: a cancelled or settled invoice cannot be overdue
    # however old it is.
    d["is_overdue"] = bool(
        due and due < today and balance > 0.01 and d.get("status") != "Cancelled"
    )
    d["days_overdue"] = (
        (datetime.strptime(today, "%Y-%m-%d") - datetime.strptime(due, "%Y-%m-%d")).days
        if d["is_overdue"] else 0
    )
    return d


_SELECT = """
    SELECT i.*, COALESCE((SELECT SUM(p.amount) FROM invoice_payments p
                          WHERE p.invoice_id = i.id), 0) AS amount_paid
    FROM invoices i
"""


def get_invoices(status=None, limit=300, include_items=False):
    conn = _connect()
    try:
        where = "WHERE i.status = ?" if status else ""
        params = ([status] if status else []) + [limit]
        rows = conn.execute(
            f"{_SELECT} {where} ORDER BY i.id DESC LIMIT ?", params
        ).fetchall()
        out = []
        for row in rows:
            d = _enrich(row)
            raw = d.pop("items_json", None)
            try:
                parsed = json.loads(raw) if raw else []
            except Exception:
                parsed = []
            # The count is always present even when the lines are not — the list renders it,
            # and omitting a field the UI reads is how the history table broke once already.
            d["item_count"] = len(parsed)
            if include_items:
                d["items"] = parsed
            out.append(d)
        return out
    finally:
        conn.close()


def get_invoice(invoice_id):
    conn = _connect()
    try:
        row = conn.execute(f"{_SELECT} WHERE i.id = ?", (invoice_id,)).fetchone()
        if not row:
            return None
        d = _enrich(row)
        try:
            d["items"] = json.loads(d.pop("items_json") or "[]")
        except Exception:
            d["items"] = []
        d["item_count"] = len(d["items"])
        d["payments"] = get_payments(invoice_id)
        return d
    finally:
        conn.close()


def get_invoice_for_quotation(quotation_id):
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id FROM invoices WHERE quotation_id = ?", (quotation_id,)
        ).fetchone()
        return get_invoice(row["id"]) if row else None
    finally:
        conn.close()


# --- Reporting --------------------------------------------------------------------------

def client_statement(client_name):
    """Everything owed and paid by one client — what gets sent when chasing."""
    conn = _connect()
    try:
        rows = conn.execute(
            f"{_SELECT} WHERE LOWER(TRIM(i.client_name)) = LOWER(TRIM(?)) "
            f"AND i.status != 'Cancelled' ORDER BY i.issue_date, i.id",
            (client_name,),
        ).fetchall()
        invoices = [_enrich(r) for r in rows]
        for inv in invoices:
            inv.pop("items_json", None)
        billed = sum(i["grand_total"] for i in invoices)
        paid = sum(i["amount_paid"] for i in invoices)
        return {
            "client_name": client_name,
            "invoices": invoices,
            "total_billed": round(billed, 2),
            "total_paid": round(paid, 2),
            "total_outstanding": round(billed - paid, 2),
            "overdue_count": sum(1 for i in invoices if i["is_overdue"]),
        }
    finally:
        conn.close()


def aging_report():
    """Outstanding money bucketed by how late it is — the collections worklist."""
    buckets = {"current": 0.0, "1_30": 0.0, "31_60": 0.0, "61_90": 0.0, "over_90": 0.0}
    detail = []
    for inv in get_invoices(limit=10000):
        if inv["status"] == "Cancelled" or inv["balance"] <= 0.01:
            continue
        days = inv["days_overdue"]
        if days <= 0:
            buckets["current"] += inv["balance"]
        elif days <= 30:
            buckets["1_30"] += inv["balance"]
        elif days <= 60:
            buckets["31_60"] += inv["balance"]
        elif days <= 90:
            buckets["61_90"] += inv["balance"]
        else:
            buckets["over_90"] += inv["balance"]
        detail.append({
            "id": inv["id"], "invoice_number": inv["invoice_number"],
            "client_name": inv["client_name"], "balance": inv["balance"],
            "days_overdue": days, "due_date": inv["due_date"],
        })
    detail.sort(key=lambda d: d["days_overdue"], reverse=True)
    return {
        "buckets": {k: round(v, 2) for k, v in buckets.items()},
        "total_outstanding": round(sum(buckets.values()), 2),
        "invoices": detail,
    }


def vat_summary(start_date, end_date):
    """Output VAT charged on invoices issued in the period — the sales side of a VAT return.

    Cancelled invoices are excluded. Draft ones are included and counted separately, because
    an unsent invoice is not yet a taxable supply and filing on it would overstate the
    liability — the caller needs to see both numbers to decide.
    """
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT status, subtotal, discount_amount, vat, grand_total FROM invoices "
            "WHERE issue_date BETWEEN ? AND ? AND status != 'Cancelled'",
            (start_date, end_date),
        ).fetchall()
        issued = [r for r in rows if r["status"] != "Draft"]
        drafts = [r for r in rows if r["status"] == "Draft"]
        return {
            "start_date": start_date,
            "end_date": end_date,
            "invoice_count": len(issued),
            "net_sales": round(sum(float(r["subtotal"] or 0) - float(r["discount_amount"] or 0)
                                   for r in issued), 2),
            "output_vat": round(sum(float(r["vat"] or 0) for r in issued), 2),
            "gross_sales": round(sum(float(r["grand_total"] or 0) for r in issued), 2),
            "draft_count": len(drafts),
            "draft_vat_excluded": round(sum(float(r["vat"] or 0) for r in drafts), 2),
        }
    finally:
        conn.close()


def outstanding_total():
    """One number for the dashboard: everything not yet collected."""
    return aging_report()["total_outstanding"]


init_db()
