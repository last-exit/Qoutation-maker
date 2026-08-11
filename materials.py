"""Resolve which rate-card row fills each construction role.

The estimator used to name materials in code: `DEFAULT_SUBSTRATE = "WD-MDF-18"`, a
`FINISH_SYSTEMS` table full of specific codes, and so on. That duplicated the catalogue —
the same materials already sit in `master_rate_card.csv` — and it meant adding a board to
the sheet did nothing until someone also edited Python.

This module removes the duplication. A construction *role* (the carcass board, the stud
framing, the finish primer) is described by what it is *for*, and filled by searching the
sheet's own `Category`, `Unit` and `Typical Usage` columns. The rate card becomes the only
place materials live: add a row and it is immediately eligible; delete one and the item
reports the gap rather than silently substituting.

Nothing here is a catalogue. `SUBSTRATE_QUERIES["wall_curved"]` says "a curved wall wants a
flexible cladding board", never "a curved wall uses WD-MDF-06". Which code that resolves to
is entirely the sheet's decision, and changes when the sheet changes.

Determinism is the contract (see the `calculators.py` docstring): the same drawing must
always cost the same. So a tie between two equally-suitable rows is broken by lowest cost,
then by code, never by dict order — an unstable pick would quietly break that promise.
"""


class Query:
    """A description of the material a role needs, matched against the sheet.

    * `category` and `unit` are hard filters — a substrate is a Sheet in Wood & Boards, and
      a row failing either is not a candidate at all. This is what stops a framing query
      (also Wood & Boards) from picking a 3 mm MDF board, and a substrate query from
      picking a stud.
    * `prefer` / `avoid` are scored: one point per prefer keyword found in the row's
      category + usage + description text, minus one per avoid keyword. Highest wins.

    Keywords are substrings, deliberately: "shelv" catches both "shelving" and "shelves",
    which are written inconsistently across the sheet.
    """

    __slots__ = ("category", "unit", "prefer", "avoid")

    def __init__(self, category=None, unit=None, prefer=(), avoid=()):
        self.category = (category or "").lower()
        self.unit = (unit or "").lower()
        self.prefer = tuple(k.lower() for k in prefer)
        self.avoid = tuple(k.lower() for k in avoid)

    def _text(self, item):
        return f"{item.category} {item.usage} {item.description}".lower()

    def score(self, item):
        """Points for `item`, or None if it fails a hard filter."""
        if self.category and self.category not in (item.category or "").lower():
            return None
        if self.unit and self.unit != (item.unit or "").lower():
            return None
        text = self._text(item)
        points = sum(1 for kw in self.prefer if kw in text)
        points -= sum(1 for kw in self.avoid if kw in text)
        return points

    def matched_keyword(self, item):
        """The first prefer keyword present — used to explain the choice to the PM."""
        text = self._text(item)
        for kw in self.prefer:
            if kw in text:
                return kw
        return None


# --- Substrate: the carcass board, per shape ------------------------------------------
# Keyed by the merged shape (see shapes.py). Every query filters to Sheet in Wood & Boards,
# so no framing piece or veneer can ever win one.

_BOARDS = "Wood & Boards"

SUBSTRATE_QUERIES = {
    "wall_flat":      Query(_BOARDS, "Sheet", prefer=("structural", "wall"),
                            avoid=("curved", "moisture", "drawer", "shelv")),
    "wall_curved":    Query(_BOARDS, "Sheet", prefer=("curved", "flexible", "cladding")),
    "counter_flat":   Query(_BOARDS, "Sheet", prefer=("counter", "structural"),
                            avoid=("curved", "moisture", "shelv")),
    "counter_curved": Query(_BOARDS, "Sheet", prefer=("curved", "flexible", "cladding")),
    "arch":           Query(_BOARDS, "Sheet", prefer=("structural", "wall"),
                            avoid=("curved", "moisture", "drawer", "shelv")),
    "stage":          Query(_BOARDS, "Sheet", prefer=("stage", "sub-floor", "subfloor"),
                            avoid=("curved", "drawer")),
    "ring":           Query(_BOARDS, "Sheet", prefer=("shelv", "lightweight"),
                            avoid=("curved", "structural", "drawer")),
}

# Framing: the stud skeleton. Filtered to Piece, which in this sheet is only the two WD-FRM
# rows, so the wall/stage split comes down to prefer/avoid alone.
FRAMING_QUERIES = {
    "light": Query(_BOARDS, "Piece", prefer=("skeleton", "internal", "standard"),
                   avoid=("heavy", "load-bearing", "stage")),
    "heavy": Query(_BOARDS, "Piece", prefer=("heavy", "load-bearing", "stage", "support")),
}

# Shape-independent roles. These fill the same way regardless of what is being built.
STANDARD_QUERIES = {
    "fixings":  Query("Hardware", prefer=("assembly", "framing")),
    "brackets": Query("Hardware", prefer=("reinforc", "joint", "bracket")),
    "adhesive": Query("Paints & Chems", prefer=("carpentry", "joint")),
}

# Finish component roles. A finish is a *method* — "primer, two coats, then PU" — which no
# single sheet row can express, so the recipe (which roles, how many coats) lives in
# `FINISH_BUNDLES` below and only the products resolve from the sheet here.
FINISH_QUERIES = {
    "primer":           Query("Paints & Chems", prefer=("surface preparation", "primer")),
    "topcoat":          Query("Paints & Chems", prefer=("spray finish", "flawless")),
    "thinner":          Query("Paints & Chems", prefer=("thinning", "cleaning spray")),
    "emulsion":         Query("Paints & Chems", prefer=("wall painting", "covers")),
    "laminate":         Query("Finishes & Decor", prefer=("countertop", "durable wall")),
    "contact_adhesive": Query("Paints & Chems", prefer=("bonding", "laminate", "vinyl")),
    "printed_vinyl":    Query("Finishes & Decor", prefer=("branding", "wrap", "graphic")),
    "veneer":           Query(_BOARDS, "Sqm", prefer=("wooden finish", "veneer", "high-end")),
}


def resolve(card, query):
    """The best-matching rate item for `query`, or None if the sheet has nothing suitable.

    Result: {code, description, unit, cost, reason, keyword, score}. Cached per card so a
    role is scored once per rate-card load, never once per item.
    """
    cache = getattr(card, "_material_cache", None)
    if cache is None:
        cache = {}
        setattr(card, "_material_cache", cache)

    signature = (query.category, query.unit, query.prefer, query.avoid)
    if signature in cache:
        return cache[signature]

    best = None          # (sort_key, item, score)
    for item in card.items.values():
        points = query.score(item)
        if points is None:
            continue
        # Highest score, then cheapest, then code — a total order, so the winner never
        # depends on iteration order.
        sort_key = (-points, item.avg_cost, item.code)
        if best is None or sort_key < best[0]:
            best = (sort_key, item, points)

    if best is None:
        cache[signature] = None
        return None

    item, score = best[1], best[2]
    keyword = query.matched_keyword(item)
    if keyword:
        reason = f'sheet says "{item.usage}"' if item.usage else f'matched "{keyword}"'
    else:
        reason = item.usage and f'sheet says "{item.usage}"' or "only candidate on the sheet"

    result = {
        "code": item.code,
        "description": item.description,
        "unit": item.unit,
        "cost": item.avg_cost,
        "reason": reason,
        "keyword": keyword,
        "score": score,
    }
    cache[signature] = result
    return result


def substrate_query(shape_key):
    """The substrate query for a merged shape key, defaulting to a flat wall."""
    return SUBSTRATE_QUERIES.get(shape_key, SUBSTRATE_QUERIES["wall_flat"])


# --- Finish bundles -------------------------------------------------------------------
# A finish names the roles it needs and how many coats each takes. The products come from
# FINISH_QUERIES; the coats and coverage are consumption ratios, not materials, and stay
# here (mirrored into shop_config so a PM can adjust coverage without a release).
#
# `role`     which FINISH_QUERIES entry supplies the product
# `coats`    how many passes (paint only)
# `drives`   what the quantity scales with: "area" (sheets/sqm) or "paint" (coverage math)

FINISH_BUNDLES = {
    "paint_pu": {
        "label": "Primer + PU Spray",
        "painting_hr_m2": 0.30,
        "components": [
            {"role": "primer",  "coats": 2, "coverage_m2_per_l": 10.0, "unit_size": 5.0},
            {"role": "topcoat", "coats": 2, "coverage_m2_per_l": 8.0,  "unit_size": 1.0},
            {"role": "thinner", "coats": 1, "coverage_m2_per_l": 40.0, "unit_size": 5.0},
        ],
    },
    "paint_emulsion": {
        "label": "Matt Emulsion",
        "painting_hr_m2": 0.18,
        "components": [
            {"role": "primer",   "coats": 1, "coverage_m2_per_l": 10.0,  "unit_size": 5.0},
            {"role": "emulsion", "coats": 2, "coverage_m2_per_l": 4.444, "unit_size": 18.0},
        ],
    },
    "laminate_hpl": {
        "label": "HPL Laminate",
        "finishing_hr_m2": 0.35,
        "components": [
            {"role": "laminate",         "drives": "area"},
            {"role": "contact_adhesive", "m2_per_unit": 55.0},
        ],
    },
    "vinyl_print": {
        "label": "Printed Vinyl Wrap",
        "finishing_hr_m2": 0.22,
        "components": [{"role": "printed_vinyl", "drives": "area"}],
    },
    "veneer_oak": {
        "label": "Natural Oak Veneer",
        "finishing_hr_m2": 0.45,
        "components": [
            {"role": "veneer",           "drives": "area"},
            {"role": "contact_adhesive", "m2_per_unit": 55.0},
        ],
    },
    "none": {"label": "Raw / Unfinished", "components": []},
}
DEFAULT_FINISH = "paint_pu"
