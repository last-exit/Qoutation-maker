"""Curved-geometry mathematics for the Automated Design Estimator.

Pure functions over numbers. Nothing here reads a rate card, prices anything, or knows
what an item is — `calculators.py` owns all of that. This module exists because the
estimator's original geometry was entirely rectilinear (length x height x depth, flat
faces), and a stand full of curved walls, ring shelves and arched portals cannot be
described that way at all, let alone priced.

The three shapes that matter, and why each needs its own formula:

* **Curved wall.** A 3 m chord bent into an arc has *more* cladding on it than 3 m — the
  arc length. Pricing the chord under-quotes every curve on the drawing, and it does so
  invisibly, because the number looks like a perfectly ordinary wall cost.
* **Ring / annular shelf.** A doughnut of sheet material. Its area is not width x depth,
  and it nests badly on an 8x4 sheet, so it carries its own wastage.
* **Arch.** The band follows the arc over the opening, not the straight run of
  `(2 x height) + length` that the flat model assumed.

Every function is total: given nonsense it returns 0.0 rather than raising, because these
feed a live UI where a half-typed dimension must not throw. Callers that need to know a
value was unusable check for a zero result.
"""

import math

# Two curves are treated as the same shape when their radii agree this closely. Used by
# cross-page reconciliation to decide that the arc on page 4 and the arc on page 7 are one
# object quoted twice. 4% absorbs draughting and pixel-measurement noise without merging a
# 1.2 m ring into a 1.8 m one.
RADIUS_MATCH_TOLERANCE = 0.04

# Below this included angle a "curve" is a straight panel with a rounded corner, and
# forcing the curved build-up (thin skins, tight stud centres) onto it would over-quote.
MIN_CURVE_ANGLE_DEG = 5.0


def radius_from_chord_and_sagitta(chord_m, sagitta_m):
    """Radius of the circle a drawn arc belongs to.

    Draughtsmen rarely dimension a radius. What a drawing gives you is the chord (the
    straight distance across the opening) and the sagitta — the "bulge", measured from the
    midpoint of the chord to the arc. Both are directly measurable off an elevation, which
    is why this is the entry point for nearly every curve the parser finds.

        r = c^2 / (8h) + h / 2
    """
    chord_m = float(chord_m or 0.0)
    sagitta_m = float(sagitta_m or 0.0)
    if chord_m <= 0 or sagitta_m <= 0:
        return 0.0
    return (chord_m ** 2) / (8.0 * sagitta_m) + sagitta_m / 2.0


def included_angle_deg(chord_m, radius_m, sagitta_m=None):
    """The angle the arc subtends at its centre, in degrees.

    `atan2` is used rather than `asin` so that a *major* arc — one bulging past its own
    centre, which is what a barrel-fronted counter or a full ring actually is — comes back
    as the reflex angle it really is instead of silently folding back under 180 degrees.
    That fold is a genuine trap: it would halve the arc length of every deep curve.
    """
    chord_m = float(chord_m or 0.0)
    radius_m = float(radius_m or 0.0)
    if chord_m <= 0 or radius_m <= 0:
        return 0.0

    half_chord = chord_m / 2.0
    if half_chord > radius_m:
        # Chord longer than the diameter: the two numbers disagree. The most that can be
        # meant is a half-circle, so clamp rather than return a NaN into a price.
        return 180.0

    if sagitta_m is None:
        # Without a sagitta there is no way to tell a minor arc from a major one; the
        # minor reading is the conservative choice because it never over-states area.
        return math.degrees(2.0 * math.asin(half_chord / radius_m))

    centre_to_chord = radius_m - float(sagitta_m or 0.0)
    return math.degrees(2.0 * math.atan2(half_chord, centre_to_chord))


def arc_length(radius_m, angle_deg):
    """Developed length of an arc — the material actually wrapped around it."""
    radius_m = float(radius_m or 0.0)
    angle_deg = float(angle_deg or 0.0)
    if radius_m <= 0 or angle_deg <= 0:
        return 0.0
    return radius_m * math.radians(min(angle_deg, 360.0))


def arc_length_from_chord(chord_m, sagitta_m):
    """Developed length straight from the two dimensions a drawing gives you.

    Falls back to the chord when the sagitta is missing or degenerate: a flat panel is the
    honest reading of "no bulge", and it is also what the old rectilinear model assumed, so
    this can never price *less* than the code it replaces.
    """
    chord_m = float(chord_m or 0.0)
    if chord_m <= 0:
        return 0.0
    radius = radius_from_chord_and_sagitta(chord_m, sagitta_m)
    if radius <= 0:
        return chord_m
    angle = included_angle_deg(chord_m, radius, sagitta_m)
    if angle < MIN_CURVE_ANGLE_DEG:
        return chord_m
    return arc_length(radius, angle)


def annulus_area(outer_r_m, inner_r_m=0.0):
    """Plan area of a ring shelf. A solid disc is the inner radius at zero."""
    outer_r_m = float(outer_r_m or 0.0)
    inner_r_m = max(0.0, float(inner_r_m or 0.0))
    if outer_r_m <= 0:
        return 0.0
    inner_r_m = min(inner_r_m, outer_r_m)
    return math.pi * (outer_r_m ** 2 - inner_r_m ** 2)


def annulus_edge_length(outer_r_m, inner_r_m=0.0):
    """Total edge to be banded or lipped: both circumferences of the ring.

    Edging a ring is a real line on the bill — it is the slow part of making one — and it
    scales with circumference, not with area.
    """
    outer_r_m = float(outer_r_m or 0.0)
    inner_r_m = max(0.0, float(inner_r_m or 0.0))
    if outer_r_m <= 0:
        return 0.0
    inner_r_m = min(inner_r_m, outer_r_m)
    edges = 2.0 * math.pi * outer_r_m
    if inner_r_m > 0:
        edges += 2.0 * math.pi * inner_r_m
    return edges


def arch_band_run(opening_m, height_m, sagitta_m=None, radius_m=None):
    """Length of the band running up one leg, over the arc, and down the other.

    The flat model used `(2 x height) + opening`, which is a square-headed portal. A real
    arched portal's head is an arc, and its legs stop where the arc springs — so the naive
    formula both over-counts the legs and under-counts the head.

    `height_m` is the overall height to the crown. When the arc's rise is unknown the
    opening is assumed to be a semicircle, the commonest portal on an exhibition stand.
    """
    opening_m = float(opening_m or 0.0)
    height_m = float(height_m or 0.0)
    if opening_m <= 0 or height_m <= 0:
        return 0.0

    rise = float(sagitta_m or 0.0)
    if rise <= 0:
        if radius_m:
            # Rise implied by the radius, capped at a semicircle.
            radius_m = float(radius_m)
            half = opening_m / 2.0
            if radius_m >= half:
                rise = radius_m - math.sqrt(max(0.0, radius_m ** 2 - half ** 2))
        if rise <= 0:
            rise = opening_m / 2.0     # semicircular head

    rise = min(rise, height_m)         # the head cannot be taller than the portal
    leg_height = max(0.0, height_m - rise)
    head_run = arc_length_from_chord(opening_m, rise)
    return (2.0 * leg_height) + head_run


def is_curved(shape):
    """True for shapes that cost more to make than a flat panel of the same area.

    Covers rings, which are slow to cut and edge even though nothing about them is bent.
    Use this for labour, not for build-up.
    """
    return shape in ("curved", "ring", "arch")


def is_bent(shape):
    """True only for shapes formed by bending material around a former.

    The distinction matters and is easy to get wrong: a ring shelf is *curved* but it is
    not *bent*. It is a disc cut flat out of ordinary board, so giving it the flexible
    thin-skin build-up of a curved wall would swap its 18 mm carcass for two 6 mm skins it
    never has — a cheaper board, twice over, for a part that is simply sawn out.
    """
    return shape in ("curved", "arch")


def describe(shape, geometry):
    """One-line human summary of a curve, for the `basis` strings and the UI.

    Kept here so the wording of a curve is written once and cannot drift between the
    quotation document, the cost breakdown and the estimator card.
    """
    geometry = geometry or {}
    if shape == "ring":
        outer = float(geometry.get("outer_r_m") or 0.0)
        inner = float(geometry.get("inner_r_m") or 0.0)
        if inner > 0:
            return f"ring, R{outer:.3f} m outer / R{inner:.3f} m inner"
        return f"disc, R{outer:.3f} m"
    if shape in ("curved", "arch"):
        radius = float(geometry.get("radius_m") or 0.0)
        angle = float(geometry.get("included_angle_deg") or 0.0)
        if radius > 0 and angle > 0:
            return f"arc R{radius:.3f} m over {angle:.1f} deg"
        sagitta = float(geometry.get("sagitta_m") or 0.0)
        if sagitta > 0:
            return f"arc, {sagitta:.3f} m rise"
        return "arc, rise not stated"
    return "flat"
