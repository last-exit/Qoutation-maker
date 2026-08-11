"""Find the shape of a drawn object from the page image.

Curve detection used to read a PDF's vector arcs, which is exact but only works when the
export kept its linework as vectors. A SketchUp deck exported as flat images has none, so
every item on a rasterised drawing came out `Flat wall` — including the curved walls and
ring shelves these drawings are full of. A curved wall priced flat is under-quoted, and
nothing on screen says so.

This module reads pixels instead. It is deliberately a *reporter*: it takes an image and a
box, and returns what it thinks is in there. It never edits a spec, never prices anything,
and never decides what an item is called.

OpenCV arrives as a dependency of easyocr, so it costs nothing extra to use. It is still
imported defensively — a machine without easyocr simply gets no suggestions and the whole
estimator behaves exactly as it did before.

The bar for reporting a shape is deliberately high. A false "curved" is expensive twice
over: it inflates the price through arc length and the curved-work factor, and it demands a
curve rise the PM then has to invent. Straight panels must stay straight.
"""

import math

try:
    import cv2
    import numpy as np
    AVAILABLE = True
except ImportError:                       # easyocr not installed — degrade to no-op
    cv2 = None
    np = None
    AVAILABLE = False


# A circle must fill at least this much of the shorter side of its box to count. Below it,
# the "circle" is a bolt head, a logo, or a dot on a leader line.
MIN_CIRCLE_FILL = 0.35

# How far a fitted arc must bow, as a fraction of its chord, before it is a curve rather
# than a straight line drawn slightly off. Matches the flatness threshold already used when
# reading vector arcs, so both paths agree on what "curved" means.
MIN_BOW_RATIO = 0.02

# An ellipse fit this far off the actual contour is not describing that contour.
MAX_FIT_RESIDUAL_PX = 6.0

# Detection runs on a downscaled copy. A page renders at ~2880x1620, and running Hough over
# a crop that size costs ~13 seconds *per element* — a 25-page deck then sits on the loading
# spinner for minutes. Shapes that matter here are walls, portals and shelves: they occupy a
# large share of their own box, so they survive downscaling intact, while the cost falls by
# the square of the factor. Everything measured is scaled back to page pixels before it is
# reported, so callers never see detection-space numbers.
DETECT_MAX_PX = 700


def _crop(image, bbox):
    """The region of `image` inside `bbox`, as greyscale. None if the box is unusable."""
    if image is None or not bbox:
        return None
    height, width = image.shape[:2]
    x0 = max(0, int(bbox[0]))
    y0 = max(0, int(bbox[1]))
    x1 = min(width, int(bbox[2]))
    y1 = min(height, int(bbox[3]))
    if x1 - x0 < 12 or y1 - y0 < 12:
        return None
    region = image[y0:y1, x0:x1]
    if region.ndim == 3:
        region = cv2.cvtColor(region, cv2.COLOR_RGB2GRAY)

    # Downscale for detection and report how much, so measurements can be scaled back.
    longest = max(region.shape[:2])
    if longest > DETECT_MAX_PX:
        factor = longest / float(DETECT_MAX_PX)
        region = cv2.resize(region,
                            (max(1, int(region.shape[1] / factor)),
                             max(1, int(region.shape[0] / factor))),
                            interpolation=cv2.INTER_AREA)
        return region, factor
    return region, 1.0


def _detect_circle(grey):
    """The strongest circle in the crop, as (cx, cy, r) in crop pixels, or None."""
    short_side = min(grey.shape[:2])
    circles = cv2.HoughCircles(
        cv2.medianBlur(grey, 3),
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=short_side * 0.5,
        param1=120,          # Canny high threshold
        param2=45,           # accumulator threshold: higher = fewer, surer circles
        minRadius=int(short_side * MIN_CIRCLE_FILL / 2),
        maxRadius=int(short_side * 0.55),
    )
    if circles is None:
        return None
    # HoughCircles returns them strongest-first.
    cx, cy, r = circles[0][0]
    return float(cx), float(cy), float(r)


def _largest_contour(grey):
    """The biggest closed contour in the crop, or None."""
    edges = cv2.Canny(grey, 80, 180)
    found = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = found[0] if len(found) == 2 else found[1]
    if not contours:
        return None
    biggest = max(contours, key=cv2.contourArea)
    return biggest if len(biggest) >= 5 else None      # fitEllipse needs 5 points


def _is_straight_edged(contour):
    """True when a contour is made of straight runs — a rectangle, a panel, a mesh cell.

    This check has to come before any bow measurement. A rectangle is a *closed* contour, so
    its first and last points sit next to each other: the chord between them is almost zero
    and the "bow" against it is enormous, which reads as a violently curved shape. Every
    flat panel on a drawing would be priced as curved joinery.

    `approxPolyDP` answers the real question — can this outline be drawn with a handful of
    straight lines? A rectangle collapses to 4 vertices; a genuine arc keeps many.
    """
    perimeter = cv2.arcLength(contour, True)
    if perimeter <= 0:
        return True
    approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
    return len(approx) <= 6


def _bow_of_contour(contour):
    """How far a contour bows from the straight line joining its two furthest points.

    Returns (chord_px, sagitta_px) — the pair `curves.radius_from_chord_and_sagitta`
    consumes, so a detected curve arrives with its rise already measured rather than left
    for the PM to eyeball.

    The endpoints are the two most distant points on the contour, not its first and last.
    For an open polyline those are the same thing; for anything closed they are not, and
    using first/last is what makes a rectangle look like a violent curve.
    """
    points = contour.reshape(-1, 2).astype(float)
    if len(points) < 3:
        return 0.0, 0.0

    # Two furthest-apart points, computed on the convex hull. Vectorised rather than a
    # double Python loop: a busy contour's hull can carry hundreds of points, and the
    # pairwise scan then costs tens of thousands of interpreted iterations per element.
    hull = cv2.convexHull(contour).reshape(-1, 2).astype(float)
    if len(hull) < 2:
        return 0.0, 0.0
    deltas = hull[:, None, :] - hull[None, :, :]
    pair_distances = np.hypot(deltas[..., 0], deltas[..., 1])
    i, j = np.unravel_index(int(pair_distances.argmax()), pair_distances.shape)
    start, end = hull[i], hull[j]

    chord = float(pair_distances[i, j])
    if chord <= 1:
        return 0.0, 0.0

    # Perpendicular distance of every point from the chord; the maximum is the sagitta.
    dx, dy = end[0] - start[0], end[1] - start[1]
    distances = np.abs(
        (dx * (start[1] - points[:, 1])) - ((start[0] - points[:, 0]) * dy)
    ) / chord
    return float(chord), float(distances.max())


def detect(page_image, bbox, px_per_m=0.0):
    """What shape occupies `bbox` on `page_image`.

    Returns None when nothing is confidently found — which leaves the element exactly as it
    was. A returned dict carries `shape`, a `confidence`, the reason, and any geometry that
    could be measured in metres (only possible where the element has a local scale).
    """
    if not AVAILABLE or page_image is None:
        return None

    array = np.asarray(page_image)
    cropped = _crop(array, bbox)
    if cropped is None:
        return None
    grey, scale = cropped          # `scale` converts detection pixels back to page pixels

    # --- Ring: a strong circle filling much of the box ---------------------------------
    circle = _detect_circle(grey)
    if circle is not None:
        _, _, radius_px = circle
        result = {
            "shape": "ring",
            "confidence": "medium",
            "reason": "a circle was found in the drawing",
        }
        if px_per_m > 0:
            result["outer_r_m"] = round((radius_px * scale) / px_per_m, 3)
        return result

    # --- Curve: a contour that bows away from its own chord ----------------------------
    contour = _largest_contour(grey)
    if contour is None or _is_straight_edged(contour):
        return None                       # a panel, a frame, a mesh cell — leave it flat

    chord_px, sagitta_px = _bow_of_contour(contour)
    if chord_px <= 0 or sagitta_px / chord_px < MIN_BOW_RATIO:
        return None                       # straight enough to be a flat panel

    # An ellipse fit confirms the bow is a genuine arc rather than a corner or a zigzag.
    try:
        (_, _), (axis_a, axis_b), _ = cv2.fitEllipse(contour)
    except cv2.error:
        return None
    if max(axis_a, axis_b) <= 0:
        return None

    result = {
        "shape": "curved",
        "confidence": "medium",
        "reason": "the outline bows rather than running straight",
    }
    if px_per_m > 0:
        result["sagitta_m"] = round((sagitta_px * scale) / px_per_m, 3)
    return result


def apply_to_elements(page_image, elements):
    """Sets the detected shape on each element that has not been set by a person.

    Mutates `elements` in place and returns how many were changed. Two rules matter:

    * A `shape_source` of `user` is never touched. A PM correction that a later re-parse
      silently undoes is worse than no detection at all.
    * A curve detected without a local scale keeps the shape but gets no rise, so the item
      asks for it. The existing rule that a curve with no rise refuses to price still holds
      — this must not invent the one number that decides the curve's cost.
    """
    if not AVAILABLE or page_image is None:
        return 0

    changed = 0
    for element in elements or []:
        if element.get("shape_source") == "user":
            continue
        found = detect(page_image, element.get("bbox_px"), element.get("px_per_m") or 0.0)
        if not found:
            element.setdefault("shape_source", "default")
            continue

        element["shape"] = found["shape"]
        element["shape_source"] = "detected"
        element["shape_reason"] = found["reason"]
        for field in ("outer_r_m", "sagitta_m"):
            if field in found:
                element[field] = found[field]
        changed += 1

    return changed
