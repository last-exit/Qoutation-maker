# Invoices UI — Design Spec

Date: 2026-08-10
Status: Approved, pending implementation plan

## Problem

`invoices_db.py` and 9 `QuotationApi` methods implement a complete invoicing system —
invoice numbers, due dates, an itemized multi-payment ledger, VAT summary, an aging
report, and per-client statements — verified working end-to-end in a backend smoke test
this session (all 9 methods succeed against realistic data with no exceptions). None of
it is reachable from the UI. The sidebar nav item labeled **"Invoices"** actually routes
to `view-history`, the older quotation-lifecycle table (`history_db`'s simple
`payment_status`/`amount_paid` fields, edited via `update_payment(history_id, status,
amount)`). The two systems are unrelated in the code; only the label conflates them.

This spec wires the existing, unmodified backend into a real UI. **No new backend
methods or schema changes are needed or in scope** — every call below already exists and
already works.

Orphaned methods this wires up (`app.py`): `create_invoice_from_quotation`,
`get_invoices`, `get_invoice`, `update_invoice`, `delete_invoice`, `add_invoice_payment`,
`delete_invoice_payment`, `generate_invoice_document`, `get_client_statement`,
`get_vat_summary`, `get_aging_report`.

## 1. Nav & tab changes

- Add a new sidebar item, **Invoices**, after Jobs: `<button ... data-tab="invoices"
  aria-controls="view-invoices" onclick="switchTab('invoices')">` in `index.html`,
  following the exact markup pattern of the existing nav buttons (`index.html:21-27`).
  New panel `<main class="main-view hidden" id="view-invoices" ...>`.
- Relabel the current mislabeled tab: change its `<span class="nav-label">` from
  `Invoices` back to `History` (`index.html:27`). The `view-history` panel's own content,
  title ("Client & Quotation History"), and behavior are **unchanged** — only the nav
  label text.
- Fix stale copy: Jobs' empty state currently reads *"Mark a quotation Won in Invoices to
  open a job for it"* (`app.js:1814`) — this was correct when "Invoices" meant the
  history/status tab. Change it to *"Mark a quotation Won in History to open a job for
  it"*.
- `switchTab()` and `TAB_TITLES` (`app.js:456`) get an `invoices` entry, following the
  existing pattern for every other tab.

## 2. Raising an invoice

No new backend call. `create_invoice_from_quotation(history_id)` already exists
(`app.py:1586`) and already guards against double-invoicing: if the quotation was already
invoiced, it returns `{"success": false, "error": "...", "invoice_id": <existing id>}`
rather than a bare failure — the frontend must use that `invoice_id` when present, even
on failure, to open the existing invoice instead of just toasting an error.

- In `renderHistoryTable()` (`app.js:1289`), add a "Raise Invoice" button to the Actions
  cell, rendered only when `q.status === 'Won'`.
- On click: call `api().create_invoice_from_quotation(q.id)`. On success, or on failure
  with `res.invoice_id` present, switch to the Invoices tab and open that invoice's
  detail modal directly. On failure with no `invoice_id`, show the error toast as usual.

## 3. Invoices list view

Structurally mirrors the Jobs tab (`index.html:249-273`, `app.js` `loadJobs`/`renderJobs`
family) rather than inventing a new pattern:

- `view-header` with title "Invoices" and a "Reports" button (opens the reports modal,
  section 5).
- `stats-row` sourced from `get_aging_report()`'s totals: Outstanding, Overdue.
- Filter chips, client-side, same mechanism as `jobStatusFilter`
  (`app.js:1750`/`setJobFilter`): **All / Unpaid / Partial / Paid / Overdue**, filtering
  on each invoice's `payment_state` and `is_overdue` fields (both already computed by
  `invoices_db._enrich`, present on every row from `get_invoices()`).
- Row/card per invoice: invoice number, client name (a link — reuses the existing Client
  Ledger modal, `openClientLedger(name, phone)`, `app.js:1372`), venue, due date, grand
  total, a payment-state pill reusing `status-pill-won` (Paid) / `status-pill-sent`
  (Partial) / `chip-muted` (Unpaid) with `stat-danger` styling layered on when
  `is_overdue`, a status `<select>` (Draft/Sent/Cancelled) matching the inline-dropdown
  pattern Jobs uses for its own status (`app.js:1830` `changeJobStatus` →
  `update_job(id, {status})`; same shape here calling `update_invoice(id, {status})`),
  and a "View" action opening the detail modal.
- Empty state: matches the Jobs/History empty-state visual pattern
  (`icon + <p>` inside `.empty-state`).

## 4. Invoice detail modal

New modal `invoice-detail-modal-overlay`, structurally mirroring
`job-costs-modal-overlay` (`app.js` `openJob`/`renderJobCosts` family):

- Header: invoice number, client, venue, issue/due dates.
- Read-only line-items table with totals (subtotal, discount, VAT, grand total) — these
  are frozen at raise-time by design (`invoices_db.py`'s own docstring: figures are
  copied, not recomputed, because "the invoice must say what the client agreed to").
- Payment ledger: list of payments (`get_invoice(id).payments`), each with a delete
  action (`delete_invoice_payment`). A "Record Payment" form (amount, date, method
  dropdown from `invoices_db.PAYMENT_METHODS`, reference, notes) calling
  `add_invoice_payment(invoice_id, amount, paid_date, method, reference, notes)` —
  note this method takes flat positional/keyword args, **not** a payload dict (confirmed
  against `app.py:1636` during the backend smoke test).
- "Generate Document" button calling `generate_invoice_document(invoice_id)`. The
  backend already opens the resulting file itself (`pdf_export.open_file(...)`,
  `app.py:1687`) and returns `{docx_path, pdf_path}`; the frontend reuses the existing
  `showSuccessModal` pattern (`app.js:1186`, same one `compileQuote` uses) to confirm
  what was written rather than inventing a new confirmation UI.

## 5. Reports

- "Reports" button on the Invoices view-header opens a modal with two sections:
  - **VAT Summary**: start/end date inputs (default: current calendar year), calling
    `get_vat_summary(start_date, end_date)`, rendering `net_sales`, `output_vat`,
    `gross_sales`, `invoice_count`, and `draft_count`/`draft_vat_excluded` (drafts are
    shown separately since they're explicitly not yet taxable supplies per the backend's
    own docstring).
  - **Aging Report**: the five buckets (`current`, `1_30`, `31_60`, `61_90`, `over_90`)
    from `get_aging_report()`, plus its `invoices` worklist, each row clickable through
    to that invoice's detail modal.
- **Client Statement** gets no new surface. It's added as a second section inside the
  *existing* Client Ledger modal (`client-ledger-modal-overlay`, already reachable from
  client-name links in History and now also from Invoices rows), calling
  `get_client_statement(client_name)` alongside the modal's existing
  `get_client_ledger` section.

## 6. Error handling

No new convention — every call follows the `if (!res.success) { showToast(res.error,
'error'); return; }` pattern already used throughout `app.js`. The one deliberate
exception is section 2's `invoice_id`-on-failure handling for the double-invoice guard.
`add_invoice_payment`'s amount-must-be-positive validation (`invoices_db.py:226`)
surfaces as a toast via the standard path — no special-casing needed.

## 7. Testing

- Extend `tests/test_js_api_contract.py` (`called_methods()` already regex-scans
  `app.js` for `api().method(...)` calls) so the 9 previously-orphaned methods are
  covered by the existing "every field the frontend reads is present" style of check,
  the same way `get_history`/`renderHistoryTable` are covered today — this is what would
  have caught the orphaned-feature gap in the first place had it existed.
- Add `invoices_db` unit tests (new `tests/test_invoices_db.py`, following the pattern of
  `tests/test_history_db.py`) specifically for `aging_report()`'s bucket boundaries and
  `vat_summary()`'s draft-exclusion logic — the two places wrong arithmetic would be easy
  to ship silently, per this codebase's own stated testing philosophy (coarse contract
  tests catch missing fields, not wrong values; targeted unit tests catch wrong values).
- Manual verification: raise an invoice from a Won quotation, record a partial payment,
  confirm the payment-state pill updates, generate the Word/Excel document and confirm it
  opens, check the aging report buckets a backdated due date correctly.

## Out of scope

- Any change to `invoices_db.py`, `app.py`'s invoice methods, or the invoice data model —
  all verified working as-is.
- A "blank" invoice creation flow not tied to a quotation (no backend support for this
  exists; only `create_invoice_from_quotation` is exposed).
- `delete_invoice` UI (cancelling via the status dropdown is the intended path per the
  backend's own docstring — deletion is "kept for genuine mistakes," not a first-class
  flow. If a delete affordance turns out to be wanted, it's a small follow-up, not part of
  this build).
