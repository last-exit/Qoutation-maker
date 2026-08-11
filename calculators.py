"""Deterministic BOQ rules engine for the Automated Design Estimator.

Every number this module produces is plain Python arithmetic over the dimensions handed
to it and the prices in `master_rate_card.csv`. There is no model, no embedding and no
inference anywhere in this file — the same drawing must always cost the same, and a PM
must be able to follow any figure on the quotation back to a formula printed beside it.

That auditability is why each computed line carries a `basis` string: the human-readable
derivation ("18.40 m2 x 1.10 wastage / 2.9768 m2 per sheet = 6.80 -> 7 sheets") is
rendered directly in the UI next to the cost it produced.
"""

import math

import curves
import materials as materials_module
import rate_card as rate_card_module
import shapes as shapes_module
import shop_config


# --- Physical constants -------------------------------------------------------------

# Standard 8ft x 4ft board. The exact geometric area is 2.4384 m x 1.2192 m = 2.97289728 m2;
# the trade (and this project's spec) rounds to 2.9768, which is what gets used so the
# estimator agrees with the sheet counts on the business's existing hand-built cost sheets.
SHEET_AREA_M2 = 2.9768

# Cut-and-fit offcuts. Applied to area before the ceiling to sheets, never after, so a
# 3-sheet job does not silently become 4 through double-rounding.
WASTAGE_FACTOR = 0.10

# Framing geometry.
STUD_SPACING_M = 0.60      # vertical stud centres
STUD_PIECE_LEN_M = 4.0     # WD-FRM-2X2 / WD-FRM-2X4 ship as 4m pieces

# Consumable ratios, measured off completed jobs rather than guessed.
SCREWS_PER_BOX = 1000
SCREWS_PER_STUD_JOINT = 6
BRACKETS_PER_STUD_PIECE = 2
ADHESIVE_M2_PER_DRUM = 55.0     # 15L contact adhesive drum, laminate bonding
WOOD_GLUE_M2_PER_CAN = 90.0     # 5L PVA
SILICONE_M_PER_TUBE = 12.0      # 300ml tube, joint sealing


# --- Item type geometry -------------------------------------------------------------
# Each builder returns the list of individual surfaces that make up a fabricated item, so
# the UI can show *which* faces were counted rather than one opaque area figure.

def _wall_surfaces(length_m, height_m, depth_m, faces):
    """A feature wall: clad face(s) plus the returns at each end if it has depth."""
    surfaces = []
    for face in range(max(1, int(faces))):
        surfaces.append({
            "name": f"Clad face {face + 1}",
            "formula": f"{length_m:.3f} m x {height_m:.3f} m",
            "area_m2": length_m * height_m,
        })
    if depth_m > 0:
        surfaces.append({
            "name": "End returns (2)",
            "formula": f"2 x {depth_m:.3f} m x {height_m:.3f} m",
            "area_m2": 2 * depth_m * height_m,
        })
    return surfaces


def _counter_surfaces(length_m, height_m, depth_m, faces):
    """A kiosk/bar counter: front fascia, worktop, two ends, and a back panel per `faces`."""
    surfaces = [
        {
            "name": "Front fascia",
            "formula": f"{length_m:.3f} m x {height_m:.3f} m",
            "area_m2": length_m * height_m,
        },
        {
            "name": "Worktop",
            "formula": f"{length_m:.3f} m x {depth_m:.3f} m",
            "area_m2": length_m * depth_m,
        },
        {
            "name": "End panels (2)",
            "formula": f"2 x {depth_m:.3f} m x {height_m:.3f} m",
            "area_m2": 2 * depth_m * height_m,
        },
    ]
    if int(faces) >= 2:
        surfaces.append({
            "name": "Back panel",
            "formula": f"{length_m:.3f} m x {height_m:.3f} m",
            "area_m2": length_m * height_m,
        })
    return surfaces


def _stage_surfaces(length_m, height_m, depth_m, faces):
    """A raised stage/platform: walkable deck plus the fascia skirt around its perimeter."""
    perimeter = 2 * (length_m + depth_m)
    return [
        {
            "name": "Deck",
            "formula": f"{length_m:.3f} m x {depth_m:.3f} m",
            "area_m2": length_m * depth_m,
        },
        {
            "name": "Perimeter fascia",
            "formula": f"{perimeter:.3f} m perimeter x {height_m:.3f} m",
            "area_m2": perimeter * height_m,
        },
    ]


def _arch_surfaces(length_m, height_m, depth_m, faces):
    """A portal arch: two legs plus a header, clad on both faces, with a soffit wrap.

    `depth_m` is the visible band width on the face; the soffit is the strip running
    through the opening, taken at the same width.
    """
    run_m = (2 * height_m) + length_m  # up one leg, across the header, down the other
    band_w = depth_m if depth_m > 0 else 0.30
    face_count = max(1, int(faces))
    surfaces = [{
        "name": f"Arch band face {i + 1}",
        "formula": f"{run_m:.3f} m run x {band_w:.3f} m band",
        "area_m2": run_m * band_w,
    } for i in range(face_count)]
    surfaces.append({
        "name": "Soffit / inner wrap",
        "formula": f"{run_m:.3f} m run x {band_w:.3f} m depth",
        "area_m2": run_m * band_w,
    })
    return surfaces


def _ring_surfaces(length_m, height_m, depth_m, faces, geometry=None):
    """A circular or annular shelf: the ring itself, per shelf, plus its edge.

    A ring is the one shape here that is not a bent rectangle, so it does not reuse the
    length/height model at all. `faces` counts shelves — a display tower is one ring
    repeated up a post, and the drawing dimensions the ring once.
    """
    geometry = geometry or {}
    outer_r = float(geometry.get("outer_r_m") or 0.0)
    inner_r = float(geometry.get("inner_r_m") or 0.0)
    if outer_r <= 0:
        return []

    shelves = max(1, int(faces or 1))
    area = curves.annulus_area(outer_r, inner_r)
    formula = (f"pi x ({outer_r:.3f}^2 - {inner_r:.3f}^2) m2"
               if inner_r > 0 else f"pi x {outer_r:.3f}^2 m2")

    return [{
        "name": f"Shelf ring {i + 1}",
        "formula": formula,
        "area_m2": area,
    } for i in range(shelves)]


# The shapes an element can take. `flat` reproduces the original rectilinear behaviour
# exactly, so an existing quotation re-priced today gives the same number it gave before.
SHAPES = {
    "flat":   {"label": "Flat", "hint": "Straight panel or square-headed portal."},
    "curved": {"label": "Curved", "hint": "Bent on plan or elevation — priced on arc length."},
    "ring":   {"label": "Ring / disc shelf", "hint": "Circular shelf, priced on annular area."},
    "arch":   {"label": "Arched head", "hint": "Portal whose head follows an arc."},
}
DEFAULT_SHAPE = "flat"

# Dimensions a shape needs beyond its item type's usual ones, and what to call them.
SHAPE_DIMS = {
    "curved": ("sagitta_m",),
    "arch":   (),
    "ring":   ("outer_r_m",),
    "flat":   (),
}
_SHAPE_DIM_LABELS = {
    "sagitta_m": "Curve rise",
    "outer_r_m": "Outer radius",
    "inner_r_m": "Inner radius",
    "radius_m": "Radius",
}


def shape_of(spec):
    """The spec's shape, defaulting to flat and never returning an unknown value."""
    shape = (spec.get("shape") or DEFAULT_SHAPE)
    return shape if shape in SHAPES else DEFAULT_SHAPE


def geometry_of(spec):
    """The curve parameters carried on a spec, normalised to floats."""
    return {
        "sagitta_m": max(0.0, float(spec.get("sagitta_m") or 0.0)),
        "radius_m": max(0.0, float(spec.get("radius_m") or 0.0)),
        "included_angle_deg": max(0.0, float(spec.get("included_angle_deg") or 0.0)),
        "outer_r_m": max(0.0, float(spec.get("outer_r_m") or 0.0)),
        "inner_r_m": max(0.0, float(spec.get("inner_r_m") or 0.0)),
    }


def developed_run_m(spec, settings=None):
    """The length of material actually wrapped along the item.

    For a flat item this is simply its length, which is why every existing quotation
    re-prices unchanged. For a curve it is the arc length: a 3 m chord bowed 0.4 m develops
    to about 3.28 m of cladding, and quoting the chord loses that 9% on every curved run of
    the stand.
    """
    length_m = max(0.0, float(spec.get("length_m") or 0.0))
    shape = shape_of(spec)
    if shape == "flat" or length_m <= 0:
        return length_m

    geometry = geometry_of(spec)
    settings = settings or shop_config.load()[0]
    min_angle = float(settings.get("min_curve_angle_deg") or curves.MIN_CURVE_ANGLE_DEG)

    if shape == "arch":
        return length_m        # the arch builder develops its own run over the head

    radius = geometry["radius_m"]
    sagitta = geometry["sagitta_m"]
    if sagitta > 0:
        angle = curves.included_angle_deg(length_m, curves.radius_from_chord_and_sagitta(
            length_m, sagitta), sagitta)
        if angle < min_angle:
            return length_m
        return curves.arc_length_from_chord(length_m, sagitta)
    if radius > 0 and geometry["included_angle_deg"] > 0:
        if geometry["included_angle_deg"] < min_angle:
            return length_m
        return curves.arc_length(radius, geometry["included_angle_deg"])
    return length_m


ITEM_TYPES = {
    "wall":    {"label": "Feature Wall",  "surfaces": _wall_surfaces,    "carpentry_hr_m2": 0.45},
    "counter": {"label": "Kiosk Counter", "surfaces": _counter_surfaces, "carpentry_hr_m2": 0.85},
    "stage":   {"label": "Stage / Riser", "surfaces": _stage_surfaces,   "carpentry_hr_m2": 0.55},
    "arch":    {"label": "Main Arch",     "surfaces": _arch_surfaces,    "carpentry_hr_m2": 0.95},
}
DEFAULT_ITEM_TYPE = "wall"

# Sensible fallbacks when a drawing gives a plan dimension but no depth.
DEFAULT_DEPTH_M = {"wall": 0.20, "counter": 0.60, "stage": 3.00, "arch": 0.30}

# The dimensions each item type needs a real (>0) value for before it can be priced at all.
# Depth is required for counter and stage, and excluded for wall and arch. The split is not
# arbitrary: on a wall or an arch, depth is construction thickness, so DEFAULT_DEPTH_M is a
# fair stand-in that barely moves the number. On a counter it is the worktop and both end
# panels — roughly 45% of the clad area — and on a stage it is half the deck, so defaulting
# it (0.60 m and 3.00 m respectively) can understate a real item by a third or more.
#
# compute_item_boq enforces this list, not just a zero-area check. Both failure modes have
# to be caught: an item with no face at all prices at 0.00, but an item missing only its
# depth still has a face and prices at a confident, plausible, understated figure. The
# second is the one that reaches a client, because 0.00 gets questioned and 1,092.91 does not.
REQUIRED_DIMS = {
    "wall": ("length_m", "height_m"),
    "counter": ("length_m", "height_m", "depth_m"),
    "stage": ("length_m", "depth_m"),
    "arch": ("length_m", "height_m"),
}
_DIM_LABELS = {
    "length_m": "Length", "height_m": "Height", "depth_m": "Depth",
    "sagitta_m": "Curve rise", "outer_r_m": "Outer radius", "inner_r_m": "Inner radius",
    "radius_m": "Radius",
}


# --- Finish systems -------------------------------------------------------------------
# Finishes are no longer a table of rate-card codes. A finish is a *method* — which roles
# it needs and how many coats — and its actual products are resolved from the sheet in
# `materials.py`. This module keeps only the default and a reference to the bundles.
FINISH_BUNDLES = materials_module.FINISH_BUNDLES
DEFAULT_FINISH = materials_module.DEFAULT_FINISH

# Last-resort fallbacks, used only when the sheet cannot fill a role — which, with the
# shipped rate card, never happens. They are not a catalogue: the material a shape uses is
# decided by scoring the sheet (see materials.py), not by these names.
DEFAULT_SUBSTRATE = "WD-MDF-18"
DEFAULT_FRAMING = "WD-FRM-2X2"


# --- Primitive calculations -----------------------------------------------------------

def net_surface_area(spec):
    """Gross clad area from the item's own geometry, minus every cutout.

    Returns (surfaces, gross_m2, cutout_m2, net_m2). Net is floored at zero so a drawing
    with over-declared cutouts produces a zero-area item rather than a negative cost.
    """
    item_type = spec.get("item_type", DEFAULT_ITEM_TYPE)
    if item_type not in ITEM_TYPES:
        item_type = DEFAULT_ITEM_TYPE

    length_m = max(0.0, float(spec.get("length_m") or 0.0))
    height_m = max(0.0, float(spec.get("height_m") or 0.0))
    depth_m = float(spec.get("depth_m") or 0.0)
    if depth_m <= 0:
        depth_m = DEFAULT_DEPTH_M.get(item_type, 0.20)
    faces = spec.get("faces", 1)
    shape = shape_of(spec)
    geometry = geometry_of(spec)

    if shape == "ring":
        # A ring ignores length/height entirely — its size is its radii.
        surfaces = _ring_surfaces(length_m, height_m, depth_m, faces, geometry)
    elif shape == "arch":
        # The band runs up the legs and over the arc, not around a rectangle. Feed the
        # developed run in as the "length" so the item type's own builder still decides
        # which faces exist and how many are clad.
        run_m = curves.arch_band_run(
            length_m, height_m, geometry["sagitta_m"], geometry["radius_m"])
        surfaces = ITEM_TYPES[item_type]["surfaces"](run_m, height_m, depth_m, faces)
    else:
        # Flat passes its own length straight through; curved substitutes arc length, so
        # every face the builder makes is sized on developed material rather than chord.
        run_m = developed_run_m(spec)
        surfaces = ITEM_TYPES[item_type]["surfaces"](run_m, height_m, depth_m, faces)

    gross_m2 = sum(s["area_m2"] for s in surfaces)

    cutout_m2 = 0.0
    for cutout in spec.get("cutouts") or []:
        width = max(0.0, float(cutout.get("width_m") or 0.0))
        height = max(0.0, float(cutout.get("height_m") or 0.0))
        count = max(1, int(cutout.get("count") or 1))
        cutout_m2 += width * height * count

    cutout_m2 = min(cutout_m2, gross_m2)
    return surfaces, gross_m2, cutout_m2, max(0.0, gross_m2 - cutout_m2)


def sheets_required(area_m2, wastage=WASTAGE_FACTOR):
    """m2 -> whole 8x4 sheets, with wastage applied before rounding up."""
    if area_m2 <= 0:
        return 0, 0.0
    with_wastage = area_m2 * (1.0 + wastage)
    return int(math.ceil(with_wastage / SHEET_AREA_M2)), with_wastage


def stud_linear_meters(spec, settings=None):
    """Framing skeleton: perimeter plates plus a vertical every STUD_SPACING_M.

    Returns (total_linear_m, breakdown_dict).

    Two things change on a curve. The runs follow the arc rather than the chord, and the
    formers sit closer together — a curve framed at flat centres reads as a series of flat
    facets once it is skinned. Both come from the developed run and the configured curved
    spacing, so a shop that frames curves differently changes one setting, not this code.
    """
    item_type = spec.get("item_type", DEFAULT_ITEM_TYPE)
    shape = shape_of(spec)
    height_m = max(0.0, float(spec.get("height_m") or 0.0))
    depth_m = float(spec.get("depth_m") or 0.0)
    if depth_m <= 0:
        depth_m = DEFAULT_DEPTH_M.get(item_type, 0.20)

    settings = settings or shop_config.load()[0]

    if shape == "ring":
        # A ring shelf is cut sheet on a support structure the drawing has not described.
        # Framing it as a stud wall would invent a carcass that is not there; the UI says
        # so and lets the PM add the real support as its own item.
        return 0.0, {"perimeter_m": 0.0, "vertical_count": 0, "vertical_m": 0.0,
                     "legs_m": 0.0, "spacing_m": 0.0, "run_m": 0.0}

    # Curved and arched items frame along developed length, not chord.
    if shape == "arch":
        geometry = geometry_of(spec)
        length_m = curves.arch_band_run(
            max(0.0, float(spec.get("length_m") or 0.0)),
            height_m, geometry["sagitta_m"], geometry["radius_m"])
    else:
        length_m = developed_run_m(spec, settings)

    spacing_m = STUD_SPACING_M
    if curves.is_bent(shape):
        # Only a bent skin needs formers at closer centres; a flat part that happens to be
        # round is framed, if at all, like any other flat part.
        spacing_m = float(settings.get("curved_stud_spacing_m") or STUD_SPACING_M)
    spacing_m = max(0.05, spacing_m)

    if item_type == "stage":
        # A deck is framed on plan, not in elevation: joists run across the short span.
        perimeter_m = 2 * (length_m + depth_m)
        vertical_count = int(math.floor(length_m / spacing_m)) + 1
        vertical_m = vertical_count * depth_m
        legs_m = vertical_count * height_m
        total = perimeter_m + vertical_m + legs_m
        return total, {
            "perimeter_m": perimeter_m,
            "vertical_count": vertical_count,
            "vertical_m": vertical_m,
            "legs_m": legs_m,
            "spacing_m": spacing_m,
            "run_m": length_m,
        }

    perimeter_m = 2 * (length_m + height_m)
    vertical_count = int(math.floor(length_m / spacing_m)) + 1
    vertical_m = vertical_count * height_m
    total = perimeter_m + vertical_m
    return total, {
        "perimeter_m": perimeter_m,
        "vertical_count": vertical_count,
        "vertical_m": vertical_m,
        "legs_m": 0.0,
        "spacing_m": spacing_m,
        "run_m": length_m,
    }


def paint_liters(area_m2, coverage_m2_per_l, coats):
    """Litres of wet product needed to put `coats` over `area_m2`."""
    if area_m2 <= 0 or coverage_m2_per_l <= 0:
        return 0.0
    return (area_m2 * max(1, int(coats))) / coverage_m2_per_l


# --- Material resolution from the sheet ------------------------------------------------

def _pick(card, query, override_code, role):
    """One resolved material for a role: a PM override if given, else the sheet's best match.

    Returns a dict carrying the code, the reason it was chosen, and whether the PM overrode
    it — everything the UI needs to show *why* a material is on the bill and let it be
    changed. Returns None only when the sheet has nothing suitable and the PM gave no code,
    which the caller turns into a "needs material" message rather than a silent substitution.
    """
    override_code = (override_code or "").strip()
    if override_code and card.has(override_code):
        item = card.get(override_code)
        return {"role": role, "code": item.code, "description": item.description,
                "unit": item.unit, "cost": item.avg_cost, "reason": "chosen by you",
                "keyword": None, "overridden": True}

    resolved = materials_module.resolve(card, query)
    if resolved is None:
        return None
    resolved = dict(resolved)
    resolved.update({"role": role, "overridden": False})
    return resolved


def resolve_build_materials(card, spec, shape_key, settings):
    """Substrate, framing, fixings, brackets and adhesive for a shape, from the sheet.

    Returns (chosen, problems). `chosen` maps role -> resolved dict (or None). `problems`
    lists the required roles the sheet could not fill, in plain language, so the item can
    refuse to price rather than inventing a material.
    """
    definition = shapes_module.SHAPES.get(shape_key, shapes_module.SHAPES[shapes_module.DEFAULT_SHAPE])
    chosen, problems = {}, []

    chosen["substrate"] = _pick(
        card, materials_module.substrate_query(shape_key), spec.get("substrate"), "substrate")
    if chosen["substrate"] is None:
        problems.append("No board on the sheet suits this shape — add one or pick a substrate.")

    framing_weight = definition.get("framing")
    if framing_weight:
        chosen["framing"] = _pick(
            card, materials_module.FRAMING_QUERIES[framing_weight], spec.get("framing"), "framing")
        if chosen["framing"] is None:
            problems.append("No framing timber on the sheet — add a stud row or pick framing.")
    else:
        chosen["framing"] = None

    for role in ("fixings", "brackets", "adhesive"):
        chosen[role] = _pick(card, materials_module.STANDARD_QUERIES[role], None, role)

    return chosen, problems


def _material_choice_summary(chosen):
    """The compact list the item card shows: what each role resolved to and why."""
    summary = []
    for role in ("substrate", "framing", "fixings", "brackets", "adhesive"):
        pick = chosen.get(role)
        if pick:
            summary.append({
                "role": role, "code": pick["code"], "description": pick["description"],
                "reason": pick["reason"], "overridden": pick.get("overridden", False),
            })
    return summary


# --- BOQ assembly ---------------------------------------------------------------------

def _line(card, code, qty, basis, category=None, override_cost=None):
    """Prices one material line against the rate card. qty is rounded up to whole
    purchase units — you cannot buy 0.4 of a sheet.

    `override_cost`, when given, is a PM-entered rate that wins over the card's price for
    this line only; `default_cost` is still carried so the UI can show what the card says
    and let the PM reset back to it.
    """
    item = card.get(code)
    whole_qty = int(math.ceil(qty - 1e-9)) if qty > 0 else 0
    unit_cost = item.avg_cost if override_cost is None else max(0.0, float(override_cost))
    return {
        "code": code,
        "description": item.description,
        "category": category or item.category,
        "unit": item.unit,
        "qty": whole_qty,
        "raw_qty": round(qty, 3),
        "unit_cost": unit_cost,
        "default_cost": item.avg_cost,
        "line_cost": round(whole_qty * unit_cost, 2),
        "basis": basis,
    }


def _apply_line_edits(materials, labor, spec, card, line_fn):
    """Applies the PM's edits to a computed bill: renames, quantities, deletions, additions.

    Keyed by `code` for materials and `trade` for labour, which is what the UI addresses a
    row by. An edited quantity replaces the derived one outright rather than scaling it —
    when a PM types 14 sheets they mean 14, not 14 times a wastage factor they cannot see.
    The original figure stays in `basis` so nothing is lost.
    """
    removed = set(spec.get("removed_lines") or [])
    edits = spec.get("line_overrides") or {}

    kept_materials = []
    for material in materials:
        if material["code"] in removed:
            continue
        edit = edits.get(material["code"]) or {}
        if edit.get("description"):
            material["description"] = str(edit["description"])
            material["edited"] = True
        if edit.get("qty") is not None:
            try:
                new_qty = max(0, int(float(edit["qty"])))
            except (TypeError, ValueError):
                new_qty = material["qty"]
            if new_qty != material["qty"]:
                material["basis"] = f"{material['basis']} — set to {new_qty} by you"
                material["qty"] = new_qty
                material["edited"] = True
        material["line_cost"] = round(material["qty"] * material["unit_cost"], 2)
        kept_materials.append(material)

    # Lines the drawing never implied: site works, a bought-in part, a delivery charge.
    for extra in spec.get("extra_lines") or []:
        try:
            qty = max(0, float(extra.get("qty") or 0))
            rate = max(0.0, float(extra.get("rate") or 0))
        except (TypeError, ValueError):
            continue
        code = str(extra.get("code") or "CUSTOM").strip() or "CUSTOM"
        kept_materials.append({
            "code": code,
            "description": str(extra.get("description") or "Custom line"),
            "category": "Added by you",
            "unit": str(extra.get("unit") or "Unit"),
            "qty": int(qty),
            "raw_qty": qty,
            "unit_cost": rate,
            "default_cost": rate,
            "line_cost": round(int(qty) * rate, 2),
            "basis": "added by you",
            "edited": True,
            "custom": True,
        })

    kept_labor = []
    for entry in labor:
        if entry["trade"] in removed:
            continue
        edit = edits.get(entry["trade"]) or {}
        if edit.get("description"):
            entry["label"] = str(edit["description"])
            entry["edited"] = True
        if edit.get("qty") is not None:
            try:
                entry["hours"] = round(max(0.0, float(edit["qty"])), 2)
                entry["basis"] = f"{entry['basis']} — set to {entry['hours']} hr by you"
                entry["edited"] = True
            except (TypeError, ValueError):
                pass
        entry["cost"] = round(entry["hours"] * entry["rate"], 2)
        kept_labor.append(entry)

    return kept_materials, kept_labor


def missing_required_dims(item_type, spec):
    """The required dimension fields this spec has not supplied a positive value for.

    A missing dimension is not the same as a zero-area item. A counter with a length and a
    height but no depth still has one clad face, so it prices — at a number that looks
    entirely reasonable while silently omitting the top and both returns. That is more
    dangerous than a visible 0.00, because nothing about the figure invites a second look.
    """
    shape = shape_of(spec)

    if shape == "ring":
        # A ring is defined by its radii; its length and height are meaningless. Requiring
        # the item type's usual fields here would block a perfectly well-described shelf.
        return [f for f in ("outer_r_m",) if float(spec.get(f) or 0.0) <= 0]

    required = list(REQUIRED_DIMS.get(item_type, REQUIRED_DIMS[DEFAULT_ITEM_TYPE]))

    # A curve with no stated rise develops to exactly its chord, which prices it as a flat
    # panel — the quiet under-quote this whole feature exists to stop. Ask for the rise
    # rather than accept a number that looks right and is not.
    if shape == "curved":
        required.append("sagitta_m")

    return [f for f in required if float(spec.get(f) or 0.0) <= 0]


def dimension_message(item_type, spec):
    """Names the specific fields still needed before an item type has any clad area."""
    missing = [_DIM_LABELS[f] for f in missing_required_dims(item_type, spec)]
    label = ITEM_TYPES.get(item_type, ITEM_TYPES[DEFAULT_ITEM_TYPE])["label"]
    if not missing:
        return f"Enter dimensions to price this {label}."
    return f"Enter {' and '.join(missing)} to price this {label} — drawing gave no usable value."


def compute_item_boq(spec, card=None):
    """Full deterministic BOQ for one detected item.

    `spec` keys: item_type, label, length_m, height_m, depth_m, faces, cutouts[],
    substrate, framing, finish, quantity, plus optional lighting flags.
    """
    card = card or rate_card_module.get_rate_card()

    # Accept both the new merged shape (e.g. "wall_curved") and the legacy item_type+shape
    # pair, and reduce them to the vocabulary the geometry below already understands.
    spec = shapes_module.normalize(spec)
    shape_key = spec["shape_key"]

    item_type = spec.get("item_type", DEFAULT_ITEM_TYPE)
    if item_type not in ITEM_TYPES:
        item_type = DEFAULT_ITEM_TYPE
    type_meta = ITEM_TYPES[item_type]

    settings, settings_problems = shop_config.load()
    shape = shape_of(spec)
    geometry = geometry_of(spec)
    curved = curves.is_curved(shape)

    quantity = max(1, int(spec.get("quantity") or 1))

    # Materials come from the sheet. The shape declares which roles it needs; each is filled
    # by scoring the rate card's own Category and Usage columns (materials.py). A PM override
    # on any role still wins; this only fills the blanks, and never invents a code.
    chosen, material_problems = resolve_build_materials(card, spec, shape_key, settings)
    settings_problems.extend(material_problems)

    substrate_pick = chosen.get("substrate")
    substrate = substrate_pick["code"] if substrate_pick else DEFAULT_SUBSTRATE
    framing_pick = chosen.get("framing")
    framing = framing_pick["code"] if framing_pick else None

    # A bent skin is built from several thin layers laminated over the frame — a build
    # method, not a different board — so the layer count is a setting while the sheet still
    # chooses the board. A PM who named a board explicitly gets exactly that, one layer.
    skin_layers = 1
    substrate_note = ""
    if curves.is_bent(shape) and not (substrate_pick and substrate_pick.get("overridden")):
        skin_layers = max(1, int(settings.get("curved_skin_layers") or 1))
        if skin_layers > 1:
            substrate_note = f"curved build-up: {skin_layers} x flexible skin ({substrate})"

    finish_key = spec.get("finish") or DEFAULT_FINISH
    if finish_key not in FINISH_BUNDLES:
        finish_key = DEFAULT_FINISH
    finish = FINISH_BUNDLES[finish_key]

    rate_overrides = spec.get("rate_overrides") or {}
    labor_rate_overrides = spec.get("labor_rate_overrides") or {}

    def line(code, qty, basis, category=None):
        return _line(card, code, qty, basis, category, rate_overrides.get(code))

    def labor_rate(trade):
        if trade in labor_rate_overrides:
            return max(0.0, float(labor_rate_overrides[trade]))
        return card.labor_rate(trade)

    surfaces, gross_m2, cutout_m2, net_m2 = net_surface_area(spec)

    # No clad face means nothing to build: pricing framing/hardware off a degenerate
    # rectangle (e.g. a length with no height) produces a cost for zero actual material,
    # which reads as a real number but is not one. Stop here and ask for the dimension
    # instead of guessing — the PM enters it in the same fields, this just refuses to
    # fabricate a number until they do.
    #
    # The area test alone is not enough. It catches the item that prices at 0.00, but not
    # the one whose *partial* dimensions still form a face: a counter with no depth, a
    # stage with no depth, an arch with no height. Those return a confident, plausible,
    # under-stated figure — the failure mode that actually reaches a client, since a
    # visible 0.00 gets questioned and AED 1,092.91 does not. REQUIRED_DIMS already states
    # what each type needs, so hold every item to it.
    needs_dims = gross_m2 <= 0 or bool(missing_required_dims(item_type, spec))
    needs_materials = bool(material_problems)
    if needs_dims or needs_materials:
        # Prefer the dimension message — a PM fixes a missing size far more often than a
        # missing material — but surface the material gap when that is the only blocker.
        message = (dimension_message(item_type, spec) if needs_dims
                   else " ".join(material_problems))
        return {
            "label": spec.get("label") or type_meta["label"],
            "item_type": item_type,
            "item_type_label": type_meta["label"],
            "quantity": quantity,
            "dimensions": {
                "length_m": round(float(spec.get("length_m") or 0.0), 3),
                "height_m": round(float(spec.get("height_m") or 0.0), 3),
                "depth_m": round(float(spec.get("depth_m") or 0.0), 3),
                "faces": int(spec.get("faces") or 1),
            },
            "shape": shape,
            "shape_key": shape_key,
            "shape_label": SHAPES[shape]["label"],
            "shape_summary": curves.describe(shape, geometry),
            "geometry": {k: round(v, 3) for k, v in geometry.items()},
            "developed_run_m": 0.0,
            "settings_problems": settings_problems,
            "substrate": substrate,
            "framing": framing,
            "finish": finish_key,
            "finish_label": finish["label"],
            "materials_chosen": _material_choice_summary(chosen),
            "surfaces": [],
            "gross_area_m2": 0.0,
            "cutout_area_m2": 0.0,
            "net_area_m2": 0.0,
            "cutouts": spec.get("cutouts") or [],
            "materials": [],
            "labor": [],
            "unit_material_cost": 0.0,
            "unit_labor_cost": 0.0,
            "unit_labor_hours": 0.0,
            "unit_factory_cost": 0.0,
            "material_cost": 0.0,
            "labor_cost": 0.0,
            "labor_hours": 0.0,
            "factory_cost": 0.0,
            "needs_dimensions": needs_dims,
            "needs_materials": needs_materials,
            "dimension_message": message,
            "source": spec.get("source") or {},
        }

    materials = []

    # --- Substrate boards -------------------------------------------------------
    # Circles nest badly. Cutting rings out of an 8x4 sheet throws away far more than the
    # 10% that trimming a rectangular panel does, so a ring carries its own wastage figure
    # and the basis string names it rather than hiding it inside the standard rate.
    board_wastage = WASTAGE_FACTOR
    if shape == "ring":
        board_wastage = float(settings.get("ring_wastage_factor") or WASTAGE_FACTOR)

    skin_area_m2 = net_m2 * skin_layers
    sheet_count, area_with_wastage = sheets_required(skin_area_m2, board_wastage)
    if sheet_count:
        basis = f"{net_m2:.2f} m2 net"
        if skin_layers > 1:
            basis += f" x {skin_layers} skins = {skin_area_m2:.2f} m2"
        basis += (
            f" x {1 + board_wastage:.2f} wastage = {area_with_wastage:.2f} m2 "
            f"/ {SHEET_AREA_M2} m2 per sheet -> {sheet_count} sheets"
        )
        if shape == "ring":
            basis += f" (ring cutting wastage {board_wastage * 100:.0f}%)"
        materials.append(line(substrate, sheet_count, basis))

    # --- Framing ----------------------------------------------------------------
    linear_m, framing_detail = stud_linear_meters(spec, settings)
    stud_pieces = 0
    if linear_m > 0 and framing:
        linear_with_wastage = linear_m * (1.0 + WASTAGE_FACTOR)
        stud_pieces = int(math.ceil(linear_with_wastage / STUD_PIECE_LEN_M))
        basis = (
            f"perimeter {framing_detail['perimeter_m']:.2f} m + "
            f"{framing_detail['vertical_count']} verticals @ "
            f"{framing_detail.get('spacing_m', STUD_SPACING_M):g} m centres "
            f"({framing_detail['vertical_m']:.2f} m)"
        )
        if curved:
            basis = (f"developed run {framing_detail.get('run_m', 0.0):.2f} m — " + basis)
        if framing_detail.get("legs_m"):
            basis += f" + legs {framing_detail['legs_m']:.2f} m"
        basis += (
            f" = {linear_m:.2f} m x {1 + WASTAGE_FACTOR:.2f} "
            f"/ {STUD_PIECE_LEN_M} m per piece -> {stud_pieces} pieces"
        )
        materials.append(line(framing, stud_pieces, basis))

    # --- Ring edging --------------------------------------------------------------
    # Edging a disc is the slow, material-hungry part of making one, and it scales with
    # circumference rather than area. Only billed when the PM has named a banding product:
    # with no code configured this stays off the quote entirely rather than guessing one.
    if shape == "ring":
        banding_code = str(settings.get("ring_edge_banding_code") or "").strip()
        if banding_code and card.has(banding_code):
            shelves = max(1, int(spec.get("faces") or 1))
            edge_m = curves.annulus_edge_length(
                geometry["outer_r_m"], geometry["inner_r_m"]) * shelves
            if edge_m > 0:
                materials.append(line(
                    banding_code, edge_m,
                    f"{shelves} x ring edge "
                    f"{curves.annulus_edge_length(geometry['outer_r_m'], geometry['inner_r_m']):.2f} m "
                    f"= {edge_m:.2f} m",
                ))

    # --- Finish system ----------------------------------------------------------
    # The finish names roles; the products resolve from the sheet. A role the sheet cannot
    # fill is skipped with a note rather than blocking the whole item — a missing thinner
    # should not stop a wall being quoted, unlike a missing structural board.
    finish_reasons = []
    for component in finish.get("components", []):
        role = component["role"]
        pick = materials_module.resolve(card, materials_module.FINISH_QUERIES[role])
        if pick is None or not card.has(pick["code"]):
            settings_problems.append(
                f"No material on the sheet for the {role} in {finish['label']} — "
                f"that part of the finish is not costed.")
            continue
        code = pick["code"]
        finish_reasons.append({"role": role, "code": code, "reason": pick["reason"]})

        if "coverage_m2_per_l" in component:
            litres = paint_liters(net_m2, component["coverage_m2_per_l"], component["coats"])
            unit_size = component.get("unit_size", 1.0)
            units = litres / unit_size if unit_size else litres
            if units > 0:
                materials.append(line(
                    code, units,
                    f"{net_m2:.2f} m2 x {component['coats']} coats "
                    f"/ {component['coverage_m2_per_l']} m2 per L = {litres:.2f} L "
                    f"/ {unit_size:g} L per unit -> {math.ceil(units)}",
                ))
        elif component.get("drives") == "area":
            if (pick["unit"] or "").lower() == "sheet":
                count, with_waste = sheets_required(net_m2)
                if count:
                    materials.append(line(
                        code, count,
                        f"{net_m2:.2f} m2 x {1 + WASTAGE_FACTOR:.2f} = {with_waste:.2f} m2 "
                        f"/ {SHEET_AREA_M2} m2 per sheet -> {count} sheets",
                    ))
            else:
                qty = net_m2 * (1.0 + WASTAGE_FACTOR)
                if qty > 0:
                    materials.append(line(
                        code, qty,
                        f"{net_m2:.2f} m2 x {1 + WASTAGE_FACTOR:.2f} wastage = {qty:.2f} m2",
                    ))
        elif "m2_per_unit" in component:
            per_unit = component.get("m2_per_unit", 1.0)
            units = net_m2 / per_unit if per_unit else 0.0
            if units > 0:
                materials.append(line(
                    code, units,
                    f"{net_m2:.2f} m2 / {per_unit:g} m2 per unit -> {math.ceil(units)}",
                ))

    # --- Fixings and consumables -------------------------------------------------
    # Codes resolve from the sheet like everything else, so a shop that stocks a different
    # screw or glue changes the sheet, not this file.
    fixings_code = (chosen.get("fixings") or {}).get("code")
    brackets_code = (chosen.get("brackets") or {}).get("code")
    adhesive_code = (chosen.get("adhesive") or {}).get("code")

    if stud_pieces:
        joints = stud_pieces * SCREWS_PER_STUD_JOINT
        boxes = joints / SCREWS_PER_BOX
        if boxes > 0 and fixings_code and card.has(fixings_code):
            materials.append(line(
                fixings_code, boxes,
                f"{stud_pieces} stud pieces x {SCREWS_PER_STUD_JOINT} screws = {joints} "
                f"/ {SCREWS_PER_BOX} per box -> {math.ceil(boxes)}",
            ))
        brackets = stud_pieces * BRACKETS_PER_STUD_PIECE
        if brackets_code and card.has(brackets_code):
            materials.append(line(
                brackets_code, brackets,
                f"{stud_pieces} stud pieces x {BRACKETS_PER_STUD_PIECE} brackets -> {brackets}",
            ))

    if net_m2 > 0 and adhesive_code and card.has(adhesive_code):
        cans = net_m2 / WOOD_GLUE_M2_PER_CAN
        if cans > 0:
            materials.append(line(
                adhesive_code, cans,
                f"{net_m2:.2f} m2 / {WOOD_GLUE_M2_PER_CAN:g} m2 per can -> {math.ceil(cans)}",
            ))

    # --- Optional LED lighting ----------------------------------------------------
    if spec.get("led_meters"):
        led_m = float(spec["led_meters"])
        rolls = led_m / 5.0
        if rolls > 0:
            materials.append(line(
                "EL-LED-12W", rolls,
                f"{led_m:.2f} m LED / 5 m per roll -> {math.ceil(rolls)}",
            ))
            drivers = math.ceil((led_m * 12.0) / 200.0)  # ~12W/m against a 200W driver
            materials.append(line(
                "EL-TRN-200", drivers,
                f"{led_m:.2f} m x 12 W/m = {led_m * 12:.0f} W / 200 W per driver -> {drivers}",
            ))

    # --- Labor ---------------------------------------------------------------------
    labor = []

    # Curved work is slower per square metre than flat: formers to set out, skins to
    # laminate, more fettling. The factor is a shop setting, and it appears as its own term
    # in the basis string so a PM can see exactly what the curve cost them.
    curve_factor = 1.0
    if curved:
        curve_factor = max(1.0, float(settings.get("curve_labour_factor") or 1.0))

    carpentry_hours = net_m2 * type_meta["carpentry_hr_m2"] * curve_factor
    if carpentry_hours > 0:
        rate = labor_rate("carpentry")
        basis = f"{net_m2:.2f} m2 x {type_meta['carpentry_hr_m2']} hr/m2 ({type_meta['label']})"
        if curve_factor > 1.0:
            basis += f" x {curve_factor:g} curved-work factor"
        labor.append({
            "trade": "carpentry",
            "hours": round(carpentry_hours, 2),
            "rate": rate,
            "cost": round(carpentry_hours * rate, 2),
            "basis": basis,
        })

    painting_hr_m2 = finish.get("painting_hr_m2", 0.0)
    if painting_hr_m2 > 0 and net_m2 > 0:
        hours = net_m2 * painting_hr_m2
        rate = labor_rate("painting")
        labor.append({
            "trade": "painting",
            "hours": round(hours, 2),
            "rate": rate,
            "cost": round(hours * rate, 2),
            "basis": f"{net_m2:.2f} m2 x {painting_hr_m2} hr/m2 ({finish['label']})",
        })

    finishing_hr_m2 = finish.get("finishing_hr_m2", 0.0)
    if finishing_hr_m2 > 0 and net_m2 > 0:
        hours = net_m2 * finishing_hr_m2
        rate = labor_rate("finishing")
        labor.append({
            "trade": "finishing",
            "hours": round(hours, 2),
            "rate": rate,
            "cost": round(hours * rate, 2),
            "basis": f"{net_m2:.2f} m2 x {finishing_hr_m2} hr/m2 ({finish['label']})",
        })

    if stud_pieces:
        assembly_hours = stud_pieces * 0.25
        rate = labor_rate("assembly")
        labor.append({
            "trade": "assembly",
            "hours": round(assembly_hours, 2),
            "rate": rate,
            "cost": round(assembly_hours * rate, 2),
            "basis": f"{stud_pieces} stud pieces x 0.25 hr each",
        })

    if spec.get("led_meters"):
        elec_hours = float(spec["led_meters"]) * 0.15
        rate = labor_rate("electrical")
        labor.append({
            "trade": "electrical",
            "hours": round(elec_hours, 2),
            "rate": rate,
            "cost": round(elec_hours * rate, 2),
            "basis": f"{float(spec['led_meters']):.2f} m LED x 0.15 hr/m",
        })

    # --- PM edits to the bill ---------------------------------------------------------
    # Everything above is derived from geometry and the rate card. This is where the PM's
    # own corrections land: a renamed line, a quantity they know better than the formula, a
    # line deleted because it is already on site, or one added that no drawing implied.
    # Applied last so an edit always wins over the calculation, and recorded on the line so
    # the UI can show which figures are no longer the computed ones.
    materials, labor = _apply_line_edits(materials, labor, spec, card, line)

    # --- Roll up (single unit, then multiplied by quantity) --------------------------
    unit_material_cost = round(sum(m["line_cost"] for m in materials), 2)
    unit_labor_cost = round(sum(l["cost"] for l in labor), 2)
    unit_labor_hours = round(sum(l["hours"] for l in labor), 2)

    return {
        "label": spec.get("label") or type_meta["label"],
        "item_type": item_type,
        "item_type_label": type_meta["label"],
        "quantity": quantity,
        "dimensions": {
            "length_m": round(float(spec.get("length_m") or 0.0), 3),
            "height_m": round(float(spec.get("height_m") or 0.0), 3),
            "depth_m": round(float(spec.get("depth_m") or DEFAULT_DEPTH_M.get(item_type, 0.2)), 3),
            "faces": int(spec.get("faces") or 1),
        },
        "shape": shape,
        "shape_key": shape_key,
        "shape_label": SHAPES[shape]["label"],
        "shape_summary": curves.describe(shape, geometry),
        "geometry": {k: round(v, 3) for k, v in geometry.items()},
        # The developed run is the single number that explains why a curve costs more than
        # its drawn width, so it is reported rather than left buried in the surface list.
        "developed_run_m": round(developed_run_m(spec, settings), 3),
        "curve_labour_factor": round(curve_factor, 3),
        "skin_layers": skin_layers,
        "substrate_note": substrate_note,
        "settings_problems": settings_problems,
        "substrate": substrate,
        "framing": framing,
        "finish": finish_key,
        "finish_label": finish["label"],
        # Which material filled each role and why — the item card shows this instead of a
        # substrate/framing dropdown, so the choice is visible without being editable up front.
        "materials_chosen": _material_choice_summary(chosen),
        "finish_reasons": finish_reasons,
        "needs_materials": False,
        "surfaces": [
            {"name": s["name"], "formula": s["formula"], "area_m2": round(s["area_m2"], 3)}
            for s in surfaces
        ],
        "gross_area_m2": round(gross_m2, 3),
        "cutout_area_m2": round(cutout_m2, 3),
        "net_area_m2": round(net_m2, 3),
        "cutouts": spec.get("cutouts") or [],
        "materials": materials,
        "labor": labor,
        "unit_material_cost": unit_material_cost,
        "unit_labor_cost": unit_labor_cost,
        "unit_labor_hours": unit_labor_hours,
        "unit_factory_cost": round(unit_material_cost + unit_labor_cost, 2),
        "material_cost": round(unit_material_cost * quantity, 2),
        "labor_cost": round(unit_labor_cost * quantity, 2),
        "labor_hours": round(unit_labor_hours * quantity, 2),
        "factory_cost": round((unit_material_cost + unit_labor_cost) * quantity, 2),
        "needs_dimensions": False,
        "source": spec.get("source") or {},
    }


def aggregate(boq_items, margin_pct=None, card=None):
    """Master summary across every item from every uploaded drawing.

    Margin is a markup on factory cost: selling = factory x (1 + margin/100).
    """
    card = card or rate_card_module.get_rate_card()
    if margin_pct is None:
        margin_pct = card.margin_pct
    margin_pct = max(0.0, float(margin_pct))

    total_material = round(sum(i["material_cost"] for i in boq_items), 2)
    total_labor_cost = round(sum(i["labor_cost"] for i in boq_items), 2)
    total_labor_hours = round(sum(i["labor_hours"] for i in boq_items), 2)
    factory_cost = round(total_material + total_labor_cost, 2)
    margin_amount = round(factory_cost * (margin_pct / 100.0), 2)
    selling_price = round(factory_cost + margin_amount, 2)

    # Consolidated material take-off: the same code across different drawings becomes one
    # purchasing line, which is what the factory actually orders against.
    consolidated = {}
    for item in boq_items:
        multiplier = item.get("quantity", 1)
        for material in item["materials"]:
            entry = consolidated.setdefault(material["code"], {
                "code": material["code"],
                "description": material["description"],
                "category": material["category"],
                "unit": material["unit"],
                "unit_cost": material["unit_cost"],
                "qty": 0,
                "line_cost": 0.0,
            })
            entry["qty"] += material["qty"] * multiplier
            entry["line_cost"] = round(entry["qty"] * entry["unit_cost"], 2)

    labor_by_trade = {}
    for item in boq_items:
        multiplier = item.get("quantity", 1)
        for line in item["labor"]:
            entry = labor_by_trade.setdefault(line["trade"], {
                "trade": line["trade"], "hours": 0.0, "rate": line["rate"], "cost": 0.0,
            })
            entry["hours"] = round(entry["hours"] + line["hours"] * multiplier, 2)
            entry["cost"] = round(entry["cost"] + line["cost"] * multiplier, 2)

    return {
        "item_count": len(boq_items),
        "total_units": sum(i.get("quantity", 1) for i in boq_items),
        "total_net_area_m2": round(
            sum(i["net_area_m2"] * i.get("quantity", 1) for i in boq_items), 3
        ),
        "total_material_cost": total_material,
        "total_labor_hours": total_labor_hours,
        "total_labor_cost": total_labor_cost,
        "factory_cost": factory_cost,
        "margin_pct": margin_pct,
        "margin_amount": margin_amount,
        "selling_price": selling_price,
        "consolidated_materials": sorted(
            consolidated.values(), key=lambda m: (m["category"], m["code"])
        ),
        "labor_by_trade": sorted(labor_by_trade.values(), key=lambda l: l["trade"]),
    }


def options_payload(card=None):
    """Everything the UI needs to render the estimator, sourced from the card and the sheet.

    The old separate item-type and shape lists are gone: `shapes` is the single merged list
    the PM picks from. The substrate and framing lists remain for the Advanced override, but
    are now read from the sheet's own Wood & Boards rows rather than a hardcoded table, so a
    board added to the CSV appears in the override dropdown too.
    """
    card = card or rate_card_module.get_rate_card()

    boards = card.in_category("Wood & Boards")
    substrates = [{"code": i.code, "label": i.description, "cost": i.avg_cost}
                  for i in boards if (i.unit or "").lower() == "sheet"]
    framing = [{"code": i.code, "label": i.description, "cost": i.avg_cost}
               for i in boards if (i.unit or "").lower() == "piece"]

    return {
        "shapes": shapes_module.options_payload(),
        "fabrication": shop_config.describe(),
        "finishes": [
            {"key": key, "label": bundle["label"]}
            for key, bundle in FINISH_BUNDLES.items()
        ],
        "substrates": sorted(substrates, key=lambda s: s["code"]),
        "framing": sorted(framing, key=lambda s: s["code"]),
        "constants": {
            "sheet_area_m2": SHEET_AREA_M2,
            "wastage_factor": WASTAGE_FACTOR,
            "stud_spacing_m": STUD_SPACING_M,
            "stud_piece_len_m": STUD_PIECE_LEN_M,
        },
        "labor_rates": dict(card.labor_rates),
        "default_margin_pct": card.margin_pct,
    }


def to_quotation_items(boq_items, aggregate_result, mode="client"):
    """Converts BOQ output into the draft-item shape the existing compiler consumes.

    `client` yields one priced line per fabricated item at the marked-up selling rate,
    which is what the customer should see. `factory` explodes the consolidated material
    take-off plus labor, which is what production needs.
    """
    rows = []
    if mode == "factory":
        for material in aggregate_result["consolidated_materials"]:
            rows.append({
                "description": f"[{material['code']}] {material['description']}",
                "unit": material["unit"],
                "qty": material["qty"],
                "rate": material["unit_cost"],
                "image_base64": "",
                "image_source": "",
            })
        for line in aggregate_result["labor_by_trade"]:
            rows.append({
                "description": f"Labor - {line['trade'].title()}",
                "unit": "Hrs",
                "qty": line["hours"],
                "rate": line["rate"],
                "image_base64": "",
                "image_source": "",
            })
        return rows

    margin_multiplier = 1.0 + (aggregate_result["margin_pct"] / 100.0)
    for item in boq_items:
        unit_rate = round(item["unit_factory_cost"] * margin_multiplier, 2)
        descriptor = f"{item['label']} - {item['item_type_label']}"
        dims = item["dimensions"]
        if dims["length_m"] and dims["height_m"]:
            descriptor += f" ({dims['length_m']:g}m x {dims['height_m']:g}m"
            if dims["depth_m"]:
                descriptor += f" x {dims['depth_m']:g}m"
            descriptor += f", {item['finish_label']})"
        rows.append({
            "description": descriptor,
            "unit": "Nos",
            "qty": item.get("quantity", 1),
            "rate": unit_rate,
            "image_base64": (item.get("source") or {}).get("thumbnail", ""),
            "image_source": "design_estimator",
        })
    return rows


if __name__ == "__main__":
    card = rate_card_module.get_rate_card()
    demo = {
        "label": "Main Feature Wall",
        "item_type": "wall",
        "length_m": 6.0,
        "height_m": 3.0,
        "depth_m": 0.2,
        "faces": 1,
        "cutouts": [{"label": "Display niche", "width_m": 1.2, "height_m": 0.9, "count": 2}],
        "finish": "paint_pu",
        "quantity": 1,
    }
    result = compute_item_boq(demo, card)
    print(f"{result['label']}: net {result['net_area_m2']} m2 "
          f"(gross {result['gross_area_m2']} - cutouts {result['cutout_area_m2']})")
    for material in result["materials"]:
        print(f"  {material['code']:<12} {material['qty']:>4} {material['unit']:<8} "
              f"{material['line_cost']:>9,.2f}   {material['basis']}")
    for line in result["labor"]:
        print(f"  LABOR {line['trade']:<12} {line['hours']:>6} hr  {line['cost']:>9,.2f}")
    summary = aggregate([result], card=card)
    print(f"Factory {summary['factory_cost']:,.2f} -> selling "
          f"{summary['selling_price']:,.2f} at {summary['margin_pct']}%")
