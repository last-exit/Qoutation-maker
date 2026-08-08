# Red Cube Smart Quotation Engine

A desktop quotation tool (Python + [pywebview](https://pywebview.flowrl.com/) backend, HTML/JS frontend) for building, pricing, and exporting fit-out quotations. It parses historical Excel quotations and design drawings (PDF/PNG/JPG), matches items against a semantic index (ChromaDB + sentence-transformers), and generates Excel/Word quotation documents.

## Running the app

```bash
python app.py
```

This opens a native desktop window (`pywebview`) loading `index.html`, backed by the `QuotationApi` class in [app.py](app.py).

## Setup

```bash
pip install -r requirements.txt   # if present, otherwise see imports in app.py
```

### Optional: OCR for raster drawings (PNG/JPG dimension detection)

Vector PDF drawings parse dimensions exactly from the embedded text layer — no OCR needed. Raster drawings (PNG/JPG screenshots, e.g. SketchUp exports) need OCR to read dimension labels off the image. Without an OCR backend installed, [`design_parser.ocr_status()`](design_parser.py:327) reports unavailable and all dimensions on raster pages come back as `0`, so estimator items price at `0.00`.

To enable it, install one of, **into this project's `venv`** (the app runs on `venv\Scripts\python.exe`, not the system Python — installing to the wrong interpreter is a common gotcha):

```bash
# Recommended: lightweight, needs the Tesseract binary too
venv\Scripts\python.exe -m pip install pytesseract
winget install --id UB-Mannheim.TesseractOCR -e   # Windows; adds tesseract.exe

# Alternative: heavier (~2GB, pulls in torch), no separate binary needed
venv\Scripts\python.exe -m pip install easyocr
```

The Tesseract installer adds `C:\Program Files\Tesseract-OCR` to PATH, but only for *new* shells/processes started after install — an already-open terminal or already-running app won't see it. After installing, **close any open terminal, open a fresh one, and restart the app** (`python app.py`) so both the new PATH and the new package are picked up. Verify with:

```bash
venv\Scripts\python.exe -c "import design_parser; print(design_parser.ocr_status())"
```

## Project structure

- [app.py](app.py) — pywebview entry point, `QuotationApi` (JS-callable backend methods)
- [app.js](app.js) / [index.html](index.html) — frontend UI
- [design_parser.py](design_parser.py) — drawing parsing (PDF/PNG/JPG), dimension extraction, OCR
- [parsing.py](parsing.py) — historical Excel quotation parsing
- [rate_card.py](rate_card.py) — material/labor rate lookups and costing (`RateCard.cost_of()`)
- [doc_generator.py](doc_generator.py) — Excel/Word quotation document generation
- [history_db.py](history_db.py), [corrections_db.py](corrections_db.py) — SQLite-backed history and correction storage
- [image_tools.py](image_tools.py), [pdf_export.py](pdf_export.py), [sharing.py](sharing.py), [calculators.py](calculators.py) — supporting utilities

## Knowledge graph (graphify)

This project has a knowledge graph in `graphify-out/` (god nodes, community structure, cross-file relationships). For codebase questions, prefer:

```bash
graphify query "<question>"
graphify path "<A>" "<B>"
graphify explain "<concept>"
```

Run `graphify update .` after code changes to keep the graph current.
