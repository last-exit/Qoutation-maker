# Red Cube ERP — Odoo deployment

Odoo 19 Community + PostgreSQL (pgvector), running locally in Docker, with a custom addon
that carries the parts of the quoting workflow Odoo has no concept of.

## Why Odoo, and what stays ours

Odoo prices a quotation from a product's list price. That works when you sell a catalogue; it
does not work for bespoke builds, where the honest answer to "what do we charge for this" is
"what did we charge last time we built something like it".

So the split is:

| Concern | Where it lives |
|---|---|
| Clients, quotations, sales orders | Odoo `sale_management` |
| Purchase orders, supplier price lists | Odoo `purchase` |
| Invoicing, payments, 5% UAE VAT | Odoo `account` + `l10n_ae` |
| Job costing, timesheets | Odoo `project` + `hr_timesheet` |
| **Historical price archive + semantic search** | `redcube_price_intelligence` |
| **Photo extraction, dedup, cross-fill** | `redcube_price_intelligence` |
| **Review queue and durable corrections** | `redcube_price_intelligence` |

### Community vs Enterprise

Verified against `github.com/odoo/odoo` @ 19.0 — a module in that repo is Community (free).

Community: `sale_management`, `purchase`, `project`, `hr_timesheet`, `account` (invoicing),
`l10n_ae` (UAE chart of accounts and 5% VAT).

Enterprise only: `l10n_ae_reports` (the FTA-format **VAT return**), `account_reports`,
`account_accountant` (bank sync, full accounting), `planning` (shift scheduling),
`industry_fsm` (field service).

Practical effect: you can issue VAT-compliant invoices and track payments on Community, but
generating the VAT return for filing needs Enterprise or a third-party module. Crew scheduling
works via `project` tasks with dates; drag-and-drop resource planning needs Enterprise.

## Running it

Double-click **`run-odoo.command`** in the project root. It starts the Docker VM if it is not
already up, starts the containers, waits until Odoo actually answers, and opens the browser.
Safe to run when everything is already running.

**`stop-odoo.command`** stops it again. Data lives in Docker volumes, not in the containers,
so stopping loses nothing.

From a terminal instead:

```bash
colima start          # the Linux VM the containers run in; only needed after a reboot
cd odoo && docker compose up -d
```

Then open <http://127.0.0.1:8069> and log in as **admin**. The password is
`ODOO_ADMIN_PASSWORD` in `odoo/.env`, which is gitignored.

### Where things are

Everything custom is under the **Price Archive** app in the top-left app menu:

| Menu | What it is |
|---|---|
| Archive → Search Archive | Describe a structure, see what comparable work was quoted at |
| Archive → Price Archive | All indexed historical line items |
| Archive → Source Documents | Every document read, with how many lines and photos it gave |
| Archive → Index Archive | Re-read the quotation folder. Incremental — unchanged files are skipped |
| Archive → Import Desktop Data | One-time import of the old app's clients, catalog and history |
| Review → Needs Review | Items the parser could not read confidently |
| Review → Corrections | Fixes that survive re-indexing, and which fields each one pins |

Quoting happens in the standard **Sales** app. Open a quotation and use the **Price from
Archive** button in the top-right button box to search the archive and pull priced lines in.
Print with the **Quotation** report.

### Common tasks

```bash
cd odoo

docker compose logs -f odoo            # watch the log
docker compose restart odoo            # after changing addon Python
docker compose exec odoo odoo -d redcube -u redcube_price_intelligence --stop-after-init
                                       # reload the addon after changing views or models
docker compose exec odoo odoo -d redcube --test-enable \
    --test-tags redcube_price_intelligence -u redcube_price_intelligence \
    --stop-after-init --http-port 8099 # run the addon tests
```

The test command uses a different port on purpose: the running instance already holds 8069,
and Odoo exits with "Address already in use" otherwise.

First-time setup on a fresh machine:

```bash
cp .env.example .env                       # then fill in real values
cp config/odoo.conf.example config/odoo.conf
docker compose build
docker compose up -d
docker compose exec odoo odoo -d redcube \
    -i base,sale_management,purchase,project,hr_timesheet,l10n_ae,redcube_price_intelligence \
    --without-demo=all --stop-after-init
docker compose restart odoo
```

Reload the addon after editing it:

```bash
docker compose exec odoo odoo -d redcube -u redcube_price_intelligence --stop-after-init
docker compose restart odoo
```

## Notable configuration choices

**Port bound to `127.0.0.1`.** This instance holds every rate the company has quoted and every
client's contact details. It does not listen on the LAN until that is a deliberate decision.

**Images pinned to dated tags** (`odoo:19.0-20260803`, not `odoo:19.0`). A floating tag means
an unattended `docker compose pull` can change the application version under a live database
and force an upgrade nobody asked for.

**pgvector, not a separate vector database.** Embeddings live in the same Postgres as the
records they describe, so similarity search is a SQL join rather than a second datastore to
keep in sync. The previous desktop build used ChromaDB, and keeping two stores consistent was
a recurring source of trouble — including one incident where truncating Chroma's write log
reclaimed 179 MB and silently broke every lookup.

**No PyTorch.** Embeddings run on `onnxruntime` against a pre-exported all-MiniLM-L6-v2
(`tools/export_onnx.py`, verified at cosine 1.000000 against sentence-transformers). That is
~90 MB instead of ~340 MB in the image.

**Long request timeouts** (`limit_time_real = 3600`). Re-indexing the archive parses hundreds
of documents and embeds every line item; the stock 120s cap kills it well before it finishes.

## Custom addon layout

```
addons/redcube_price_intelligence/
  models/
    archive_source.py      Source documents, with fingerprints for incremental re-index
    archive_item.py        One historical line item; content-hash identity
    archive_correction.py  PM corrections, keyed to survive a rebuild
  security/                Two-level access: read the archive vs. rewrite it
  views/                   List, form, search, and the review queue
```

### Two design decisions worth knowing

**Archive items are not products.** They are observations of what was quoted on a particular
job on a particular date. Several items commonly describe the same structure at different
prices, and that spread is the useful information — collapsing them into one
`product.template` would throw it away.

**Corrections record which fields a human actually edited.** In the previous build every
review action snapshotted rate, unit and venue together and re-applied all three on re-index,
so setting a venue in bulk — or merely dismissing a review flag — froze that item's price
permanently, and a later price change in the source spreadsheet could never reach the system.
`corrected_field_ids` fixes that; an empty list means "reviewed and deliberately left as-is",
which clears the flag without pinning anything.

## Not done yet

- The indexer itself: porting `parsing.py`, `image_store.py` and `embedder.py` from the
  desktop app into the addon, plus a pgvector column and similarity search.
- The quotation-side UI: searching the archive from a `sale.order` and dropping in priced lines.
- Importing existing clients, catalog and quote history from the desktop app's SQLite.
- Archive root configuration — pointing at a local folder or NAS share instead of Drive.
