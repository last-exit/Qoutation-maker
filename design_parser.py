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
import page_geometry
import shape_detect

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


# A usable name has at least three letters in a row. OCR on a raster drawing throws up
# runs like "—=s\" and "50.0cm" that pass every other filter — not pure dimensions, not
# boilerplate — yet are meaningless as an item name. Requiring a real word rejects them and
# lets the sheet title stand in instead.
_MEANINGFUL_LABEL = re.compile(r"[A-Za-z]{3,}")


def _is_meaningful_label(text):
    return bool(_MEANINGFUL_LABEL.search(text or ""))


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
        if not _is_meaningful_label(text):
            continue
        size = span.get("size", 0)
        lowered = text.lower()
        score = size + (12 if any(hint in lowered for hint in TITLE_HINTS) else 0)
        candidates.append((score, size, text))

    if not candidates:
        return None
    candidates.sort(key=lambda c: (-c[0], -c[1]))
    return candidates[0][2]


# A dimension written against its own name — "DEPTH 600 mm", "HEIGHT: 2400" — rather than
# as part of an LxH callout. Draughtsmen write the depth of a counter or the height of an
# arch this way constantly, and reading only the paired callouts threw those away: the value
# was sitting in the OCR text, correctly recognised, and still came back as 0.
_LABELLED_DIM = re.compile(
    r"\b(depth|deep|height|high|ht|length|long|width|wide)\b"
    r"\s*[:=]?\s*"
    r"(\d+(?:[.,]\d+)?)\s*(mm|cm|m)?\b",
    re.IGNORECASE,
)

# Which spec field each label feeds. "Width" maps to length because in this model the long
# horizontal run is length_m for every item type — a counter's width is its run, and its
# front-to-back measurement is the one called depth.
#
# THK/THICKNESS are deliberately absent. On a shop drawing they name the board — "THK 18"
# is 18 mm MDF — not how deep the counter is. Reading that as depth would set a 4 m counter
# 18 mm deep and quote a worktop of almost no area, which is precisely the confident-looking
# wrong number this parser is supposed to stop producing.
_LABEL_FIELDS = {
    "depth": "depth_m", "deep": "depth_m",
    "height": "height_m", "high": "height_m", "ht": "height_m",
    "length": "length_m", "long": "length_m", "width": "length_m", "wide": "length_m",
}


def extract_labelled_dimensions(text):
    """Named dimensions found in the drawing text, as {field: metres}.

    Later mentions lose to earlier ones: the first time a sheet names a dimension is
    normally the primary callout, and repeats tend to be detail or section notes.
    """
    found = {}
    for match in _LABELLED_DIM.finditer(text or ""):
        field = _LABEL_FIELDS[match.group(1).lower()]
        if field in found:
            continue
        value = float(match.group(2).replace(",", "."))
        unit = (match.group(3) or "").lower() or _infer_bare_unit(value)
        found[field] = round(_to_meters(value, unit), 3)
    return found


def _apply_labelled_dimensions(text, assigned):
    """Fills gaps in `assigned` from named callouts, without overriding what was measured.

    Only fields the pair/triple pass left at zero are touched. A drawing that states both
    "5000 x 2400" and "HEIGHT 2400" should keep the paired reading, which is the stronger
    signal; this exists for the dimension that appears *only* as a label.
    """
    labelled = extract_labelled_dimensions(text)
    filled = []
    for field, meters in labelled.items():
        if meters > 0 and float(assigned.get(field) or 0.0) <= 0:
            assigned[field] = meters
            filled.append(field)

    if filled:
        source = assigned.get("source_text") or ""
        names = ", ".join(f.replace("_m", "") for f in filled)
        assigned["source_text"] = f"{source} + labelled {names}".strip(" +")
        if assigned.get("confidence") in (None, "none"):
            assigned["confidence"] = "low"
    return filled


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


# A drawing's dimension text is the smallest type on the sheet and often the palest. One
# OCR pass at native resolution reads the sheet title confidently and drops most of the
# callouts, which is exactly the failure this deck showed: seven callouts on the page, one
# recovered. These passes are unioned, not raced — each finds tokens the other misses.
#
# `upscale` is the important one. Recognisers are trained on text tens of pixels tall; a
# 12 px callout on a 3D render is below that floor, and enlarging it before recognition
# costs a second and roughly triples recall on this kind of page.
_OCR_PASSES = (
    {"name": "native", "upscale": 1.0, "contrast": False},
    {"name": "upscaled", "upscale": 3.0, "contrast": True},
)

# Upscaling is capped so a large sheet cannot blow memory: 3x of an already-large render is
# no better than 3x of a downscaled one for text this size.
_OCR_MAX_SIDE_PX = 4200


# Text that reads as a measurement, used to decide whether a second OCR pass is worth its
# time. Deliberately loose — this only gates an optimisation, so a near-miss like "120cm"
# with a stray character still counts as a callout worth having.
_LOOKS_LIKE_DIMENSION = re.compile(r"\d\s*(?:mm|cm|m)\b|\d{3,}", re.IGNORECASE)


def _dimension_like(tokens):
    """How many collected tokens look like a dimension callout."""
    return sum(1 for t in tokens if _LOOKS_LIKE_DIMENSION.search(t.get("text") or ""))


def _prepare_for_ocr(pil_image, upscale, contrast):
    """Scaled and contrast-normalised copy of a page for one OCR pass."""
    image = pil_image
    if contrast:
        # Dimension lines and their text are near-black; the shaded render behind them is
        # mid-grey. A hard stretch pushes those apart instead of letting the recogniser
        # decide, which is what loses pale callouts over a grey solid.
        from PIL import ImageOps
        image = ImageOps.autocontrast(image.convert("L"), cutoff=2)

    if upscale and upscale != 1.0:
        width, height = image.size
        target = (int(width * upscale), int(height * upscale))
        if max(target) > _OCR_MAX_SIDE_PX:
            factor = _OCR_MAX_SIDE_PX / float(max(target))
            target = (max(1, int(target[0] * factor)), max(1, int(target[1] * factor)))
        if target[0] > width:
            image = image.resize(target, PILImage.LANCZOS)

    return image


def _ocr_tokens(pil_image):
    """Text tokens with their pixel boxes, unioned over several passes.

    Returns (tokens, status). Each token is {text, bbox, confidence, pass}, with `bbox` in
    the coordinate space of the image handed in — every downstream stage needs that box to
    tie a callout to the object it measures, and the previous `detail=0` call threw it away.
    """
    global _ocr_reader, _ocr_checked, _ocr_init_error
    status = ocr_status()
    if not status["available"]:
        return [], status

    collected = []
    try:
        if status["backend"] == "easyocr":
            import easyocr  # noqa: F401
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
                return [], {
                    "available": False, "backend": "easyocr",
                    "hint": f"OCR backend failed to start: {_ocr_init_error}",
                }

            # The passes are adaptive, not unconditional. Reading a full-resolution drawing
            # page costs ~15 s; the upscaled second pass costs ~35 s more. Running both on
            # every page of a 25-page deck is 20 minutes of a spinner, which is what made
            # the app look frozen. The second pass only earns its cost when the first came
            # up short, so it runs then and not otherwise.
            #
            # Downscaling is deliberately never used to save time: at 2000 px this page's
            # "435.0 cm" reads as "4360cin". Full resolution or nothing.
            for spec in _OCR_PASSES:
                if spec["upscale"] != 1.0 and _dimension_like(collected) >= 2:
                    break        # the plain pass already found the callouts
                prepared = _prepare_for_ocr(pil_image, spec["upscale"], spec["contrast"])
                ratio = pil_image.size[0] / float(prepared.size[0] or 1)
                try:
                    results = _ocr_reader.readtext(
                        np.array(prepared.convert("RGB")), detail=1)
                except Exception:
                    continue
                for box, text, confidence in results:
                    xs = [point[0] for point in box]
                    ys = [point[1] for point in box]
                    collected.append({
                        "text": (text or "").strip(),
                        "bbox": (min(xs) * ratio, min(ys) * ratio,
                                 max(xs) * ratio, max(ys) * ratio),
                        "confidence": float(confidence or 0.0),
                        "pass": spec["name"],
                    })

        else:
            import pytesseract
            from pytesseract import Output
            for spec in _OCR_PASSES:
                prepared = _prepare_for_ocr(pil_image, spec["upscale"], spec["contrast"])
                ratio = pil_image.size[0] / float(prepared.size[0] or 1)
                try:
                    data = pytesseract.image_to_data(prepared, output_type=Output.DICT)
                except Exception:
                    continue
                for index, text in enumerate(data.get("text", [])):
                    text = (text or "").strip()
                    if not text:
                        continue
                    try:
                        confidence = float(data["conf"][index])
                    except (KeyError, ValueError, TypeError):
                        confidence = -1.0
                    left, top = data["left"][index], data["top"][index]
                    width, height = data["width"][index], data["height"][index]
                    collected.append({
                        "text": text,
                        "bbox": (left * ratio, top * ratio,
                                 (left + width) * ratio, (top + height) * ratio),
                        "confidence": confidence / 100.0 if confidence >= 0 else 0.0,
                        "pass": spec["name"],
                    })

    except Exception as exc:
        return [], {"available": False, "backend": status.get("backend"),
                    "hint": f"OCR backend failed: {exc}"}

    return _dedupe_tokens(collected), status


def _dedupe_tokens(tokens):
    """Merges the same physical token found by more than one pass.

    Two reads are the same token when their boxes substantially overlap. The higher
    confidence wins, so the upscaled pass — which is usually right about small text —
    replaces a native-resolution misread of the same callout rather than duplicating it.
    """
    kept = []
    for token in sorted(tokens, key=lambda t: -t.get("confidence", 0.0)):
        if not token["text"]:
            continue
        duplicate = False
        for existing in kept:
            if _box_overlap_ratio(token["bbox"], existing["bbox"]) > 0.5:
                duplicate = True
                break
        if not duplicate:
            kept.append(token)

    # Reading order keeps the assembled text sensible for the title and keyword passes.
    kept.sort(key=lambda t: (round(t["bbox"][1], -1), t["bbox"][0]))
    return kept


def _box_overlap_ratio(a, b):
    """Intersection over the smaller of two boxes."""
    overlap_w = min(a[2], b[2]) - max(a[0], b[0])
    overlap_h = min(a[3], b[3]) - max(a[1], b[1])
    if overlap_w <= 0 or overlap_h <= 0:
        return 0.0
    smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return (overlap_w * overlap_h) / smaller if smaller > 0 else 0.0


def _run_ocr(pil_image):
    """Plain text for the title/keyword passes. Kept for callers that want only text."""
    tokens, status = _ocr_tokens(pil_image)
    return "\n".join(t["text"] for t in tokens), status


# Why a page produced no dimensions. The old code collapsed every cause into one string —
# "drawing gave no usable value" — which blames the drawing even when the real reason is
# that no text reader is installed on the machine. A PM reading that has no idea the fix is
# a pip install, so they retype every number on a 25-page deck instead. Each cause now
# carries its own wording and, where there is one, the command that fixes it.
READ_STATE_NO_READER = "no_reader"        # nothing installed to read a raster page
READ_STATE_READER_FAILED = "reader_failed"  # installed, but it errored (e.g. model download)
READ_STATE_NOTHING_FOUND = "nothing_found"  # it ran and genuinely found no text
READ_STATE_OK = "ok"


def _read_state(status):
    """Classifies why OCR yielded nothing, from the status `_ocr_tokens` returned."""
    if status.get("available"):
        return READ_STATE_NOTHING_FOUND
    hint = status.get("hint") or ""
    # A backend that is present but failed to start reports itself through `hint` while
    # still being unavailable — that is a broken install, not a missing one, and the fix
    # is different.
    if status.get("backend") or "failed" in hint.lower():
        return READ_STATE_READER_FAILED
    return READ_STATE_NO_READER


def read_state_message(state, hint=""):
    """What to tell the PM on a page that produced no dimensions."""
    if state == READ_STATE_NO_READER:
        return ("No text reader is installed, so nothing could be read from this drawing. "
                "Install one with `pip install easyocr`, or type the dimensions below.")
    if state == READ_STATE_READER_FAILED:
        return (f"The text reader could not start ({hint or 'unknown error'}). "
                f"It needs to download its model once, which requires internet. "
                f"Type the dimensions below in the meantime.")
    return "Nothing readable was found on this sheet — type the dimensions below."


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


# --- Element decomposition ----------------------------------------------------------------
# A drawing sheet is rarely one item. A zone render carries a counter, a tower, a portal and
# the walls behind them, each with its own callouts. The single-item model that used to live
# here could only ever return one of those, and picked it by taking the two largest numbers
# anywhere on the page — so a sheet with eight elements produced one row built from two
# dimensions that usually belonged to two different objects.
#
# These functions turn attached dimensions (see page_geometry.measure) into one element per
# cluster. They are deliberately conservative: an element is only produced where the drawing
# actually dimensioned something. Shapes nobody measured are counted and reported, never
# invented, because a fabricated element costs more than a missing one.

def _dimension_tokens(tokens):
    """The subset of text tokens that read as a dimension, with metres attached."""
    found = []
    for token in tokens or []:
        text = (token.get("text") or "").strip()
        if not text:
            continue
        dims = extract_dimensions(text)
        if not dims:
            continue
        # A token is one callout: take its first reading rather than treating a token like
        # "1200 x 600" as two separate measured spans.
        best = dims[0]
        meters = float(best.get("meters") or 0.0)
        if meters <= 0:
            continue
        found.append({
            "text": text,
            "bbox": token.get("bbox"),
            "meters": meters,
            "assumed_unit": bool(best.get("assumed_unit")),
            "confidence": token.get("confidence", 0.0),
        })
    return found


def _label_for_cluster(cluster_box, tokens):
    """The nearest piece of non-dimension text — the drawing's own name for the object."""
    cx = (cluster_box[0] + cluster_box[2]) / 2.0
    cy = (cluster_box[1] + cluster_box[3]) / 2.0

    best, best_distance = None, None
    for token in tokens or []:
        text = (token.get("text") or "").strip()
        bbox = token.get("bbox")
        if not text or not bbox or len(text) < 3:
            continue
        if re.fullmatch(r"[\d\s.,:x×/-]+(?:\s*(mm|cm|m))?", text, re.IGNORECASE):
            continue
        if TITLE_NOISE.match(text):
            continue
        if not _is_meaningful_label(text):
            continue
        tx = (bbox[0] + bbox[2]) / 2.0
        ty = (bbox[1] + bbox[3]) / 2.0
        distance = ((tx - cx) ** 2 + (ty - cy) ** 2) ** 0.5
        if best_distance is None or distance < best_distance:
            best, best_distance = text, distance
    return best


def _shape_for_cluster(cluster_box, arcs, px_per_m):
    """Whether the object in this box is drawn as a curve, and how deep the curve is.

    The arc comes from the PDF's own vector path, so the rise is measured rather than
    estimated — and dividing it by the cluster's local pixels-per-metre turns it straight
    into the sagitta the pricing model asks for. This is the one place the estimator can
    know a wall is curved without a human saying so.
    """
    if not arcs or px_per_m <= 0:
        return "flat", {}

    best = None
    for arc in arcs:
        box = arc.get("bbox")
        if not box:
            continue
        if (box[2] < cluster_box[0] or box[0] > cluster_box[2]
                or box[3] < cluster_box[1] or box[1] > cluster_box[3]):
            continue
        if best is None or arc["chord_px"] > best["chord_px"]:
            best = arc

    if best is None or best["chord_px"] <= 0:
        return "flat", {}

    sagitta_m = best["sagitta_px"] / px_per_m
    chord_m = best["chord_px"] / px_per_m
    if chord_m <= 0 or sagitta_m <= 0:
        return "flat", {}

    # A barely-bowed line is a straight edge with drawing tolerance on it, not a curve.
    if sagitta_m / chord_m < 0.02:
        return "flat", {}

    return "curved", {"sagitta_m": round(sagitta_m, 3)}


def _elements_from_clusters(clusters, tokens, arcs, raw_text, page_kind, warnings):
    """One element per cluster of attached dimensions."""
    elements = []

    for index, group in enumerate(clusters):
        spans = group["spans"]
        box = group["bbox"]

        horizontals = [s["value_m"] for s in spans if s["axis"] == "h"]
        verticals = [s["value_m"] for s in spans if s["axis"] == "v"]
        if not horizontals and not verticals:
            continue

        # The largest run on each axis is the object's overall size; smaller callouts in
        # the same cluster are its internal divisions (shelf pitches, a plinth height).
        length_m = round(max(horizontals), 3) if horizontals else 0.0
        height_m = round(max(verticals), 3) if verticals else 0.0

        scales = [s["px_per_m"] for s in spans if s.get("px_per_m", 0) > 0]
        px_per_m = sorted(scales)[len(scales) // 2] if scales else 0.0

        label = _label_for_cluster(box, tokens)

        # Classify from this element's *own* label. On a page holding a tower and a portal,
        # matching against the whole sheet's text gives every element the same type —
        # whichever keyword appears first — so a display tower sitting beside an "Entrance
        # Arch" label silently becomes an arch itself.
        #
        # The sheet-wide text is only a safe fallback when the page turned out to hold one
        # element, because then there is nothing else on it for a keyword to belong to.
        item_type, matched = classify_item_type(label or "")
        if matched is None and len(clusters) == 1:
            item_type, matched = classify_item_type(raw_text)

        shape, geometry = _shape_for_cluster(box, arcs, px_per_m)

        # Both axes measured is a genuinely well-described object. One axis means the PM
        # still has a field to fill, and the UI must say which.
        if horizontals and verticals:
            confidence = "medium"
        else:
            confidence = "low"

        element = {
            "id": f"e{index + 1}",
            "label": label or f"Element {index + 1}",
            "item_type": item_type,
            "matched_keyword": matched,
            "shape": shape,
            "length_m": length_m,
            "height_m": height_m,
            "depth_m": 0.0,
            "faces": 1,
            "quantity": 1,
            "cutouts": [],
            "bbox_px": [round(v, 1) for v in box],
            "confidence": confidence,
            "assumed_unit": any(s.get("assumed_unit") for s in spans),
            "source_text": ", ".join(s["token"] for s in spans[:4]),
            "px_per_m": round(px_per_m, 2),
            "provenance": [
                {"value_m": s["value_m"], "axis": s["axis"], "token": s["token"],
                 "page_kind": page_kind}
                for s in spans
            ],
        }
        element.update(geometry)
        elements.append(element)

    # Biggest first: the PM reads the stand's main structure before its details.
    elements.sort(key=lambda e: -(e["length_m"] * max(e["height_m"], 0.01)))
    for position, element in enumerate(elements, start=1):
        element["id"] = f"e{position}"
    return elements


def _legacy_element(spans, raw_text, warnings):
    """The original whole-page reading, used when no dimension could be attached.

    This is the safety net, and it matters: a page whose callouts sit on oblique leaders,
    or which has no detectable linework at all, still parses exactly as it did before this
    feature existed. Decomposition adds elements — it never removes the fallback.
    """
    title = _pick_title(spans)
    item_type, matched = classify_item_type(f"{title or ''} {raw_text}")
    dimensions = extract_dimensions(raw_text)
    assigned = _assign_dimensions(dimensions, item_type)
    _apply_labelled_dimensions(raw_text, assigned)
    cutouts = _reject_envelope_cutouts(_detect_cutouts(spans), assigned, warnings)

    return {
        "id": "e1",
        "label": title or "",
        "item_type": item_type,
        "matched_keyword": matched,
        "shape": "flat",
        "length_m": assigned["length_m"],
        "height_m": assigned["height_m"],
        "depth_m": assigned["depth_m"],
        "faces": 1,
        "quantity": 1,
        "cutouts": cutouts,
        "bbox_px": None,
        "confidence": assigned["confidence"],
        "assumed_unit": assigned.get("assumed_unit", False),
        "source_text": assigned.get("source_text", ""),
        "px_per_m": 0.0,
        "provenance": [],
    }, dimensions


def _build_page(source_file, page_number, page_count, thumbnail, spans, raw_text,
                width_px, height_px, text_source, warnings=None,
                tokens=None, segments=None, arcs=None,
                read_state=READ_STATE_OK, page_image=None):
    """Assembles one parsed drawing page into the shape the UI and calculators consume."""
    warnings = list(warnings or [])

    page_kind, page_detail = page_geometry.classify_page(
        segments or [], page_size=(width_px, height_px))

    elements = []
    unattached_count = 0
    if tokens and segments:
        dimension_tokens = _dimension_tokens(tokens)
        measured, unattached = page_geometry.measure(
            dimension_tokens, segments, (width_px, height_px))
        unattached_count = len(unattached)
        if measured:
            clusters = page_geometry.cluster(measured)
            elements = _elements_from_clusters(
                clusters, tokens, arcs, raw_text, page_kind, warnings)

    # The legacy reading is always computed — its dimension list feeds the UI either way —
    # but its warnings only belong to the page when it is the reading actually used. On a
    # decomposed page its envelope is meaningless, and complaints measured against it would
    # be noise at best and wrong at worst.
    legacy_warnings = []
    legacy, dimensions = _legacy_element(spans, raw_text, legacy_warnings)
    if not elements:
        warnings.extend(legacy_warnings)
    if not elements:
        # Nothing could be attached to the drawing's own geometry, so fall back to the
        # whole-page reading rather than returning an empty sheet.
        elements = [legacy]
        if unattached_count:
            warnings.append(
                f"{unattached_count} dimension(s) found but none could be tied to a "
                f"line on the drawing — read as a single item. Check the values."
            )
    else:
        if unattached_count:
            warnings.append(
                f"{unattached_count} dimension(s) could not be tied to an object and are "
                f"not included in any item below."
            )
        # Cutouts are detected against the sheet as a whole, so a decomposed page has no
        # way to know which element a TV recess belongs to. Dropping them would quietly
        # remove real deductions from the quote, so they are carried on the largest
        # element — which is where a screen or niche usually is — and the PM is told, by
        # name, that the assignment is a guess they should check.
        #
        # They are re-validated against that element's envelope rather than the legacy
        # whole-page one. The difference matters: a sheet whose only dimension pair is the
        # opening's own "600 x 400" gives the legacy reading an envelope of exactly that,
        # so the envelope guard would throw the opening away as a restatement of a size
        # that was never the item's to begin with.
        raw_cutouts = _detect_cutouts(spans)
        if raw_cutouts:
            kept = _reject_envelope_cutouts(raw_cutouts, elements[0], warnings)
            if kept:
                elements[0]["cutouts"] = kept
                names = ", ".join(c.get("label", "opening") for c in kept)
                warnings.append(
                    f"Opening(s) found on this sheet ({names}) but not tied to one item — "
                    f"put on '{elements[0]['label']}'. Move them if they belong elsewhere."
                )

    # `label` on an element is the drawing's own word for it where there was one; falling
    # back to the sheet name keeps every row identifiable in the quotation.
    sheet_name = _pick_title(spans) or f"{Path(source_file).stem} - page {page_number}"
    for element in elements:
        if not element.get("label"):
            element["label"] = sheet_name

    # Shape comes from the drawing's pixels where OpenCV is available. Done after the
    # elements exist because it needs each one's box and local scale; a curve found without
    # a scale gets its shape but not its rise, so the item still asks for the number that
    # decides its cost rather than inventing one.
    shapes_found = shape_detect.apply_to_elements(page_image, elements)
    if shapes_found:
        warnings.append(
            f"{shapes_found} item(s) look curved or circular on this drawing and have been "
            f"set that way. Change the Shape on any that are wrong.")

    cutouts = elements[0].get("cutouts") or []
    label = elements[0].get("label") or sheet_name

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
        "page_kind": page_kind,              # "flat" | "perspective"
        "page_kind_detail": page_detail,
        # Why this page produced no dimensions, so the UI can say "no reader installed"
        # rather than blaming the drawing. See `read_state_message`.
        "read_state": read_state,
        "read_message": ("" if read_state == READ_STATE_OK
                         else read_state_message(read_state)),
        "elements": elements,
        # `detected` is the first element, kept so any consumer written against the
        # one-item-per-page shape keeps working while the UI moves over to `elements`.
        "detected": {
            "label": label,
            "item_type": elements[0]["item_type"],
            "matched_keyword": elements[0].get("matched_keyword"),
            "length_m": elements[0]["length_m"],
            "height_m": elements[0]["height_m"],
            "depth_m": elements[0]["depth_m"],
            "faces": 1,
            "quantity": 1,
            "cutouts": cutouts,
            "confidence": elements[0]["confidence"],
            "assumed_unit": elements[0].get("assumed_unit", False),
            "source_text": elements[0].get("source_text", ""),
        },
        "dimensions_found": dimensions[:40],
        "warnings": warnings or [],
    }


def _parse_pdf(path, warnings, page_start=0, page_count=None):
    """One entry per page of a (possibly 25-page) drawing deck.

    `page_start` / `page_count` parse a slice rather than the whole file. OCR costs 15-20
    seconds a page, so a deck parsed in one call leaves the UI with nothing to show for
    minutes; parsing a few pages at a time lets each one appear as it is read, and lets the
    PM start correcting page 1 while page 12 is still being processed.
    """
    pages = []
    document = fitz.open(str(path))
    try:
        total = document.page_count
        limit = min(total, MAX_PAGES_PER_FILE)
        if total > limit and page_start == 0:
            warnings.append(
                f"{Path(path).name}: {total} pages found, first {limit} parsed "
                f"(MAX_PAGES_PER_FILE)."
            )

        stop = limit if page_count is None else min(limit, page_start + int(page_count))
        for index in range(max(0, int(page_start)), stop):
            page = document.load_page(index)

            # Spans carry font size, which is what distinguishes a sheet title from a note.
            # Their bounding boxes are what tie a callout to the object it measures, so they
            # are scaled into the same pixel space as the render and kept as tokens.
            spans = []
            tokens = []
            try:
                layout = page.get_text("dict")
                for block in layout.get("blocks", []):
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text = (span.get("text") or "").strip()
                            if not text:
                                continue
                            spans.append({"text": text, "size": span.get("size", 0)})
                            box = span.get("bbox")
                            if box:
                                tokens.append({
                                    "text": text,
                                    "bbox": tuple(v * PDF_RENDER_SCALE for v in box),
                                    "confidence": 1.0,     # vector text is not a guess
                                    "pass": "vector",
                                })
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
            read_state = READ_STATE_OK
            if len(raw_text.strip()) < 4:
                ocr_tokens, status = _ocr_tokens(image)
                if ocr_tokens:
                    tokens = ocr_tokens
                    raw_text = "\n".join(t["text"] for t in ocr_tokens)
                    spans = [{"text": t["text"], "size": 12} for t in ocr_tokens]
                    text_source = "ocr"
                else:
                    text_source = "none"
                    read_state = _read_state(status)
                    page_warnings.append(
                        read_state_message(read_state, status.get("hint", "")))

            # Vector linework survives even when a page's text has been outlined, which is
            # the common SketchUp export and the case that reads as "OCR". Its endpoints are
            # exact, so it is always preferred; the raster scan is only for a page that
            # genuinely carries no vector paths at all.
            segments = page_geometry.segments_from_pdf_page(page, scale=PDF_RENDER_SCALE)
            arcs = page_geometry.curves_from_pdf_page(page, scale=PDF_RENDER_SCALE)
            if not segments:
                # Only when the page carries no vector paths at all. Any real linework is
                # exact and beats a pixel scan outright — a simple elevation may hold just
                # a handful of lines, and preferring the scan over them turns measured
                # endpoints back into thresholded guesses.
                segments = page_geometry.segments_from_image(image)

            pages.append(_build_page(
                path, index + 1, total, thumbnail, spans, raw_text,
                width_px, height_px, text_source, page_warnings,
                tokens=tokens, segments=segments, arcs=arcs,
                read_state=read_state, page_image=image,
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

    tokens, status = _ocr_tokens(native)
    raw_text = "\n".join(t["text"] for t in tokens)
    page_warnings = []
    read_state = READ_STATE_OK
    if raw_text.strip():
        text_source = "ocr"
    else:
        text_source = "none"
        read_state = _read_state(status)
        page_warnings.append(read_state_message(read_state, status.get("hint", "")))

    spans = [{"text": t["text"], "size": 12} for t in tokens]
    segments = page_geometry.segments_from_image(native)

    return [_build_page(
        path, 1, 1, thumbnail, spans, raw_text,
        width_px, height_px, text_source, page_warnings,
        tokens=tokens, segments=segments, arcs=None,
        read_state=read_state, page_image=native,
    )]


# --- Cross-page reconciliation -------------------------------------------------------------

def _signature(element):
    """A shape fingerprint used to recognise the same object drawn on another sheet.

    Rounded to 5 cm because the same tower dimensioned on an elevation and measured off a
    perspective will not agree to the millimetre, and demanding that they do would defeat
    the whole purpose.
    """
    return (
        element.get("item_type"),
        element.get("shape"),
        round(float(element.get("length_m") or 0.0) / 0.05),
        round(float(element.get("height_m") or 0.0) / 0.05),
    )


def _normalised_label(element):
    return re.sub(r"[^a-z0-9]+", " ", (element.get("label") or "").lower()).strip()


def reconcile(pages):
    """Links elements that appear on more than one sheet, and fills gaps between them.

    Two things happen here, and the second is the one that makes splitting a deck safe.

    **Cross-fill.** A tower dimensioned properly on an elevation and only partly readable
    on a perspective gets the elevation's number, with the source page recorded so the PM
    can see where it came from.

    **De-duplication.** The same object drawn on four sheets must be quoted once. Splitting
    pages into elements without this turns a 25-page deck into a systematic over-quote,
    which is a worse failure than the single wrong row it replaced. Duplicates are marked
    and excluded by default, never deleted — the PM can include any of them again, and the
    UI says which sheet the original was on.
    """
    by_signature = {}
    by_label = {}

    for page in pages:
        for element in page.get("elements") or []:
            element.setdefault("include", True)
            element["duplicate_of"] = None

            label = _normalised_label(element)
            if label and len(label) > 3:
                by_label.setdefault(label, []).append((page, element))

    # Cross-fill first, so a gap-filled element can then be recognised as a duplicate.
    for label, entries in by_label.items():
        donors = [(p, e) for p, e in entries
                  if e["length_m"] > 0 and e["height_m"] > 0]
        if not donors:
            continue
        # Prefer a flat page: its scale is page-wide and its numbers are the trustworthy
        # ones. That is the whole reason a mixed deck beats a deck of renders.
        donors.sort(key=lambda pe: (pe[0].get("page_kind") != "flat",))
        donor_page, donor = donors[0]

        for page, element in entries:
            if element is donor:
                continue
            filled = []
            for field in ("length_m", "height_m", "depth_m"):
                if float(element.get(field) or 0.0) <= 0 and float(donor.get(field) or 0.0) > 0:
                    element[field] = donor[field]
                    filled.append(field.replace("_m", ""))
            if filled:
                element["filled_from"] = {
                    "page": donor_page.get("page_number"),
                    "file": donor_page.get("file_name"),
                    "fields": filled,
                }
                if element.get("confidence") in (None, "none"):
                    element["confidence"] = "low"

    # De-duplicate on the reconciled dimensions.
    for page in pages:
        for element in page.get("elements") or []:
            if float(element.get("length_m") or 0.0) <= 0:
                continue
            signature = _signature(element)
            first = by_signature.get(signature)
            if first is None:
                by_signature[signature] = (page, element)
                continue
            first_page, first_element = first
            element["include"] = False
            element["duplicate_of"] = {
                "page": first_page.get("page_number"),
                "file": first_page.get("file_name"),
                "label": first_element.get("label"),
            }

    duplicates = sum(1 for p in pages for e in (p.get("elements") or [])
                     if e.get("duplicate_of"))
    return duplicates


def page_count(path):
    """How many pages a file will produce, without parsing any of them.

    Cheap: a PDF reports its own count, and any raster file is a single page. Lets the UI
    show real progress ("page 4 of 25") before the slow work starts.
    """
    path = Path(path)
    if path.suffix.lower() not in SUPPORTED_PDF:
        return 1
    try:
        document = fitz.open(str(path))
        try:
            return min(document.page_count, MAX_PAGES_PER_FILE)
        finally:
            document.close()
    except Exception:
        return 0


def parse_page_range(path, start=0, count=1):
    """Parses a slice of one file's pages.

    Returns the same page dicts `parse_files` produces, minus cross-page reconciliation —
    that needs every page and so is applied once at the end by `reconcile`.
    """
    path = Path(path)
    warnings = []
    if not path.exists():
        return {"success": False, "error": "File not found.", "drawings": [], "warnings": []}
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return {"success": False, "error": f"Unsupported type '{path.suffix}'.",
                "drawings": [], "warnings": []}

    try:
        if path.suffix.lower() in SUPPORTED_PDF:
            drawings = _parse_pdf(path, warnings, page_start=start, page_count=count)
        else:
            drawings = _parse_raster(path, warnings) if start == 0 else []
    except Exception as exc:
        return {"success": False, "error": str(exc), "drawings": [], "warnings": warnings}

    return {"success": True, "drawings": drawings, "warnings": warnings}


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

    duplicates = reconcile(drawings)
    if duplicates:
        warnings.append(
            f"{duplicates} element(s) appear on more than one sheet and are switched off "
            f"so they are quoted once. Turn any of them back on if they are separate builds."
        )

    return {
        "success": True,
        "drawings": drawings,
        "page_count": len(drawings),
        "element_count": sum(len(p.get("elements") or []) for p in drawings),
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
