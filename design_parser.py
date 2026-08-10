"""Multi-file, multi-page intake for design drawings feeding the Automated Design Estimator.

Handles two very different inputs:

* **Vector PDFs** (SketchUp/AutoCAD/Layout exports). Text is read losslessly with PyMuPDF,
  so a 25-page deck yields exact dimension strings with no OCR error at all. This is the
  path that matters — it is where the numbers are trustworthy.
* **Raster images** (PNG/JPG site photos, screenshots). There is no embedded text, so
  dimensions can only come from OCR, which is optional here (see `ocr_status`). When OCR
  is unavailable the page still loads with its thumbnail and the PM types the dimensions
  into the override fields, which is a supported workflow rather than a failure.

Nothing in this module prices anything or decides a cost — it only reports what the
drawing says. `calculators.py` owns all arithmetic.
"""

import os
import re
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image as PILImage

import image_tools

SUPPORTED_PDF = {".pdf"}
SUPPORTED_RASTER = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
SUPPORTED_EXTENSIONS = SUPPORTED_PDF | SUPPORTED_RASTER

# Render scale for PDF page previews. 2x the 72dpi default gives a ~144dpi preview that
# stays readable when a PM zooms into a dimension callout in the side-by-side view.
PDF_RENDER_SCALE = 2.0
PREVIEW_MAX_PX = (1600, 1600)

# Guard against a 300-page deck locking the UI. The cap is reported, never silent.
MAX_PAGES_PER_FILE = 60


# --- Item classification --------------------------------------------------------------
# Ordered most specific first: "reception counter" must classify as a counter, not a wall,
# even though a drawing sheet often carries both words.

TYPE_KEYWORDS = [
    ("counter", ("kiosk counter", "reception counter", "bar counter", "counter", "kiosk",
                 "reception desk", "cash desk", "bar unit", "servery", "podium counter")),
    ("arch",    ("main arch", "entrance arch", "archway", "portal", "gateway", "arch")),
    ("stage",   ("stage", "riser", "platform", "deck", "podium", "catwalk", "runway")),
    ("wall",    ("feature wall", "backdrop", "back drop", "partition", "wall", "panel wall",
                 "media wall", "step and repeat", "fascia")),
]

# Words that mark a text run as a drawing title rather than a note or a dimension.
TITLE_HINTS = (
    "wall", "counter", "kiosk", "arch", "stage", "backdrop", "partition", "platform",
    "riser", "booth", "display", "elevation", "plan", "section", "detail", "unit",
)

# Text that is definitely not a title, even when it is the largest thing on the page.
TITLE_NOISE = re.compile(
    r"^(scale|drawn|checked|date|rev|sheet|drawing\s*no|project|client|title|dwg|page)\b",
    re.IGNORECASE,
)

CUTOUT_KEYWORDS = ("window", "niche", "opening", "cut out", "cutout", "cut-out", "void",
                   "screen", "tv", "recess", "aperture", "display box")

# Phrases that pair a dimension with the word "opening" while describing the item's own
# envelope rather than a hole in it. On an arch drawing "CLEAR OPENING 4000 x 3500" is the
# overall size; treating it as a cutout subtracts the entire item and prices it at zero.
ENVELOPE_PHRASES = ("clear opening", "overall", "external", "envelope", "structural opening",
                    "finished opening", "o/a", "outer", "total size")

# A cutout this close to the full envelope is the envelope restated, not a void.
_ENVELOPE_MATCH_TOLERANCE = 0.02   # 2% on each side
_MAX_CUTOUT_AREA_RATIO = 0.90      # a real void never removes >90% of the clad face


# --- Dimension extraction ---------------------------------------------------------------

# "2400mm", "2.4 m", "240 cm", "1200 MM" — an explicit unit is the reliable case.
_UNIT_DIM = re.compile(
    r"(?<![\w.])(\d{1,6}(?:[.,]\d{1,3})?)\s*(mm|cm|m)(?![\w])",
    re.IGNORECASE,
)

# "2400 x 1200", "2400x1200x600", "2.4 X 3.0" — paired/tripled dimensions, unit optional.
_PAIR_DIM = re.compile(
    r"(?<![\w.])(\d{1,6}(?:[.,]\d{1,3})?)\s*(?:mm|cm|m)?\s*[xX×]\s*"
    r"(\d{1,6}(?:[.,]\d{1,3})?)\s*(?:mm|cm|m)?"
    r"(?:\s*[xX×]\s*(\d{1,6}(?:[.,]\d{1,3})?)\s*(?:mm|cm|m)?)?",
    re.IGNORECASE,
)

# Bare integers that read as millimetre callouts on a leader line.
_BARE_DIM = re.compile(r"(?<![\w.,])(\d{3,5})(?![\w.,])")


def _to_meters(value, unit):
    """Normalizes a magnitude + unit to metres."""
    value = float(str(value).replace(",", "."))
    unit = (unit or "").lower()
    if unit == "mm":
        return value / 1000.0
    if unit == "cm":
        return value / 100.0
    if unit == "m":
        return value
    return value


def _infer_bare_unit(value):
    """Guesses the unit of a dimension written without one.

    Drawing convention in this trade is millimetres, so a bare 2400 means 2.4 m. The
    thresholds below are heuristics and are surfaced to the PM as `assumed_unit` on every
    dimension they touch — the UI shows them as editable, never as settled fact.
    """
    if value >= 100:
        return "mm"
    if value >= 10:
        return "cm"
    return "m"


def extract_dimensions(text):
    """Pulls every dimension-looking token out of a blob of drawing text.

    Returns a list of dicts: {raw, meters, unit, assumed_unit, kind}. Ordering is
    preserved so downstream code can prefer the first (usually largest/leading) callout.
    """
    found = []
    seen = set()

    for match in _PAIR_DIM.finditer(text):
        groups = [g for g in match.groups() if g]
        if len(groups) < 2:
            continue
        raw = match.group(0).strip()
        if raw in seen:
            continue
        seen.add(raw)

        unit_match = re.search(r"(mm|cm|m)\b", raw, re.IGNORECASE)
        unit = unit_match.group(1).lower() if unit_match else None
        components = []
        for value in groups:
            numeric = float(str(value).replace(",", "."))
            resolved = unit or _infer_bare_unit(numeric)
            components.append({
                "value": numeric,
                "meters": _to_meters(numeric, resolved),
                "unit": resolved,
                "assumed_unit": unit is None,
            })
        found.append({
            "raw": raw,
            "kind": "pair",
            "components": components,
            "meters": components[0]["meters"],
            "assumed_unit": unit is None,
        })

    for match in _UNIT_DIM.finditer(text):
        raw = match.group(0).strip()
        if raw in seen or any(raw in f["raw"] for f in found):
            continue
        seen.add(raw)
        value, unit = match.group(1), match.group(2).lower()
        found.append({
            "raw": raw,
            "kind": "single",
            "meters": _to_meters(value, unit),
            "unit": unit,
            "assumed_unit": False,
        })

    # Bare numbers only when the page gave us almost nothing else — they are the weakest
    # signal and would otherwise drown the real callouts in page numbers and revision codes.
    if len(found) < 2:
        for match in _BARE_DIM.finditer(text):
            raw = match.group(1)
            if raw in seen:
                continue
            seen.add(raw)
            numeric = float(raw)
            unit = _infer_bare_unit(numeric)
            found.append({
                "raw": raw,
                "kind": "bare",
                "meters": _to_meters(numeric, unit),
                "unit": unit,
                "assumed_unit": True,
            })

    return found


def classify_item_type(text):
    """Maps drawing text to one of the estimator's item types. Returns (type, matched_phrase)."""
    lowered = (text or "").lower()
    for item_type, keywords in TYPE_KEYWORDS:
        for keyword in keywords:
            if keyword in lowered:
                return item_type, keyword
    return "wall", None


def _detect_cutouts(spans):
    """Finds openings called out on the drawing (windows, niches, TV recesses).

    Only counts a cutout when a dimension pair sits in the same text run as the keyword,
    so a legend entry reading just "WINDOW" does not subtract phantom area.
    """
    cutouts = []
    for span in spans:
        text = span.get("text", "")
        lowered = text.lower()
        keyword = next((k for k in CUTOUT_KEYWORDS if k in lowered), None)
        if not keyword:
            continue
        # "CLEAR OPENING 4000 x 3500" describes the item, not a hole through it.
        if any(phrase in lowered for phrase in ENVELOPE_PHRASES):
            continue
        dims = [d for d in extract_dimensions(text) if d["kind"] == "pair"]
        if not dims:
            continue
        components = dims[0]["components"]
        count_match = re.search(r"(?:x\s*)?(\d{1,2})\s*(?:nos|no\.?|pcs|off)\b", lowered)
        cutouts.append({
            "label": keyword.title(),
            "width_m": round(components[0]["meters"], 3),
            "height_m": round(components[1]["meters"], 3),
            "count": int(count_match.group(1)) if count_match else 1,
            "source_text": text.strip()[:120],
        })
    return cutouts


def _pick_title(spans):
    """The drawing's own name for the thing, taken as the largest non-boilerplate text."""
    candidates = []
    for span in spans:
        text = (span.get("text") or "").strip()
        if len(text) < 3 or len(text) > 80:
            continue
        if TITLE_NOISE.match(text):
            continue
        if re.fullmatch(r"[\d\s.,:x×/-]+", text):  # pure dimension strings
            continue
        size = span.get("size", 0)
        lowered = text.lower()
        score = size + (12 if any(hint in lowered for hint in TITLE_HINTS) else 0)
        candidates.append((score, size, text))

    if not candidates:
        return None
    candidates.sort(key=lambda c: (-c[0], -c[1]))
    return candidates[0][2]


def _assign_dimensions(dimensions, item_type):
    """Turns a page's dimension list into length/height/depth in metres.

    Preference order: an explicit 3-part pair (LxHxD), then a 2-part pair, then the two
    largest single callouts. Every result carries `confidence` so the UI can flag guesses.
    """
    result = {"length_m": 0.0, "height_m": 0.0, "depth_m": 0.0,
              "confidence": "none", "assumed_unit": False}

    triples = [d for d in dimensions if d["kind"] == "pair" and len(d["components"]) >= 3]
    if triples:
        components = triples[0]["components"]
        result.update({
            "length_m": round(components[0]["meters"], 3),
            "height_m": round(components[1]["meters"], 3),
            "depth_m": round(components[2]["meters"], 3),
            "confidence": "high",
            "assumed_unit": triples[0]["assumed_unit"],
            "source_text": triples[0]["raw"],
        })
        return result

    pairs = [d for d in dimensions if d["kind"] == "pair"]
    if pairs:
        # The largest pair on the sheet is the overall envelope; smaller ones are details.
        best = max(pairs, key=lambda d: d["components"][0]["meters"] * d["components"][1]["meters"])
        components = best["components"]
        result.update({
            "length_m": round(components[0]["meters"], 3),
            "height_m": round(components[1]["meters"], 3),
            "confidence": "medium",
            "assumed_unit": best["assumed_unit"],
            "source_text": best["raw"],
        })
        return result

    singles = sorted(
        [d for d in dimensions if d["kind"] in ("single", "bare")],
        key=lambda d: -d["meters"],
    )
    if len(singles) >= 2:
        result.update({
            "length_m": round(singles[0]["meters"], 3),
            "height_m": round(singles[1]["meters"], 3),
            "confidence": "low",
            "assumed_unit": any(s["assumed_unit"] for s in singles[:2]),
            "source_text": f"{singles[0]['raw']}, {singles[1]['raw']}",
        })
    elif singles:
        result.update({
            "length_m": round(singles[0]["meters"], 3),
            "confidence": "low",
            "assumed_unit": singles[0]["assumed_unit"],
            "source_text": singles[0]["raw"],
        })
    return result


# --- OCR (optional) ----------------------------------------------------------------------

_ocr_reader = None
_ocr_checked = False
_ocr_init_error = None


def ocr_status():
    """Reports which OCR backend is available, if any.

    Neither easyocr nor pytesseract is a hard dependency: easyocr pulls ~2GB of torch
    wheels, which is a heavy price for a fallback path that only applies to raster
    screenshots. Vector PDFs — the accurate input — never touch OCR.
    """
    try:
        import easyocr  # noqa: F401
        return {"available": True, "backend": "easyocr"}
    except ImportError:
        pass
    try:
        import pytesseract
        from shutil import which
        if which("tesseract") or getattr(pytesseract.pytesseract, "tesseract_cmd", None):
            return {"available": True, "backend": "pytesseract"}
    except ImportError:
        pass
    return {
        "available": False,
        "backend": None,
        "hint": (
            "No OCR backend installed. Vector PDFs still parse exactly. For dimension "
            "detection on PNG/JPG drawings install one of: "
            "`pip install easyocr` (large, GPU-capable) or "
            "`pip install pytesseract` plus the Tesseract binary."
        ),
    }


def _run_ocr(pil_image):
    """OCR at native resolution — deliberately no downsampling, since dimension text on a
    drawing is small and the first thing lost when an image is scaled down."""
    global _ocr_reader, _ocr_checked, _ocr_init_error
    status = ocr_status()
    if not status["available"]:
        return "", status

    try:
        if status["backend"] == "easyocr":
            import easyocr
            import numpy as np
            if _ocr_reader is None and not _ocr_checked:
                _ocr_checked = True
                try:
                    _ocr_reader = easyocr.Reader(["en"], gpu=False, verbose=False)
                except Exception as exc:
                    # Recorded rather than raised: a bad init (e.g. a corrupt model cache)
                    # would otherwise silently downgrade every remaining page in this batch
                    # to "No text layer" with no clue why, since _ocr_checked=True stops a
                    # retry on every subsequent page.
                    _ocr_init_error = str(exc)
            if _ocr_reader is None:
                return "", {
                    "available": False, "backend": "easyocr",
                    "hint": f"OCR backend failed to start: {_ocr_init_error}",
                }
            results = _ocr_reader.readtext(np.array(pil_image.convert("RGB")), detail=0)
            return "\n".join(results), status

        import pytesseract
        return pytesseract.image_to_string(pil_image), status
    except Exception as exc:
        return "", {"available": False, "backend": status.get("backend"),
                    "hint": f"OCR backend failed: {exc}"}


# --- Page builders -------------------------------------------------------------------------

def _reject_envelope_cutouts(cutouts, assigned, warnings):
    """Drops "cutouts" that are really the item's own envelope restated.

    Backstop for the phrase check in `_detect_cutouts`: a drawing that writes plain
    "OPENING 4000 x 3500" gives no lexical hint, so the dimensions themselves are compared
    against the assigned envelope. Without this an arch nets out to ~0 m2 and prices at
    nothing, which is the single most expensive way this module could be wrong.
    """
    length_m = assigned.get("length_m") or 0.0
    height_m = assigned.get("height_m") or 0.0
    envelope_area = length_m * height_m
    kept = []

    for cutout in cutouts:
        width = cutout.get("width_m") or 0.0
        height = cutout.get("height_m") or 0.0

        if envelope_area > 0:
            matches_envelope = (
                abs(width - length_m) <= length_m * _ENVELOPE_MATCH_TOLERANCE
                and abs(height - height_m) <= height_m * _ENVELOPE_MATCH_TOLERANCE
            )
            area_ratio = (width * height * max(1, cutout.get("count", 1))) / envelope_area
            if matches_envelope or area_ratio > _MAX_CUTOUT_AREA_RATIO:
                warnings.append(
                    f"Ignored '{cutout.get('label')}' {width:g}x{height:g} m as a cutout — "
                    f"it matches the overall size, so it was read as the item envelope."
                )
                continue
        kept.append(cutout)

    return kept


def _build_page(source_file, page_number, page_count, thumbnail, spans, raw_text,
                width_px, height_px, text_source, warnings=None):
    """Assembles one parsed drawing page into the shape the UI and calculators consume."""
    warnings = list(warnings or [])
    title = _pick_title(spans)
    item_type, matched = classify_item_type(f"{title or ''} {raw_text}")
    dimensions = extract_dimensions(raw_text)
    assigned = _assign_dimensions(dimensions, item_type)
    cutouts = _reject_envelope_cutouts(_detect_cutouts(spans), assigned, warnings)

    label = title or f"{Path(source_file).stem} - page {page_number}"

    return {
        "id": f"{Path(source_file).name}::p{page_number}",
        "source_file": str(source_file),
        "file_name": Path(source_file).name,
        "page_number": page_number,
        "page_count": page_count,
        "thumbnail": thumbnail,
        "width_px": width_px,
        "height_px": height_px,
        "text_source": text_source,          # "vector" | "ocr" | "none"
        "raw_text": raw_text[:4000],
        "detected": {
            "label": label,
            "item_type": item_type,
            "matched_keyword": matched,
            "length_m": assigned["length_m"],
            "height_m": assigned["height_m"],
            "depth_m": assigned["depth_m"],
            "faces": 1,
            "quantity": 1,
            "cutouts": cutouts,
            "confidence": assigned["confidence"],
            "assumed_unit": assigned.get("assumed_unit", False),
            "source_text": assigned.get("source_text", ""),
        },
        "dimensions_found": dimensions[:40],
        "warnings": warnings or [],
    }


def _parse_pdf(path, warnings):
    """One entry per page of a (possibly 25-page) drawing deck."""
    pages = []
    document = fitz.open(str(path))
    try:
        total = document.page_count
        limit = min(total, MAX_PAGES_PER_FILE)
        if total > limit:
            warnings.append(
                f"{Path(path).name}: {total} pages found, first {limit} parsed "
                f"(MAX_PAGES_PER_FILE)."
            )

        for index in range(limit):
            page = document.load_page(index)

            # Spans carry font size, which is what distinguishes a sheet title from a note.
            spans = []
            try:
                layout = page.get_text("dict")
                for block in layout.get("blocks", []):
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text = (span.get("text") or "").strip()
                            if text:
                                spans.append({"text": text, "size": span.get("size", 0)})
            except Exception as exc:
                warnings.append(f"{Path(path).name} p{index + 1}: text layout unreadable ({exc}).")

            raw_text = page.get_text("text") or ""
            text_source = "vector"

            matrix = fitz.Matrix(PDF_RENDER_SCALE, PDF_RENDER_SCALE)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            # Pixel data comes straight off the pixmap's own buffer rather than round-tripping
            # through a PNG encode+decode — ~13x faster on a full-resolution drawing sheet and
            # this image is only ever downsampled into a thumbnail, never sent anywhere at
            # full size.
            image = PILImage.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            width_px, height_px = image.size
            preview = image.copy()
            preview.thumbnail(PREVIEW_MAX_PX, PILImage.LANCZOS)
            thumbnail = image_tools.pil_to_base64(preview)

            # A page with no vector text is a scanned/exported raster inside a PDF wrapper.
            page_warnings = []
            if len(raw_text.strip()) < 4:
                ocr_text, status = _run_ocr(image)
                if ocr_text.strip():
                    raw_text = ocr_text
                    text_source = "ocr"
                else:
                    text_source = "none"
                    page_warnings.append(
                        status.get("hint")
                        or "No text layer on this page and OCR returned nothing — "
                           "enter dimensions manually."
                    )

            pages.append(_build_page(
                path, index + 1, total, thumbnail, spans, raw_text,
                width_px, height_px, text_source, page_warnings,
            ))
    finally:
        document.close()
    return pages


def _parse_raster(path, warnings):
    """A single-page entry for a PNG/JPG drawing, OCR'd when a backend is available."""
    with PILImage.open(str(path)) as image:
        image.load()
        native = image.convert("RGB") if image.mode in ("P", "CMYK", "RGBA") else image.copy()

    width_px, height_px = native.size
    preview = native.copy()
    preview.thumbnail(PREVIEW_MAX_PX, PILImage.LANCZOS)
    thumbnail = image_tools.pil_to_base64(preview)

    raw_text, status = _run_ocr(native)
    page_warnings = []
    if raw_text.strip():
        text_source = "ocr"
    else:
        text_source = "none"
        page_warnings.append(
            status.get("hint") or "OCR found no text — enter dimensions manually."
        )

    spans = [{"text": line.strip(), "size": 12}
             for line in raw_text.splitlines() if line.strip()]

    return [_build_page(
        path, 1, 1, thumbnail, spans, raw_text,
        width_px, height_px, text_source, page_warnings,
    )]


def parse_files(paths):
    """Parses every uploaded drawing into a flat list of pages.

    Returns {"success", "drawings", "warnings", "ocr", "skipped"}. One unreadable file
    never aborts the batch — it is reported and the rest still parse.
    """
    drawings, warnings, skipped = [], [], []

    for raw_path in paths or []:
        path = Path(raw_path)
        if not path.exists():
            skipped.append({"file": str(path), "reason": "File not found."})
            continue

        suffix = path.suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            skipped.append({
                "file": path.name,
                "reason": f"Unsupported type '{suffix}'. Accepts: "
                          f"{', '.join(sorted(SUPPORTED_EXTENSIONS))}",
            })
            continue

        try:
            if suffix in SUPPORTED_PDF:
                drawings.extend(_parse_pdf(path, warnings))
            else:
                drawings.extend(_parse_raster(path, warnings))
        except Exception as exc:
            skipped.append({"file": path.name, "reason": str(exc)})

    return {
        "success": True,
        "drawings": drawings,
        "page_count": len(drawings),
        "warnings": warnings,
        "skipped": skipped,
        "ocr": ocr_status(),
    }


if __name__ == "__main__":
    import json
    import sys

    targets = sys.argv[1:]
    if not targets:
        print("usage: python design_parser.py <drawing.pdf|drawing.png> [...]")
        raise SystemExit(1)

    result = parse_files(targets)
    print(f"Parsed {result['page_count']} page(s). OCR: {result['ocr']}")
    for skip in result["skipped"]:
        print(f"  SKIPPED {skip['file']}: {skip['reason']}")
    for warning in result["warnings"]:
        print(f"  WARN {warning}")
    for page in result["drawings"]:
        detected = page["detected"]
        print(f"\n  {page['file_name']} p{page['page_number']}/{page['page_count']} "
              f"[{page['text_source']}]")
        print(f"    label:   {detected['label']}")
        print(f"    type:    {detected['item_type']} (matched: {detected['matched_keyword']})")
        print(f"    L x H x D: {detected['length_m']} x {detected['height_m']} x "
              f"{detected['depth_m']} m  confidence={detected['confidence']} "
              f"assumed_unit={detected['assumed_unit']}")
        if detected["cutouts"]:
            print(f"    cutouts: {json.dumps(detected['cutouts'])}")
