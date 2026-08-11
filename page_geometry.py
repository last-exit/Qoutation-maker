"""Line geometry off a drawing page, and what it tells you about the objects on it.

The estimator's original parser flattened a page into one bag of text and took the two
largest numbers it found. That throws away the single most useful thing on a drawing: a
dimension callout is not floating text, it is a value *attached by witness lines to the
thing it measures*. Recovering that attachment is what lets one page yield eight items
instead of one wrong one.

Two sources of line geometry, tried in order:

* **Vector paths** (`fitz.Page.get_drawings`). Exact endpoints, no thresholds, no guessing.
  A SketchUp/Layout PDF usually keeps its linework as vectors even when the shaded render
  beside it is a raster and the text has been outlined — which is exactly the page that
  reads as "OCR" and looks like the hard case. It is not: its geometry is perfect.
* **Raster scan** (numpy). For a PNG/JPG, or a PDF page that really is a flat bitmap.
  Detects axis-aligned runs of dark pixels, which is what dimension and witness lines are
  on the overwhelming majority of drawings.

The raster path deliberately does *not* attempt oblique lines. A general Hough transform
would find them, and would also find every edge of every shaded solid on a 3D render,
producing confident nonsense. Axis-aligned runs are the signal that is reliably a drawing
annotation rather than the drawing's subject. Callouts on a steeply oblique leader are
reported as unattached rather than guessed at — see `unattached` in `measure`.

No OpenCV. The project deliberately runs on a lean dependency set (see requirements.txt),
and everything here is numpy and Pillow, both already present.
"""

import math

try:
    import numpy as np
except ImportError:                       # numpy is pinned in requirements, but never
    np = None                             # let a missing optional break the whole parse

# A segment must be at least this fraction of the page's larger side to count as a
# dimension line. Below it you are collecting hatching, text strokes and shading edges.
MIN_SEGMENT_FRACTION = 0.02

# Dark-pixel threshold for the raster scan, 0-255. Dimension lines on these exports are
# near-black; the shaded solids are mid-greys, which this deliberately excludes.
DARK_THRESHOLD = 110

# A run may skip this many light pixels and still count as one line — covers antialiasing
# gaps and the break a dimension line leaves for its own text.
MAX_RUN_GAP_PX = 6

# How far a witness line may sit from a dimension's text and still be read as its bracket,
# as a fraction of the page's larger side.
ATTACH_RADIUS_FRACTION = 0.06

# How far apart two non-crossing dimension brackets may sit and still be read as measuring
# the same object, as a fraction of that object's own size. A dimension line is normally
# offset a little way outside what it measures, so its brackets stop short of each other
# rather than meeting. Large enough to group a tower's width and height, small enough not to
# swallow the counter standing next to it.
CLUSTER_GAP_FRACTION = 0.12


# --- Segment model ---------------------------------------------------------------------

def _segment(x0, y0, x1, y1):
    """A line segment with its orientation precomputed."""
    length = math.hypot(x1 - x0, y1 - y0)
    angle = math.degrees(math.atan2(y1 - y0, x1 - x0)) % 180.0
    if angle < 15 or angle > 165:
        axis = "h"
    elif 75 < angle < 105:
        axis = "v"
    else:
        axis = "o"                        # oblique
    return {"x0": float(x0), "y0": float(y0), "x1": float(x1), "y1": float(y1),
            "length": length, "angle": angle, "axis": axis}


# --- Vector extraction -----------------------------------------------------------------

def segments_from_pdf_page(page, scale=1.0):
    """Line segments from a PDF page's vector drawing operators.

    `scale` matches the render matrix used for the page preview, so segment coordinates
    land in the same pixel space as the thumbnail and the OCR boxes.
    """
    segments = []
    try:
        drawings = page.get_drawings()
    except Exception:
        return segments

    for path in drawings:
        for item in path.get("items", []):
            op = item[0]
            try:
                if op == "l":                       # line
                    p0, p1 = item[1], item[2]
                    segments.append(_segment(p0.x * scale, p0.y * scale,
                                             p1.x * scale, p1.y * scale))
                elif op == "re":                    # rectangle -> its four sides
                    rect = item[1]
                    x0, y0 = rect.x0 * scale, rect.y0 * scale
                    x1, y1 = rect.x1 * scale, rect.y1 * scale
                    segments.extend([
                        _segment(x0, y0, x1, y0), _segment(x1, y0, x1, y1),
                        _segment(x1, y1, x0, y1), _segment(x0, y1, x0, y0),
                    ])
            except Exception:
                # One malformed path never costs the whole page its geometry.
                continue

    return segments


def curves_from_pdf_page(page, scale=1.0):
    """Bezier curve spans, which is how a PDF stores an arc.

    Returned as chord-and-bulge rather than control points, because that is what the
    pricing model asks for: `curves.radius_from_chord_and_sagitta` wants exactly these two
    numbers. A curved wall drawn in elevation lands here with its rise already measured,
    which is the dimension a PM would otherwise have to read off the drawing by eye.
    """
    found = []
    try:
        drawings = page.get_drawings()
    except Exception:
        return found

    for path in drawings:
        for item in path.get("items", []):
            if item[0] != "c":
                continue
            try:
                p0, p1, p2, p3 = item[1], item[2], item[3], item[4]
            except Exception:
                continue

            x0, y0 = p0.x * scale, p0.y * scale
            x3, y3 = p3.x * scale, p3.y * scale
            chord = math.hypot(x3 - x0, y3 - y0)
            if chord <= 0:
                continue

            # Sagitta: the furthest the curve strays from its own chord. For a cubic the
            # extreme is at or near t=0.5, which is close enough for a build estimate and
            # avoids solving the curve.
            mx = (x0 + 3 * p1.x * scale + 3 * p2.x * scale + x3) / 8.0
            my = (y0 + 3 * p1.y * scale + 3 * p2.y * scale + y3) / 8.0
            sagitta = abs((x3 - x0) * (y0 - my) - (x0 - mx) * (y3 - y0)) / chord

            found.append({
                "x0": x0, "y0": y0, "x1": x3, "y1": y3,
                "chord_px": chord, "sagitta_px": sagitta,
                "bbox": (min(x0, x3), min(y0, y3), max(x0, x3), max(y0, y3)),
            })
    return found


# --- Raster extraction -----------------------------------------------------------------

def segments_from_image(pil_image, max_side=1600):
    """Axis-aligned dark runs in a bitmap, as segments in the image's own pixel space.

    Works on a downscaled copy for speed and scales the result back up; a dimension line is
    tens of pixels long, so nothing that matters is lost at 1600 px.
    """
    if np is None or pil_image is None:
        return []

    width, height = pil_image.size
    if not width or not height:
        return []

    scale = 1.0
    image = pil_image
    if max(width, height) > max_side:
        scale = max(width, height) / float(max_side)
        image = pil_image.copy()
        image.thumbnail((max_side, max_side))

    grey = np.asarray(image.convert("L"))
    dark = grey < DARK_THRESHOLD
    if not dark.any():
        return []

    rows, cols = dark.shape
    min_len = max(12, int(max(dark.shape) * MIN_SEGMENT_FRACTION))
    # A run within a couple of pixels of the image edge is the border of the picture, not a
    # line in the drawing; a run that spans almost the whole side is the page frame. Both are
    # axis-aligned and would fool the flat/perspective test, so they are dropped here.
    edge_r, edge_c = max(2, int(rows * 0.02)), max(2, int(cols * 0.02))
    segments = []

    # Rows then columns. `_runs` finds maximal dark runs allowing small gaps.
    for row_index in range(rows):
        if row_index <= edge_r or row_index >= rows - edge_r:
            continue
        for start, end in _runs(dark[row_index], min_len):
            if start <= edge_c and end >= cols - edge_c:
                continue                       # full-width frame line
            segments.append(_segment(start * scale, row_index * scale,
                                     end * scale, row_index * scale))
    for col_index in range(cols):
        if col_index <= edge_c or col_index >= cols - edge_c:
            continue
        for start, end in _runs(dark[:, col_index], min_len):
            if start <= edge_r and end >= rows - edge_r:
                continue                       # full-height frame line
            segments.append(_segment(col_index * scale, start * scale,
                                     col_index * scale, end * scale))

    return _merge_parallel(segments)


def _runs(mask, min_len):
    """Maximal True runs in a 1-D boolean array, tolerating gaps up to MAX_RUN_GAP_PX."""
    indices = np.flatnonzero(mask)
    if indices.size == 0:
        return []

    runs = []
    start = prev = indices[0]
    for value in indices[1:]:
        if value - prev <= MAX_RUN_GAP_PX:
            prev = value
            continue
        if prev - start >= min_len:
            runs.append((int(start), int(prev)))
        start = prev = value
    if prev - start >= min_len:
        runs.append((int(start), int(prev)))
    return runs


def _merge_parallel(segments, tolerance=2.0):
    """Collapses the many one-pixel-tall rows of a thick line into a single segment.

    A 3 px dimension line otherwise arrives as three separate parallel segments, which
    would then be counted three times when classifying the page.
    """
    merged = []
    for axis in ("h", "v"):
        group = [s for s in segments if s["axis"] == axis]
        group.sort(key=lambda s: (s["y0"] if axis == "h" else s["x0"],
                                  s["x0"] if axis == "h" else s["y0"]))
        current = None
        for seg in group:
            if current is None:
                current = dict(seg)
                continue
            if axis == "h":
                same_line = abs(seg["y0"] - current["y0"]) <= tolerance
                overlaps = seg["x0"] <= current["x1"] + tolerance
            else:
                same_line = abs(seg["x0"] - current["x0"]) <= tolerance
                overlaps = seg["y0"] <= current["y1"] + tolerance
            if same_line and overlaps:
                current["x1"] = max(current["x1"], seg["x1"])
                current["y1"] = max(current["y1"], seg["y1"])
                current["length"] = math.hypot(current["x1"] - current["x0"],
                                               current["y1"] - current["y0"])
            else:
                merged.append(current)
                current = dict(seg)
        if current is not None:
            merged.append(current)

    merged.extend(s for s in segments if s["axis"] == "o")
    return merged


# --- Page classification ---------------------------------------------------------------

def _is_frame_segment(seg, page_size):
    """True for a segment that is the image's own border or page frame, not drawing content.

    A rendered page sits inside a rectangular image, and that rectangle — plus any full-page
    border box the export draws — is perfectly axis-aligned. Counting it as linework makes a
    3D perspective view score as flat, which is exactly the mislabelling seen on the Mirdif
    deck. Both the edge-hugging border and any near-full-span straight line are excluded.
    """
    width, height = page_size
    if not width or not height:
        return False
    edge = 0.02
    margin_x, margin_y = width * edge, height * edge

    if seg["axis"] == "h":
        near_edge = seg["y0"] <= margin_y or seg["y0"] >= height - margin_y
        spans_page = seg["length"] >= width * 0.95
    elif seg["axis"] == "v":
        near_edge = seg["x0"] <= margin_x or seg["x0"] >= width - margin_x
        spans_page = seg["length"] >= height * 0.95
    else:
        return False
    return near_edge or spans_page


def classify_page(segments, page_size=None, min_segments=8):
    """`flat` for an orthographic elevation or plan, `perspective` for a 3D view.

    A flat drawing's linework is overwhelmingly axis-aligned — the drawing's own edges as
    well as its dimension lines. A perspective view sends every receding edge off at its own
    angle, so the axis-aligned share collapses.

    When `page_size` is given, the image border and any full-page frame are excluded first,
    because those are axis-aligned no matter what the drawing is and would otherwise drag a
    perspective page over the line into `flat`.

    Returns (kind, detail). When there is too little *interior* linework to judge, the answer
    is `perspective`: the conservative pipeline, where being wrong costs a few undetected
    elements rather than a page of confidently wrong dimensions.
    """
    usable = [s for s in segments if s["length"] > 0]
    if page_size:
        usable = [s for s in usable if not _is_frame_segment(s, page_size)]

    if len(usable) < min_segments:
        return "perspective", {"reason": "too little interior linework to classify",
                               "segments": len(usable), "axis_aligned_ratio": 0.0}

    total_length = sum(s["length"] for s in usable)
    aligned_length = sum(s["length"] for s in usable if s["axis"] in ("h", "v"))
    ratio = aligned_length / total_length if total_length else 0.0

    kind = "flat" if ratio >= 0.72 else "perspective"
    return kind, {
        "reason": f"{ratio * 100:.0f}% of interior linework is axis-aligned",
        "segments": len(usable),
        "axis_aligned_ratio": round(ratio, 3),
    }


# --- Measured spans --------------------------------------------------------------------

def measure(tokens, segments, page_size):
    """Ties each dimension token to the segment it dimensions.

    `tokens` are OCR/vector text hits: {"text", "meters", "bbox": (x0, y0, x1, y1)}.
    Returns (spans, unattached). A span is the payload the rest of the estimator wants:

        {value_m, axis, bbox, px_len, px_per_m, token}

    `px_per_m` is a *local* scale. On a perspective page it legitimately differs across the
    image, and that is the point — solving scale per element is what makes foreshortening
    stop mattering. A page-wide scale is only meaningful on a flat page, where
    `page_scale` computes it from these spans.
    """
    width, height = page_size
    reach = max(width, height) * ATTACH_RADIUS_FRACTION
    spans, unattached = [], []

    candidates = [s for s in segments
                  if s["axis"] in ("h", "v")
                  and s["length"] >= max(width, height) * MIN_SEGMENT_FRACTION]

    for token in tokens or []:
        bbox = token.get("bbox")
        meters = float(token.get("meters") or 0.0)
        if not bbox or meters <= 0:
            continue

        cx = (bbox[0] + bbox[2]) / 2.0
        cy = (bbox[1] + bbox[3]) / 2.0

        best, best_distance = None, None
        for seg in candidates:
            distance = _point_to_segment(cx, cy, seg)
            if distance > reach:
                continue
            # A dimension's text sits *along* its line, so prefer the segment the text is
            # centred on over a longer one that merely passes nearby.
            if best_distance is None or distance < best_distance:
                best, best_distance = seg, distance

        if best is None:
            unattached.append(token)
            continue

        px_len = best["length"]
        if px_len <= 0:
            unattached.append(token)
            continue

        spans.append({
            "value_m": meters,
            "axis": best["axis"],
            "bbox": (min(best["x0"], best["x1"]), min(best["y0"], best["y1"]),
                     max(best["x0"], best["x1"]), max(best["y0"], best["y1"])),
            "px_len": round(px_len, 2),
            "px_per_m": round(px_len / meters, 2),
            "token": token.get("text", ""),
            "distance_px": round(best_distance, 1),
        })

    return spans, unattached


def _point_to_segment(px, py, seg):
    """Shortest distance from a point to a line segment."""
    x0, y0, x1, y1 = seg["x0"], seg["y0"], seg["x1"], seg["y1"]
    dx, dy = x1 - x0, y1 - y0
    if dx == 0 and dy == 0:
        return math.hypot(px - x0, py - y0)
    t = ((px - x0) * dx + (py - y0) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


def page_scale(spans):
    """One pixels-per-metre figure for a flat page, with the outliers named.

    Uses the median rather than a least-squares fit: a single misread callout — 2400 read
    as 400 — would drag a mean badly, and on a drawing the honest reading is that most
    callouts agree and one does not. Spans more than 25% off the median are returned as
    `outliers` so the UI can show which callout to check.
    """
    usable = [s for s in spans if s.get("px_per_m", 0) > 0]
    if not usable:
        return 0.0, []

    values = sorted(s["px_per_m"] for s in usable)
    middle = len(values) // 2
    median = (values[middle] if len(values) % 2
              else (values[middle - 1] + values[middle]) / 2.0)
    if median <= 0:
        return 0.0, []

    outliers = [s for s in usable if abs(s["px_per_m"] - median) / median > 0.25]
    return round(median, 2), outliers


# --- Clustering into elements ------------------------------------------------------------

def cluster(spans):
    """Groups spans that measure the same object.

    Spans whose bounding boxes overlap, or whose brackets share an endpoint region, are
    describing one thing: the 240 cm height and the 110 cm width of the same tower cross at
    its corner. Each returned cluster is one element candidate, carrying every span that
    supports it — which is what lets the UI say "height from this callout" later.
    """
    remaining = list(spans)
    clusters = []

    while remaining:
        seed = remaining.pop(0)
        group = [seed]
        box = list(seed["bbox"])

        changed = True
        while changed:
            changed = False
            for span in list(remaining):
                if _boxes_related(box, span["bbox"]):
                    group.append(span)
                    remaining.remove(span)
                    box = [min(box[0], span["bbox"][0]), min(box[1], span["bbox"][1]),
                           max(box[2], span["bbox"][2]), max(box[3], span["bbox"][3])]
                    changed = True
        clusters.append({"spans": group, "bbox": tuple(box)})

    return clusters


def _boxes_related(a, b):
    """True when two spans plausibly bracket the same object.

    A dimension bracket is a *line*, so its box is long in one direction and has almost no
    thickness in the other. That makes an area-overlap test the wrong instrument: the width
    and height callouts of one object cross at its corner, and the area they share is
    thickness x thickness — a few square pixels against boxes of many thousands. Judged by
    area ratio those two obviously-related brackets look unrelated, and every object on the
    sheet splits into two half-dimensioned halves.

    Crossing is therefore the test, with a proximity fallback for brackets that stop just
    short of each other, as an offset dimension line does.
    """
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b

    overlap_w = min(ax1, bx1) - max(ax0, bx0)
    overlap_h = min(ay1, by1) - max(ay0, by0)
    if overlap_w > 0 and overlap_h > 0:
        return True

    # Not crossing: related only if they very nearly touch, measured against the size of
    # the object they would be describing rather than an absolute pixel figure.
    gap_x = max(0.0, max(ax0, bx0) - min(ax1, bx1))
    gap_y = max(0.0, max(ay0, by0) - min(ay1, by1))
    span_scale = max(ax1 - ax0, ay1 - ay0, bx1 - bx0, by1 - by0, 1.0)
    reach = span_scale * CLUSTER_GAP_FRACTION
    return gap_x < reach and gap_y < reach
