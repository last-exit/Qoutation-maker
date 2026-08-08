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

import rate_card as rate_card_module


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


ITEM_TYPES = {
    "wall":    {"label": "Feature Wall",  "surfaces": _wall_surfaces,    "carpentry_hr_m2": 0.45},
    "counter": {"label": "Kiosk Counter", "surfaces": _counter_surfaces, "carpentry_hr_m2": 0.85},
    "stage":   {"label": "Stage / Riser", "surfaces": _stage_surfaces,   "carpentry_hr_m2": 0.55},
    "arch":    {"label": "Main Arch",     "surfaces": _arch_surfaces,    "carpentry_hr_m2": 0.95},
}
DEFAULT_ITEM_TYPE = "wall"

# Sensible fallbacks when a drawing gives a plan dimension but no depth.
DEFAULT_DEPTH_M = {"wall": 0.20, "counter": 0.60, "stage": 3.00, "arch": 0.30}


# --- Finish systems -------------------------------------------------------------------
# Each finish is a recipe of rate-card codes with the coverage math that sizes them.
# `per` selects how the quantity is derived from the net clad area:
#   "sheet"   -> 8x4 sheet count with wastage
#   "sqm"     -> billed directly by the square metre
#   "liters"  -> area x coats / coverage, then divided into the purchase unit

FINISH_SYSTEMS = {
    "paint_pu": {
        "label": "Primer + PU Spray",
        "components": [
            {"code": "PT-PRM-05L", "per": "liters", "coverage_m2_per_l": 10.0, "coats": 2,
             "unit_size_l": 5.0, "trade": "painting"},
            {"code": "PT-PU-01L",  "per": "liters", "coverage_m2_per_l": 8.0,  "coats": 2,
             "unit_size_l": 1.0, "trade": "painting"},
            {"code": "PT-THN-05L", "per": "liters", "coverage_m2_per_l": 40.0, "coats": 1,
             "unit_size_l": 5.0, "trade": "painting"},
        ],
        "painting_hr_m2": 0.30,
    },
    "paint_emulsion": {
        "label": "Matt Emulsion",
        "components": [
            {"code": "PT-PRM-05L", "per": "liters", "coverage_m2_per_l": 10.0, "coats": 1,
             "unit_size_l": 5.0, "trade": "painting"},
            # 18L drum covers ~80 sqm per the rate card's own usage note -> 4.44 m2/L.
            {"code": "PT-EML-18L", "per": "liters", "coverage_m2_per_l": 4.444, "coats": 2,
             "unit_size_l": 18.0, "trade": "painting"},
        ],
        "painting_hr_m2": 0.18,
    },
    "laminate_hpl": {
        "label": "HPL Laminate (Solid)",
        "components": [
            {"code": "FN-HPL-SOL", "per": "sheet", "trade": "finishing"},
            {"code": "AD-GLU-15L", "per": "consumable", "m2_per_unit": ADHESIVE_M2_PER_DRUM,
             "trade": "finishing"},
        ],
        "painting_hr_m2": 0.0,
        "finishing_hr_m2": 0.35,
    },
    "laminate_wood": {
        "label": "HPL Laminate (Woodgrain)",
        "components": [
            {"code": "FN-HPL-WOD", "per": "sheet", "trade": "finishing"},
            {"code": "AD-GLU-15L", "per": "consumable", "m2_per_unit": ADHESIVE_M2_PER_DRUM,
             "trade": "finishing"},
        ],
        "painting_hr_m2": 0.0,
        "finishing_hr_m2": 0.35,
    },
    "vinyl_print": {
        "label": "Printed Vinyl Wrap",
        "components": [{"code": "FN-VNL-PRT", "per": "sqm", "trade": "finishing"}],
        "painting_hr_m2": 0.0,
        "finishing_hr_m2": 0.22,
    },
    "veneer_oak": {
        "label": "Natural Oak Veneer",
        "components": [
            {"code": "WD-VEN-OAK", "per": "sqm", "trade": "finishing"},
            {"code": "AD-GLU-15L", "per": "consumable", "m2_per_unit": ADHESIVE_M2_PER_DRUM,
             "trade": "finishing"},
        ],
        "painting_hr_m2": 0.0,
        "finishing_hr_m2": 0.45,
    },
    "none": {"label": "Raw / Unfinished", "components": [], "painting_hr_m2": 0.0},
}
DEFAULT_FINISH = "paint_pu"

# Substrate board options, keyed by the code used for the carcass.
SUBSTRATES = {
    "WD-MDF-18":   "MDF 18mm (standard)",
    "WD-MDF-18MR": "MDF 18mm Moisture Resistant",
    "WD-MDF-12":   "MDF 12mm",
    "WD-MDF-06":   "MDF 6mm (curved)",
    "WD-PLY-18M":  "Marine Plywood 18mm",
    "WD-PLY-18C":  "Commercial Plywood 18mm",
    "WD-BLK-18":   "Blockboard 18mm",
}
DEFAULT_SUBSTRATE = "WD-MDF-18"

FRAMING = {
    "WD-FRM-2X2": "White Wood Studs 2\"x2\"",
    "WD-FRM-2X4": "White Wood Studs 2\"x4\" (heavy)",
}
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

    surfaces = ITEM_TYPES[item_type]["surfaces"](length_m, height_m, depth_m, faces)
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


def stud_linear_meters(spec):
    """Framing skeleton: perimeter plates plus a vertical every STUD_SPACING_M.

    Returns (total_linear_m, breakdown_dict).
    """
    item_type = spec.get("item_type", DEFAULT_ITEM_TYPE)
    length_m = max(0.0, float(spec.get("length_m") or 0.0))
    height_m = max(0.0, float(spec.get("height_m") or 0.0))
    depth_m = float(spec.get("depth_m") or 0.0)
    if depth_m <= 0:
        depth_m = DEFAULT_DEPTH_M.get(item_type, 0.20)

    if item_type == "stage":
        # A deck is framed on plan, not in elevation: joists run across the short span.
        perimeter_m = 2 * (length_m + depth_m)
        vertical_count = int(math.floor(length_m / STUD_SPACING_M)) + 1
        vertical_m = vertical_count * depth_m
        legs_m = vertical_count * height_m
        total = perimeter_m + vertical_m + legs_m
        return total, {
            "perimeter_m": perimeter_m,
            "vertical_count": vertical_count,
            "vertical_m": vertical_m,
            "legs_m": legs_m,
        }

    perimeter_m = 2 * (length_m + height_m)
    vertical_count = int(math.floor(length_m / STUD_SPACING_M)) + 1
    vertical_m = vertical_count * height_m
    total = perimeter_m + vertical_m
    return total, {
        "perimeter_m": perimeter_m,
        "vertical_count": vertical_count,
        "vertical_m": vertical_m,
        "legs_m": 0.0,
    }


def paint_liters(area_m2, coverage_m2_per_l, coats):
    """Litres of wet product needed to put `coats` over `area_m2`."""
    if area_m2 <= 0 or coverage_m2_per_l <= 0:
        return 0.0
    return (area_m2 * max(1, int(coats))) / coverage_m2_per_l


# --- BOQ assembly ---------------------------------------------------------------------

def _line(card, code, qty, basis, category=None):
    """Prices one material line against the rate card. qty is rounded up to whole
    purchase units — you cannot buy 0.4 of a sheet."""
    item = card.get(code)
    whole_qty = int(math.ceil(qty - 1e-9)) if qty > 0 else 0
    return {
        "code": code,
        "description": item.description,
        "category": category or item.category,
        "unit": item.unit,
        "qty": whole_qty,
        "raw_qty": round(qty, 3),
        "unit_cost": item.avg_cost,
        "line_cost": round(whole_qty * item.avg_cost, 2),
        "basis": basis,
    }


def compute_item_boq(spec, card=None):
    """Full deterministic BOQ for one detected item.

    `spec` keys: item_type, label, length_m, height_m, depth_m, faces, cutouts[],
    substrate, framing, finish, quantity, plus optional lighting flags.
    """
    card = card or rate_card_module.get_rate_card()

    item_type = spec.get("item_type", DEFAULT_ITEM_TYPE)
    if item_type not in ITEM_TYPES:
        item_type = DEFAULT_ITEM_TYPE
    type_meta = ITEM_TYPES[item_type]

    quantity = max(1, int(spec.get("quantity") or 1))
    substrate = spec.get("substrate") or DEFAULT_SUBSTRATE
    framing = spec.get("framing") or DEFAULT_FRAMING
    finish_key = spec.get("finish") or DEFAULT_FINISH
    if finish_key not in FINISH_SYSTEMS:
        finish_key = DEFAULT_FINISH
    finish = FINISH_SYSTEMS[finish_key]

    if not card.has(substrate):
        substrate = DEFAULT_SUBSTRATE
    if not card.has(framing):
        framing = DEFAULT_FRAMING

    surfaces, gross_m2, cutout_m2, net_m2 = net_surface_area(spec)
    materials = []

    # --- Substrate boards -------------------------------------------------------
    sheet_count, area_with_wastage = sheets_required(net_m2)
    if sheet_count:
        materials.append(_line(
            card, substrate, sheet_count,
            f"{net_m2:.2f} m2 net x {1 + WASTAGE_FACTOR:.2f} wastage = {area_with_wastage:.2f} m2 "
            f"/ {SHEET_AREA_M2} m2 per sheet -> {sheet_count} sheets",
        ))

    # --- Framing ----------------------------------------------------------------
    linear_m, framing_detail = stud_linear_meters(spec)
    stud_pieces = 0
    if linear_m > 0:
        linear_with_wastage = linear_m * (1.0 + WASTAGE_FACTOR)
        stud_pieces = int(math.ceil(linear_with_wastage / STUD_PIECE_LEN_M))
        basis = (
            f"perimeter {framing_detail['perimeter_m']:.2f} m + "
            f"{framing_detail['vertical_count']} verticals @ {STUD_SPACING_M} m centres "
            f"({framing_detail['vertical_m']:.2f} m)"
        )
        if framing_detail.get("legs_m"):
            basis += f" + legs {framing_detail['legs_m']:.2f} m"
        basis += (
            f" = {linear_m:.2f} m x {1 + WASTAGE_FACTOR:.2f} "
            f"/ {STUD_PIECE_LEN_M} m per piece -> {stud_pieces} pieces"
        )
        materials.append(_line(card, framing, stud_pieces, basis))

    # --- Finish system ----------------------------------------------------------
    for component in finish["components"]:
        code = component["code"]
        if not card.has(code):
            continue
        mode = component["per"]

        if mode == "sheet":
            count, with_waste = sheets_required(net_m2)
            if count:
                materials.append(_line(
                    card, code, count,
                    f"{net_m2:.2f} m2 x {1 + WASTAGE_FACTOR:.2f} = {with_waste:.2f} m2 "
                    f"/ {SHEET_AREA_M2} m2 per sheet -> {count} sheets",
                ))
        elif mode == "sqm":
            qty = net_m2 * (1.0 + WASTAGE_FACTOR)
            if qty > 0:
                materials.append(_line(
                    card, code, qty,
                    f"{net_m2:.2f} m2 x {1 + WASTAGE_FACTOR:.2f} wastage = {qty:.2f} m2",
                ))
        elif mode == "liters":
            litres = paint_liters(net_m2, component["coverage_m2_per_l"], component["coats"])
            unit_size = component.get("unit_size_l", 1.0)
            units = litres / unit_size if unit_size else litres
            if units > 0:
                materials.append(_line(
                    card, code, units,
                    f"{net_m2:.2f} m2 x {component['coats']} coats "
                    f"/ {component['coverage_m2_per_l']} m2 per L = {litres:.2f} L "
                    f"/ {unit_size:g} L per unit -> {math.ceil(units)}",
                ))
        elif mode == "consumable":
            per_unit = component.get("m2_per_unit", 1.0)
            units = net_m2 / per_unit if per_unit else 0.0
            if units > 0:
                materials.append(_line(
                    card, code, units,
                    f"{net_m2:.2f} m2 / {per_unit:g} m2 per unit -> {math.ceil(units)}",
                ))

    # --- Fixings and consumables -------------------------------------------------
    if stud_pieces:
        joints = stud_pieces * SCREWS_PER_STUD_JOINT
        boxes = joints / SCREWS_PER_BOX
        if boxes > 0:
            materials.append(_line(
                card, "HW-SCR-BLK", boxes,
                f"{stud_pieces} stud pieces x {SCREWS_PER_STUD_JOINT} screws = {joints} "
                f"/ {SCREWS_PER_BOX} per box -> {math.ceil(boxes)}",
            ))
        brackets = stud_pieces * BRACKETS_PER_STUD_PIECE
        materials.append(_line(
            card, "HW-LBR-05", brackets,
            f"{stud_pieces} stud pieces x {BRACKETS_PER_STUD_PIECE} brackets -> {brackets}",
        ))

    if net_m2 > 0 and card.has("AD-WD-05L"):
        cans = net_m2 / WOOD_GLUE_M2_PER_CAN
        if cans > 0:
            materials.append(_line(
                card, "AD-WD-05L", cans,
                f"{net_m2:.2f} m2 / {WOOD_GLUE_M2_PER_CAN:g} m2 per can -> {math.ceil(cans)}",
            ))

    # --- Optional LED lighting ----------------------------------------------------
    if spec.get("led_meters"):
        led_m = float(spec["led_meters"])
        rolls = led_m / 5.0
        if rolls > 0:
            materials.append(_line(
                card, "EL-LED-12W", rolls,
                f"{led_m:.2f} m LED / 5 m per roll -> {math.ceil(rolls)}",
            ))
            drivers = math.ceil((led_m * 12.0) / 200.0)  # ~12W/m against a 200W driver
            materials.append(_line(
                card, "EL-TRN-200", drivers,
                f"{led_m:.2f} m x 12 W/m = {led_m * 12:.0f} W / 200 W per driver -> {drivers}",
            ))

    # --- Labor ---------------------------------------------------------------------
    labor = []
    carpentry_hours = net_m2 * type_meta["carpentry_hr_m2"]
    if carpentry_hours > 0:
        rate = card.labor_rate("carpentry")
        labor.append({
            "trade": "carpentry",
            "hours": round(carpentry_hours, 2),
            "rate": rate,
            "cost": round(carpentry_hours * rate, 2),
            "basis": f"{net_m2:.2f} m2 x {type_meta['carpentry_hr_m2']} hr/m2 ({type_meta['label']})",
        })

    painting_hr_m2 = finish.get("painting_hr_m2", 0.0)
    if painting_hr_m2 > 0 and net_m2 > 0:
        hours = net_m2 * painting_hr_m2
        rate = card.labor_rate("painting")
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
        rate = card.labor_rate("finishing")
        labor.append({
            "trade": "finishing",
            "hours": round(hours, 2),
            "rate": rate,
            "cost": round(hours * rate, 2),
            "basis": f"{net_m2:.2f} m2 x {finishing_hr_m2} hr/m2 ({finish['label']})",
        })

    if stud_pieces:
        assembly_hours = stud_pieces * 0.25
        rate = card.labor_rate("assembly")
        labor.append({
            "trade": "assembly",
            "hours": round(assembly_hours, 2),
            "rate": rate,
            "cost": round(assembly_hours * rate, 2),
            "basis": f"{stud_pieces} stud pieces x 0.25 hr each",
        })

    if spec.get("led_meters"):
        elec_hours = float(spec["led_meters"]) * 0.15
        rate = card.labor_rate("electrical")
        labor.append({
            "trade": "electrical",
            "hours": round(elec_hours, 2),
            "rate": rate,
            "cost": round(elec_hours * rate, 2),
            "basis": f"{float(spec['led_meters']):.2f} m LED x 0.15 hr/m",
        })

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
        "substrate": substrate,
        "framing": framing,
        "finish": finish_key,
        "finish_label": finish["label"],
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
    """Everything the UI needs to render its override dropdowns, sourced from the card."""
    card = card or rate_card_module.get_rate_card()
    return {
        "item_types": [
            {"key": key, "label": meta["label"]} for key, meta in ITEM_TYPES.items()
        ],
        "finishes": [
            {"key": key, "label": system["label"]} for key, system in FINISH_SYSTEMS.items()
        ],
        "substrates": [
            {"code": code, "label": label, "cost": card.cost_of(code)}
            for code, label in SUBSTRATES.items() if card.has(code)
        ],
        "framing": [
            {"code": code, "label": label, "cost": card.cost_of(code)}
            for code, label in FRAMING.items() if card.has(code)
        ],
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
