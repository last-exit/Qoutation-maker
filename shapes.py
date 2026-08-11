"""The shapes a PM can pick, and how each maps onto geometry and materials.

The estimator used to ask for two things that overlapped: an item *type* (Feature Wall,
Kiosk Counter, Stage, Main Arch) and a *shape* (Flat, Curved, Ring, Arched head). "Arch"
appeared in both lists, and Type=Feature Wall with Shape=Arched head was a selectable
combination that meant nothing. This module replaces the pair with one list of seven
concrete things a stand is actually built from.

Each shape declares three things:

* its **legacy pair** — the `(item_type, shape)` the pricing engine already knows how to
  cost. Merging the two dropdowns is a UI and vocabulary change; the geometry underneath is
  unchanged, so `wall_curved` simply *is* the old `(wall, curved)` and prices identically.
  That is what lets every existing test and every saved quotation keep their number.
* its **dimension fields** — so a ring never shows a Length box and a flat wall never shows
  a Curve rise box.
* its **material roles** — which substrate query fills its carcass (see `materials.py`) and
  whether it frames light or heavy.

`normalize()` is the one function callers need: hand it any spec — a new merged shape, a
legacy pair, or something half-migrated — and it returns the spec with `item_type` and
`shape` set to the vocabulary the engine consumes.
"""

# key -> definition. `item_type` and `shape` are the legacy vocabulary the pricing engine
# in calculators.py already handles; everything else is new UI/material metadata.
SHAPES = {
    "wall_flat": {
        "label": "Flat wall",
        "hint": "A straight feature wall or backdrop.",
        "item_type": "wall", "shape": "flat",
        "dims": ("length_m", "height_m", "depth_m", "faces"),
        "substrate": "wall_flat", "framing": "light",
    },
    "wall_curved": {
        "label": "Curved wall",
        "hint": "A wall bent on plan or elevation. Priced on the arc, not the chord.",
        "item_type": "wall", "shape": "curved",
        "dims": ("length_m", "height_m", "sagitta_m", "depth_m"),
        "substrate": "wall_curved", "framing": "light",
    },
    "counter_flat": {
        "label": "Counter",
        "hint": "A kiosk or bar counter: fascia, worktop and ends.",
        "item_type": "counter", "shape": "flat",
        "dims": ("length_m", "height_m", "depth_m"),
        "substrate": "counter_flat", "framing": "light",
    },
    "counter_curved": {
        "label": "Curved counter",
        "hint": "A barrel-fronted counter. Fascia and worktop follow the arc.",
        "item_type": "counter", "shape": "curved",
        "dims": ("length_m", "height_m", "depth_m", "sagitta_m"),
        "substrate": "counter_curved", "framing": "light",
    },
    "arch": {
        "label": "Arch",
        "hint": "A portal whose head runs over an arc.",
        "item_type": "arch", "shape": "arch",
        "dims": ("length_m", "height_m", "depth_m", "sagitta_m"),
        "substrate": "arch", "framing": "light",
    },
    "ring": {
        "label": "Ring shelf",
        "hint": "A circular or annular shelf, cut flat. Sized by its radii.",
        "item_type": "wall", "shape": "ring",
        "dims": ("outer_r_m", "inner_r_m", "faces"),
        "substrate": "ring", "framing": None,
    },
    "stage": {
        "label": "Stage",
        "hint": "A raised platform: walkable deck plus perimeter fascia.",
        "item_type": "stage", "shape": "flat",
        "dims": ("length_m", "depth_m", "height_m"),
        "substrate": "stage", "framing": "heavy",
    },
}
DEFAULT_SHAPE = "wall_flat"

# The reverse map, so a legacy (item_type, shape) pair finds its merged key. Where a legacy
# item_type had no explicit shape, `flat` is assumed — that was the old default.
_LEGACY_TO_KEY = {}
for _key, _meta in SHAPES.items():
    _LEGACY_TO_KEY.setdefault((_meta["item_type"], _meta["shape"]), _key)

# Field labels for the UI, one place so the wording cannot drift between form and summary.
DIM_LABELS = {
    "length_m": "Length (m)",
    "height_m": "Height (m)",
    "depth_m": "Depth (m)",
    "faces": "Clad faces",
    "sagitta_m": "Curve rise (m)",
    "outer_r_m": "Outer radius (m)",
    "inner_r_m": "Inner radius (m)",
}
# `faces` means shelves on a ring, which is worth saying on the label.
_RING_FIELD_LABELS = {"faces": "Shelves"}


def key_of(spec):
    """The merged shape key for a spec, accepting both new and legacy forms.

    A `shape` that is already a merged key is taken as-is. Otherwise the legacy
    `(item_type, shape)` pair is looked up. Anything unrecognised falls back to a flat wall
    rather than erroring, because this feeds a live UI.
    """
    shape = spec.get("shape")
    if shape in SHAPES:
        return shape

    item_type = spec.get("item_type") or "wall"
    legacy_shape = shape if shape in ("flat", "curved", "ring", "arch") else "flat"
    # A legacy ring was carried as item_type=wall, shape=ring regardless of the type.
    if legacy_shape == "ring":
        return "ring"
    if legacy_shape == "arch" or item_type == "arch":
        return "arch"
    return _LEGACY_TO_KEY.get((item_type, legacy_shape), DEFAULT_SHAPE)


def meta(spec):
    """The full shape definition for a spec."""
    return SHAPES[key_of(spec)]


def normalize(spec):
    """Return `spec` with `item_type` and `shape` in the engine's legacy vocabulary.

    Two cases, and the distinction matters:

    * A **merged key** in `shape` (from the new UI) is expanded to its legacy pair.
    * A **legacy pair** is left exactly as given. It is already the engine's vocabulary, and
      rewriting it would erase distinctions the merged list intentionally dropped but that
      old specs still rely on — an `arch` type with a `flat` shape is a square-headed
      portal, which has no merged key and must not be forced into the arched-head shape.

    Non-destructive: a shallow copy is returned. `shape_key` always carries a merged key for
    the UI and for material resolution.
    """
    out = dict(spec)
    shape = spec.get("shape")
    if shape in SHAPES:
        definition = SHAPES[shape]
        out["item_type"] = definition["item_type"]
        out["shape"] = definition["shape"]
        out["shape_key"] = shape
    else:
        out["shape_key"] = key_of(spec)
    return out


def dim_fields(shape_key):
    """(field, label) pairs the UI should show for a shape, in order."""
    definition = SHAPES.get(shape_key, SHAPES[DEFAULT_SHAPE])
    labels = dict(DIM_LABELS)
    if shape_key == "ring":
        labels.update(_RING_FIELD_LABELS)
    return [(field, labels[field]) for field in definition["dims"]]


def options_payload():
    """The shape list the UI renders, replacing the separate type and shape dropdowns."""
    return [
        {
            "key": key,
            "label": definition["label"],
            "hint": definition["hint"],
            # The legacy pair lets the browser map a parsed spec (which carries item_type +
            # shape) onto the merged dropdown without a second round-trip.
            "item_type": definition["item_type"],
            "shape": definition["shape"],
            "dims": [{"field": f, "label": lbl} for f, lbl in dim_fields(key)],
        }
        for key, definition in SHAPES.items()
    ]
