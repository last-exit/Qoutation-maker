# Red Cube Smart Quotation Engine

A desktop quotation tool (Python + [pywebview](https://pywebview.flowrl.com/) backend, HTML/JS frontend) for building, pricing, and exporting fit-out quotations. It parses historical Excel quotations and design drawings (PDF/PNG/JPG), matches items against a semantic index (ChromaDB + ONNX embeddings), and generates Excel/Word quotation documents.

## Installing on another machine

**Windows** — run `QuotationEngine-1.0.0-Setup.exe` and click through the wizard. Nothing else
is needed: no Python, no terminal, no `pip`, and no internet. The OCR and search models ship
inside the installer, so the app works offline from the first launch.

Windows will warn that the publisher is unknown, because the installer is not code-signed.
Click **More info → Run anyway**.

**Mac / Linux** — download the latest `QuotationEngine-*.zip`, unzip it, and double-click
`Setup Mac or Linux.command`. That creates a virtual environment, installs every dependency,
and starts the app; it takes a few minutes the first time and needs an internet connection.
Afterwards use `Run.command`.

### Where your data lives

Quotations, invoices, product photos, the search index and your edited rate card are stored
outside the application folder, so upgrading or uninstalling never touches them:

- **Windows** — `%LOCALAPPDATA%\QuotationEngine`
- **Mac** — `~/Library/Application Support/QuotationEngine`
- **Running from source** — the project folder, as before

Moving to a new machine means copying that folder across, with the app closed at both ends
(SQLite writes `-wal` sidecars, and copying mid-write takes a torn snapshot).

## Building the Windows installer

On a Windows PC with Python 3.11 or 3.12 and [Inno Setup 6](https://jrsoftware.org/isdl.php)
installed, double-click [installer/build_installer.bat](installer/build_installer.bat). It
creates an isolated build environment, downloads the OCR and search models, freezes the app
with PyInstaller and compiles the wizard, leaving the installer in `dist\installer\`.

It must be run on Windows — PyInstaller cannot cross-build, and Inno Setup's compiler is
Windows-only. Expect 15–30 minutes and roughly 2 GB of output.

## Running from source

```bash
pip install -r requirements.txt
python app.py
```

This opens a native desktop window (`pywebview`) loading `index.html`, backed by the `QuotationApi` class in [app.py](app.py).

## Building the distribution package

```bash
python packager.py
```

Writes a self-contained ZIP to your Desktop. The package uses an allowlist — only source code, configs, and assets are included. No databases, client records, images, or credentials are ever packaged.

## Project structure

- [app.py](app.py) — pywebview entry point, `QuotationApi` (JS-callable backend methods)
- [app.js](app.js) / [index.html](index.html) / [style.css](style.css) — frontend UI
- [design_parser.py](design_parser.py) — drawing parsing (PDF/PNG/JPG), dimension extraction, OCR
- [parsing.py](parsing.py) — historical Excel quotation parsing
- [rate_card.py](rate_card.py) — material/labor rate lookups and costing
- [doc_generator.py](doc_generator.py) — Excel/Word quotation document generation
- [calculators.py](calculators.py) — BOQ computation, area/perimeter calculations
- [history_db.py](history_db.py), [corrections_db.py](corrections_db.py), [catalog_db.py](catalog_db.py), [invoices_db.py](invoices_db.py), [jobs_db.py](jobs_db.py) — SQLite-backed data stores
- [image_store.py](image_store.py), [image_tools.py](image_tools.py) — content-addressed product photo storage
- [backup.py](backup.py) — encrypted backup and restore
- [paths.py](paths.py) — bundled resources vs. writable user data (see below)
- [packager.py](packager.py) — builds the macOS/source distribution ZIP
- [installer/](installer/) — Windows installer: PyInstaller spec, Inno Setup script, build script
- [embedder.py](embedder.py) — ONNX sentence embeddings for semantic search
- [sharing.py](sharing.py), [pdf_export.py](pdf_export.py) — quotation sharing and PDF export

## OCR for raster drawings

Vector PDF drawings parse dimensions from the embedded text layer — no OCR needed. Raster
drawings (PNG/JPG, e.g. SketchUp exports) need OCR to read dimension labels.

**The Windows installer includes OCR and its models.** Nothing to install, and it works
offline.

Running from source, or on Mac, install it alongside the other dependencies:

```bash
venv/bin/python -m pip install easyocr
```

It pulls roughly 2 GB of torch wheels and downloads its detection model on first use. It also
brings OpenCV, which is what recognises curved walls and ring shelves — without it every item
falls back to a flat panel, and a curved wall priced flat is under-quoted.

Without OCR the app still works: pages that cannot be read ask you to type the dimensions in,
and say so rather than reporting the drawing as blank.
