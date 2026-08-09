"""Invoices and the payment ledger against them."""
import pytest


@pytest.fixture
def inv(tmp_path, monkeypatch):
    import invoices_db
    monkeypatch.setattr(invoices_db, "DB_FILE", str(tmp_path / "invoices.db"))
    invoices_db.init_db()
    return invoices_db


def make(inv, total=10500.0, **kw):
    payload = dict(
        client_name="Acme360",
        items=[{"description": "Pirate Ship", "qty": 1, "rate": 10000.0}],
        subtotal=10000.0, vat=500.0, grand_total=total,
    )
    payload.update(kw)
    return inv.create_invoice(**payload)


# --- Numbering ---------------------------------------------------------------------------

def test_numbers_are_sequential_and_padded(inv):
    a, b = make(inv), make(inv)
    assert inv.get_invoice(a)["invoice_number"] == "INV-0001"
    assert inv.get_invoice(b)["invoice_number"] == "INV-0002"


def test_numbers_are_never_reused(inv):
    """An invoice number is a tax record. Two invoices sharing one is a filing problem."""
    first = make(inv)
    number = inv.get_invoice(first)["invoice_number"]
    inv.delete_invoice(first)
    assert inv.get_invoice(make(inv))["invoice_number"] != number


def test_numbers_survive_concurrent_creation(inv):
    import threading
    seen, lock = [], threading.Lock()

    def grab():
        n = inv.allocate_invoice_number()
        with lock:
            seen.append(n)

    threads = [threading.Thread(target=grab) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(set(seen)) == 10


def test_peek_does_not_consume(inv):
    peeked = inv.peek_invoice_number()
    assert inv.peek_invoice_number() == peeked
    assert inv.get_invoice(make(inv))["invoice_number"] == peeked


# --- Creating ----------------------------------------------------------------------------

def test_invoice_needs_a_client_and_lines(inv):
    with pytest.raises(ValueError):
        inv.create_invoice(client_name="  ", items=[{"x": 1}])
    with pytest.raises(ValueError):
        inv.create_invoice(client_name="Acme", items=[])


def test_a_quotation_cannot_be_invoiced_twice(inv):
    """Double-billing surfaces as an angry client, not as a crash."""
    make(inv, quotation_id=7)
    with pytest.raises(ValueError, match="already been invoiced"):
        make(inv, quotation_id=7)


def test_due_date_follows_the_payment_terms(inv):
    invoice = inv.get_invoice(make(inv, issue_date="2026-01-01", payment_terms_days=30))
    assert invoice["issue_date"] == "2026-01-01"
    assert invoice["due_date"] == "2026-01-31"


def test_invalid_status_is_rejected(inv):
    invoice_id = make(inv)
    with pytest.raises(ValueError):
        inv.update_invoice(invoice_id, status="Nearly Paid")


# --- Payments ----------------------------------------------------------------------------

def test_the_companys_own_fifty_fifty_terms_work(inv):
    """50% on confirmation, 50% before handover — two payments against one invoice, which a
    single amount_paid field cannot express."""
    invoice_id = make(inv, total=10500.0)
    inv.add_payment(invoice_id, 5250.0, paid_date="2026-01-05", reference="ADV-1")

    half = inv.get_invoice(invoice_id)
    assert half["amount_paid"] == 5250.0
    assert half["balance"] == 5250.0
    assert half["payment_state"] == "Partial"

    inv.add_payment(invoice_id, 5250.0, paid_date="2026-02-01", reference="FINAL-1")
    settled = inv.get_invoice(invoice_id)
    assert settled["amount_paid"] == 10500.0
    assert settled["balance"] == 0.0
    assert settled["payment_state"] == "Paid"
    assert len(settled["payments"]) == 2


def test_unpaid_invoice_state(inv):
    invoice = inv.get_invoice(make(inv))
    assert invoice["payment_state"] == "Unpaid"
    assert invoice["balance"] == 10500.0


def test_payment_must_be_positive(inv):
    invoice_id = make(inv)
    for bad in (0, -100):
        with pytest.raises(ValueError):
            inv.add_payment(invoice_id, bad)


def test_payment_against_a_missing_invoice_is_refused(inv):
    with pytest.raises(ValueError):
        inv.add_payment(9999, 100)


def test_removing_a_payment_reopens_the_balance(inv):
    """Derived from the ledger, so deleting a payment cannot leave a stale total behind."""
    invoice_id = make(inv)
    payment_id = inv.add_payment(invoice_id, 10500.0)
    assert inv.get_invoice(invoice_id)["payment_state"] == "Paid"

    inv.delete_payment(payment_id)
    reopened = inv.get_invoice(invoice_id)
    assert reopened["payment_state"] == "Unpaid"
    assert reopened["balance"] == 10500.0


def test_deleting_an_invoice_removes_its_payments(inv):
    invoice_id = make(inv)
    inv.add_payment(invoice_id, 100)
    inv.delete_invoice(invoice_id)
    assert inv.get_payments(invoice_id) == []


def test_overpayment_settles_rather_than_going_negative(inv):
    invoice_id = make(inv, total=1000.0)
    inv.add_payment(invoice_id, 1200.0)
    invoice = inv.get_invoice(invoice_id)
    assert invoice["payment_state"] == "Paid"
    assert invoice["balance"] == -200.0, "the overpayment stays visible rather than being hidden"


# --- Overdue -----------------------------------------------------------------------------

def test_an_unpaid_invoice_past_its_due_date_is_overdue(inv):
    invoice_id = make(inv, issue_date="2026-01-01", payment_terms_days=1)
    invoice = inv.get_invoice(invoice_id)
    assert invoice["is_overdue"] is True
    assert invoice["days_overdue"] > 0


def test_a_settled_invoice_is_never_overdue(inv):
    """Overdue is about money, not paperwork age."""
    invoice_id = make(inv, total=500.0, issue_date="2026-01-01", payment_terms_days=1)
    inv.add_payment(invoice_id, 500.0)
    assert inv.get_invoice(invoice_id)["is_overdue"] is False


def test_a_cancelled_invoice_is_never_overdue(inv):
    invoice_id = make(inv, issue_date="2026-01-01", payment_terms_days=1)
    inv.update_invoice(invoice_id, status="Cancelled")
    assert inv.get_invoice(invoice_id)["is_overdue"] is False


# --- Reporting ---------------------------------------------------------------------------

def test_client_statement_totals(inv):
    a = make(inv, total=1000.0)
    make(inv, total=2000.0)
    inv.add_payment(a, 400.0)

    statement = inv.client_statement("acme360")
    assert len(statement["invoices"]) == 2
    assert statement["total_billed"] == 3000.0
    assert statement["total_paid"] == 400.0
    assert statement["total_outstanding"] == 2600.0


def test_client_statement_excludes_cancelled(inv):
    keep = make(inv, total=1000.0)
    drop = make(inv, total=5000.0)
    inv.update_invoice(drop, status="Cancelled")
    assert inv.client_statement("Acme360")["total_billed"] == 1000.0
    assert [i["id"] for i in inv.client_statement("Acme360")["invoices"]] == [keep]


def test_aging_buckets_by_lateness(inv):
    current = make(inv, total=1000.0, issue_date="2026-01-01", payment_terms_days=36500)
    late = make(inv, total=2000.0, issue_date="2026-01-01", payment_terms_days=1)

    report = inv.aging_report()
    assert report["buckets"]["current"] == 1000.0
    assert report["total_outstanding"] == 3000.0
    assert report["invoices"][0]["id"] == late, "the latest should sort first"
    assert current in [i["id"] for i in report["invoices"]]


def test_aging_ignores_settled_and_cancelled(inv):
    paid = make(inv, total=1000.0, issue_date="2026-01-01", payment_terms_days=1)
    inv.add_payment(paid, 1000.0)
    cancelled = make(inv, total=9000.0, issue_date="2026-01-01", payment_terms_days=1)
    inv.update_invoice(cancelled, status="Cancelled")

    assert inv.aging_report()["total_outstanding"] == 0.0


def test_vat_summary_covers_sent_invoices_and_flags_drafts(inv):
    """A draft is not a taxable supply. Filing on it would overstate the liability, so it is
    excluded — and reported separately so the exclusion is visible."""
    sent = make(inv, total=10500.0, issue_date="2026-02-10")
    inv.update_invoice(sent, status="Sent")
    make(inv, total=2100.0, issue_date="2026-02-15")  # left as Draft

    summary = inv.vat_summary("2026-02-01", "2026-02-28")
    assert summary["invoice_count"] == 1
    assert summary["output_vat"] == 500.0
    assert summary["net_sales"] == 10000.0
    assert summary["draft_count"] == 1
    assert summary["draft_vat_excluded"] == 500.0


def test_vat_summary_respects_the_period(inv):
    old = make(inv, issue_date="2025-12-31")
    inv.update_invoice(old, status="Sent")
    assert inv.vat_summary("2026-01-01", "2026-03-31")["invoice_count"] == 0


def test_vat_summary_subtracts_discount_from_net_sales(inv):
    invoice_id = make(inv, subtotal=10000.0, discount_amount=1000.0, vat=450.0,
                      total=9450.0, issue_date="2026-02-10")
    inv.update_invoice(invoice_id, status="Sent")
    summary = inv.vat_summary("2026-02-01", "2026-02-28")
    assert summary["net_sales"] == 9000.0


def test_list_omits_line_items_but_keeps_the_count(inv):
    make(inv, items=[{"description": "A", "qty": 1, "rate": 1},
                     {"description": "B", "qty": 1, "rate": 2}])
    row = inv.get_invoices()[0]
    assert "items" not in row
    assert row["item_count"] == 2
    assert len(inv.get_invoices(include_items=True)[0]["items"]) == 2
