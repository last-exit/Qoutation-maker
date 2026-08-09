"""Jobs: what happens after a quotation is won.

A quotation says what a job should earn. Until now the app stopped there — it could tell you
a quote was Won and how much had been paid, but nothing about what the work actually cost, so
the margin figures were quoted estimates multiplied by a catalog cost that was usually
missing.

A job is the unit that costs attach to. Won quotation becomes a job; materials, crew hours,
transport and subcontractors get booked against it; margin becomes a measured number instead
of an aspiration.

Deliberately kept separate from `history_db` rather than bolted onto the quotations table: a
quotation is a document sent to a client and is finished the moment it is accepted, whereas a
job is a live thing that accumulates records for months afterwards. Mixing them would mean
every history query dragging cost rows behind it.
"""
import os
import re
from datetime import datetime

import db

DB_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "jobs.db"))

# A job's lifecycle. Deliberately short — this tracks delivery, not a project plan.
JOB_STATUSES = ["Planned", "In Progress", "Complete", "Cancelled"]

# What a cost is. Kept coarse enough that a PM will actually pick the right one under time
# pressure; a taxonomy nobody maintains is worse than four honest buckets.
COST_CATEGORIES = ["Material", "Labour", "Transport", "Subcontract", "Other"]

_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]")


def normalize_name(name):
    """Identity key for a supplier, matching how clients are normalized in history_db."""
    text = _PUNCT_RE.sub(" ", str(name or "").lower())
    return _WS_RE.sub(" ", text).strip().replace(" ", "")


def _connect():
    return db.connect(DB_FILE)


def _seed_job_counter(conn):
    conn.execute("INSERT OR REPLACE INTO job_counter (id, next_number) VALUES (1, 1)")


_MIGRATIONS = [
    (1, [
        """CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            normalized_name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )""",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_suppliers_norm ON suppliers(normalized_name)",

        """CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_number TEXT,
            quotation_id INTEGER,
            client_name TEXT,
            venue TEXT,
            title TEXT,
            status TEXT DEFAULT 'Planned',
            start_date TEXT,
            end_date TEXT,
            site_contact TEXT,
            quoted_total REAL DEFAULT 0,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )""",
        # One job per quotation. Booking the same work twice would double-count both the
        # revenue and the costs, which is the kind of error that only shows up at year end.
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_quotation
               ON jobs(quotation_id) WHERE quotation_id IS NOT NULL""",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_number ON jobs(job_number)",
        "CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, start_date)",

        """CREATE TABLE IF NOT EXISTS job_costs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            category TEXT NOT NULL DEFAULT 'Material',
            description TEXT NOT NULL,
            supplier_id INTEGER REFERENCES suppliers(id),
            quantity REAL DEFAULT 1,
            unit_cost REAL DEFAULT 0,
            amount REAL DEFAULT 0,
            cost_date TEXT,
            invoice_ref TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )""",
        "CREATE INDEX IF NOT EXISTS idx_job_costs_job ON job_costs(job_id)",
        "CREATE INDEX IF NOT EXISTS idx_job_costs_supplier ON job_costs(supplier_id)",

        """CREATE TABLE IF NOT EXISTS job_counter (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            next_number INTEGER NOT NULL
        )""",
        _seed_job_counter,
    ]),
]


def init_db():
    conn = _connect()
    try:
        return db.migrate(conn, _MIGRATIONS)
    finally:
        conn.close()


# --- Job numbering ----------------------------------------------------------------------

def allocate_job_number():
    """Reserves the next job number. Same never-reuse guarantee as quotation numbers: a job
    reference ends up on supplier paperwork and delivery notes, and two jobs sharing one is
    far worse than a gap in the sequence."""
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT next_number FROM job_counter WHERE id = 1").fetchone()
        number = int(row["next_number"]) if row else 1
        if row:
            conn.execute("UPDATE job_counter SET next_number = ? WHERE id = 1", (number + 1,))
        else:
            conn.execute("INSERT INTO job_counter (id, next_number) VALUES (1, ?)", (number + 1,))
        conn.execute("COMMIT")
        return f"J-{number}"
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


# --- Suppliers --------------------------------------------------------------------------

def resolve_supplier(conn, name, phone=None, email=None):
    """Finds or creates a supplier by normalized name."""
    name = str(name or "").strip()
    if not name:
        return None
    norm = normalize_name(name)
    row = conn.execute("SELECT id FROM suppliers WHERE normalized_name = ?", (norm,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute(
        "INSERT INTO suppliers (name, normalized_name, phone, email) VALUES (?, ?, ?, ?)",
        (name, norm, phone or "", email or ""),
    )
    return cur.lastrowid


def get_suppliers():
    """Suppliers with what has actually been spent with each — the number worth having when
    negotiating, and the only reason to keep a supplier list at all."""
    conn = _connect()
    try:
        rows = conn.execute("""
            SELECT s.*,
                   COUNT(c.id) AS cost_entries,
                   COALESCE(SUM(c.amount), 0) AS total_spend
            FROM suppliers s
            LEFT JOIN job_costs c ON c.supplier_id = s.id
            GROUP BY s.id
            ORDER BY total_spend DESC, s.name COLLATE NOCASE
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def save_supplier(supplier_id=None, name=None, phone=None, email=None, notes=None):
    conn = _connect()
    try:
        if supplier_id:
            existing = conn.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,)).fetchone()
            if not existing:
                raise ValueError(f"Supplier {supplier_id} not found.")
            new_name = str(name).strip() if name is not None else existing["name"]
            conn.execute(
                """UPDATE suppliers SET name = ?, normalized_name = ?, phone = ?, email = ?,
                       notes = ? WHERE id = ?""",
                (new_name, normalize_name(new_name),
                 phone if phone is not None else existing["phone"],
                 email if email is not None else existing["email"],
                 notes if notes is not None else existing["notes"],
                 supplier_id),
            )
            conn.commit()
            return supplier_id
        new_id = resolve_supplier(conn, name, phone, email)
        if notes and new_id:
            conn.execute("UPDATE suppliers SET notes = ? WHERE id = ?", (notes, new_id))
        conn.commit()
        return new_id
    finally:
        conn.close()


def delete_supplier(supplier_id):
    """Removes a supplier, leaving their cost entries in place but unattributed.

    Costs are facts about money that was spent; deleting them because a supplier record was
    tidied up would silently change every margin they contribute to.
    """
    conn = _connect()
    try:
        conn.execute("UPDATE job_costs SET supplier_id = NULL WHERE supplier_id = ?", (supplier_id,))
        conn.execute("DELETE FROM suppliers WHERE id = ?", (supplier_id,))
        conn.commit()
    finally:
        conn.close()


# --- Jobs -------------------------------------------------------------------------------

def create_job(quotation_id=None, client_name="", venue="", title="", quoted_total=0.0,
               start_date=None, end_date=None, site_contact="", notes=""):
    """Opens a job. Returns the job id, or the existing one if this quotation already has a job."""
    conn = _connect()
    try:
        if quotation_id:
            existing = conn.execute(
                "SELECT id FROM jobs WHERE quotation_id = ?", (quotation_id,)
            ).fetchone()
            if existing:
                return existing["id"]

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = conn.execute(
            """INSERT INTO jobs (job_number, quotation_id, client_name, venue, title, status,
                   start_date, end_date, site_contact, quoted_total, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'Planned', ?, ?, ?, ?, ?, ?, ?)""",
            (allocate_job_number(), quotation_id, client_name, venue, title,
             start_date or "", end_date or "", site_contact, float(quoted_total or 0), notes,
             now, now),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_job(job_id, **fields):
    allowed = {"client_name", "venue", "title", "status", "start_date", "end_date",
               "site_contact", "quoted_total", "notes"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return
    if "status" in updates and updates["status"] not in JOB_STATUSES:
        raise ValueError(f"Invalid job status '{updates['status']}'. Must be one of {JOB_STATUSES}.")

    conn = _connect()
    try:
        assignments = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE jobs SET {assignments}, updated_at = ? WHERE id = ?",
            (*updates.values(), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), job_id),
        )
        conn.commit()
    finally:
        conn.close()


def delete_job(job_id):
    conn = _connect()
    try:
        # ON DELETE CASCADE only fires with foreign keys on, which db.connect enables.
        conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        conn.commit()
    finally:
        conn.close()


def _job_row_to_dict(row):
    d = dict(row)
    quoted = float(d.get("quoted_total") or 0)
    actual = float(d.get("actual_cost") or 0)
    d["actual_cost"] = round(actual, 2)
    d["margin"] = round(quoted - actual, 2)
    d["margin_pct"] = round(100.0 * (quoted - actual) / quoted, 1) if quoted else 0.0
    # Says outright whether the margin is measured or merely quoted. A quoted margin
    # presented as a real one is how a business finds out it lost money after the fact.
    d["has_costs"] = bool(d.get("cost_entries"))
    return d


def get_jobs(status=None, limit=300):
    conn = _connect()
    try:
        where = "WHERE j.status = ?" if status else ""
        params = ([status] if status else []) + [limit]
        rows = conn.execute(f"""
            SELECT j.*,
                   COUNT(c.id) AS cost_entries,
                   COALESCE(SUM(c.amount), 0) AS actual_cost
            FROM jobs j
            LEFT JOIN job_costs c ON c.job_id = j.id
            {where}
            GROUP BY j.id
            ORDER BY
                CASE j.status WHEN 'In Progress' THEN 0 WHEN 'Planned' THEN 1 ELSE 2 END,
                COALESCE(NULLIF(j.start_date, ''), j.created_at)
            LIMIT ?
        """, params).fetchall()
        return [_job_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_job(job_id):
    conn = _connect()
    try:
        row = conn.execute("""
            SELECT j.*,
                   COUNT(c.id) AS cost_entries,
                   COALESCE(SUM(c.amount), 0) AS actual_cost
            FROM jobs j
            LEFT JOIN job_costs c ON c.job_id = j.id
            WHERE j.id = ?
            GROUP BY j.id
        """, (job_id,)).fetchone()
        if not row:
            return None
        job = _job_row_to_dict(row)
        job["costs"] = get_job_costs(job_id)
        job["cost_by_category"] = cost_breakdown(job_id)
        return job
    finally:
        conn.close()


def get_job_for_quotation(quotation_id):
    conn = _connect()
    try:
        row = conn.execute("SELECT id FROM jobs WHERE quotation_id = ?", (quotation_id,)).fetchone()
        return get_job(row["id"]) if row else None
    finally:
        conn.close()


# --- Costs ------------------------------------------------------------------------------

def add_job_cost(job_id, description, category="Material", supplier_name=None, quantity=1.0,
                 unit_cost=0.0, amount=None, cost_date=None, invoice_ref=""):
    """Books a cost against a job.

    `amount` is stored rather than derived so a supplier invoice can be entered at its actual
    total — real invoices carry rounding, delivery charges and part-quantities that
    quantity x unit_cost does not reproduce.
    """
    if category not in COST_CATEGORIES:
        raise ValueError(f"Invalid category '{category}'. Must be one of {COST_CATEGORIES}.")
    description = str(description or "").strip()
    if not description:
        raise ValueError("A cost needs a description.")

    conn = _connect()
    try:
        supplier_id = resolve_supplier(conn, supplier_name) if supplier_name else None
        qty = float(quantity or 0)
        unit = float(unit_cost or 0)
        total = float(amount) if amount not in (None, "") else qty * unit
        cur = conn.execute(
            """INSERT INTO job_costs (job_id, category, description, supplier_id, quantity,
                   unit_cost, amount, cost_date, invoice_ref)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (job_id, category, description, supplier_id, qty, unit, round(total, 2),
             cost_date or datetime.now().strftime("%Y-%m-%d"), invoice_ref or ""),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_job_cost(cost_id, **fields):
    allowed = {"category", "description", "quantity", "unit_cost", "amount", "cost_date",
               "invoice_ref"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if "category" in updates and updates["category"] not in COST_CATEGORIES:
        raise ValueError(f"Invalid category '{updates['category']}'.")
    if not updates:
        return
    conn = _connect()
    try:
        assignments = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(f"UPDATE job_costs SET {assignments} WHERE id = ?",
                     (*updates.values(), cost_id))
        conn.commit()
    finally:
        conn.close()


def delete_job_cost(cost_id):
    conn = _connect()
    try:
        conn.execute("DELETE FROM job_costs WHERE id = ?", (cost_id,))
        conn.commit()
    finally:
        conn.close()


def get_job_costs(job_id):
    conn = _connect()
    try:
        rows = conn.execute("""
            SELECT c.*, s.name AS supplier_name
            FROM job_costs c
            LEFT JOIN suppliers s ON s.id = c.supplier_id
            WHERE c.job_id = ?
            ORDER BY c.cost_date DESC, c.id DESC
        """, (job_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def cost_breakdown(job_id):
    """Spend per category, for seeing where a job actually went."""
    conn = _connect()
    try:
        rows = conn.execute("""
            SELECT category, COUNT(*) AS entries, COALESCE(SUM(amount), 0) AS total
            FROM job_costs WHERE job_id = ? GROUP BY category ORDER BY total DESC
        """, (job_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# --- Reporting --------------------------------------------------------------------------

def margin_report(period_days=90):
    """Quoted against actual across jobs, from money actually booked.

    Only jobs with at least one cost entry contribute. A job with no costs recorded would
    otherwise report 100% margin and quietly inflate the whole figure — the same mistake the
    old catalog-based margin made, in a different disguise.
    """
    conn = _connect()
    try:
        cutoff = datetime.now().strftime("%Y-%m-%d")
        rows = conn.execute("""
            SELECT j.id, j.job_number, j.client_name, j.title, j.status, j.quoted_total,
                   COUNT(c.id) AS cost_entries,
                   COALESCE(SUM(c.amount), 0) AS actual_cost
            FROM jobs j
            LEFT JOIN job_costs c ON c.job_id = j.id
            WHERE j.status != 'Cancelled'
              AND date(COALESCE(NULLIF(j.start_date,''), j.created_at)) >= date(?, ?)
            GROUP BY j.id
        """, (cutoff, f"-{int(period_days)} days")).fetchall()

        costed = [r for r in rows if r["cost_entries"]]
        quoted = sum(float(r["quoted_total"] or 0) for r in costed)
        actual = sum(float(r["actual_cost"] or 0) for r in costed)
        return {
            "period_days": period_days,
            "jobs_total": len(rows),
            "jobs_costed": len(costed),
            # Named so the UI can say how much of the period the figure actually covers.
            "jobs_without_costs": len(rows) - len(costed),
            "quoted_total": round(quoted, 2),
            "actual_cost": round(actual, 2),
            "margin": round(quoted - actual, 2),
            "margin_pct": round(100.0 * (quoted - actual) / quoted, 1) if quoted else 0.0,
        }
    finally:
        conn.close()


def upcoming_jobs(days=30):
    """Jobs starting or finishing inside the window — the crew schedule."""
    conn = _connect()
    try:
        rows = conn.execute("""
            SELECT * FROM jobs
            WHERE status IN ('Planned', 'In Progress')
              AND (
                (start_date != '' AND date(start_date) BETWEEN date('now') AND date('now', ?))
                OR (end_date != '' AND date(end_date) BETWEEN date('now') AND date('now', ?))
              )
            ORDER BY COALESCE(NULLIF(start_date,''), end_date)
        """, (f"+{int(days)} days", f"+{int(days)} days")).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


init_db()
