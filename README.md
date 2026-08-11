# Red Cube Smart Quotation Engine

A desktop quotation tool (Python + [pywebview](https://pywebview.flowrl.com/) backend, HTML/JS frontend) for building, pricing, and exporting fit-out quotations. It parses historical Excel quotations and design drawings (PDF/PNG/JPG), matches items against a semantic index (ChromaDB + ONNX embeddings), and generates Excel/Word quotation documents.

## Installing on another machine

Download the latest `QuotationEngine-*.zip`, unzip it, and double-click:

- **Windows** — `Setup Windows.bat`
- **Mac / Linux** — `Setup Mac or Linux.command`

That creates a virtual environment, installs every dependency, and starts the app. It takes a few minutes the first time and needs an internet connection. After that, use `Run.bat` (Windows) or `Run.command` (Mac) to launch.

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
- [packager.py](packager.py) — builds the distribution ZIP
- [embedder.py](embedder.py) — ONNX sentence embeddings for semantic search
- [sharing.py](sharing.py), [pdf_export.py](pdf_export.py) — quotation sharing and PDF export

## Optional: OCR for raster drawings

Vector PDF drawings parse dimensions from the embedded text layer — no OCR needed. Raster drawings (PNG/JPG, e.g. SketchUp exports) need OCR to read dimension labels.

```bash
# Recommended: lightweight, needs the Tesseract binary too
venv\Scripts\python.exe -m pip install pytesseract
winget install --id UB-Mannheim.TesseractOCR -e

# Alternative: heavier (~2 GB), no separate binary needed
venv\Scripts\python.exe -m pip install easyocr
```

Without OCR, the app still works — pages that cannot be read ask you to type the dimensions in.
