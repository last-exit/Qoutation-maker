"""Editable fabrication constants for curved and ring work.

Everything in here is a *shop* fact, not a law of geometry: how many flexible skins go on a
curve, how close the studs sit, how much longer a curved metre takes to build. Those vary
between workshops and they change over time, so none of them are baked into the pricing
code. They live in `estimator_config.json` beside the labour rates the PM already edits,
and every one of them is exposed in the UI.

Two rules govern this module:

1. **Nothing here is silently assumed.** Each default carries a `confirmed` flag. Anything
   still `False` is a figure taken from ordinary joinery practice rather than from this
   business's own costings, and the UI marks it so — a PM should never discover that a
   number they trusted was one this project invented.
2. **A bad config never breaks a quote.** Unreadable JSON, a missing key or a nonsense
   value falls back to the default and reports it. The estimator keeps working.

`curves.py` holds the mathematics, which is fixed. This holds the workshop's opinions,
which are not.
"""

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = _ROOT / "estimator_config.json"

# The section key inside estimator_config.json. Kept separate from `labor_rates` so the
# existing file and its loader in rate_card.py are untouched by anything here.
SECTION = "fabrication"


# --- Defaults ---------------------------------------------------------------------------
# `value`      the number used when the PM has not set one
# `label`      what the UI calls it
# `hint`       why it exists, shown under the field
# `unit`       for display only
# `confirmed`  False = a trade-practice figure this project chose, not one the shop supplied
#
# The confirmed=False entries are exactly the list the design document flagged as
# NEEDS PM CONFIRMATION. Do not flip one to True without a real number from the workshop.

DEFAULTS = {
    "curved_skin_layers": {
        "value": 2,
        "label": "Flexible skin layers on a curve",
        "hint": "A curve is built as thin skins laminated over the frame, not by bending "
                "18 mm board. Two layers of 6 mm is the usual build-up.",
        "unit": "layers",
        "confirmed": False,
    },
    "curved_substrate_code": {
        "value": "WD-MDF-06",
        "label": "Board used for curved skins",
        "hint": "The rate card lists WD-MDF-06 as 'Curved walls, flexible cladding skins', "
                "so it is the default. Change it if your shop bends something else.",
        "unit": "rate card code",
        "confirmed": True,          # taken from the business's own rate card
    },
    "curved_stud_spacing_m": {
        "value": 0.40,
        "label": "Stud centres on a curve",
        "hint": "Curves need more formers than the 0.60 m used on a flat wall, or the "
                "skin reads as a series of flats.",
        "unit": "m",
        "confirmed": False,
    },
    "curve_labour_factor": {
        "value": 1.45,
        "label": "Curved work labour factor",
        "hint": "Multiplies carpentry hours on curved elements only. 1.45 means a curved "
                "square metre takes 45% longer than a flat one.",
        "unit": "x flat rate",
        "confirmed": False,
    },
    "ring_wastage_factor": {
        "value": 0.35,
        "label": "Ring / disc cutting wastage",
        "hint": "Circles nest far worse on an 8x4 sheet than rectangles do. This replaces "
                "the standard 10% for ring shelves only.",
        "unit": "fraction",
        "confirmed": False,
    },
    "ring_edge_banding_code": {
        "value": "",
        "label": "Edge banding for ring shelves",
        "hint": "Optional. A rate card code billed per metre of ring edge. Leave blank to "
                "leave edging out of the bill entirely.",
        "unit": "rate card code",
        "confirmed": True,          # blank by default: nothing is invented
    },
    "min_curve_angle_deg": {
        "value": 5.0,
        "label": "Ignore curves shallower than",
        "hint": "Below this the arc is priced as a flat panel. Stops a rounded corner "
                "being costed as curved joinery.",
        "unit": "degrees",
        "confirmed": True,          # a modelling threshold, not a shop cost
    },
}

_NUMERIC = {
    "curved_skin_layers": (1, 6),
    "curved_stud_spacing_m": (0.10, 1.20),
    "curve_labour_factor": (1.0, 4.0),
    "ring_wastage_factor": (0.0, 2.0),
    "min_curve_angle_deg": (0.0, 90.0),
}


def _coerce(key, raw):
    """Clamps a configured value into a sane range, or returns None to use the default."""
    default = DEFAULTS[key]["value"]
    if key not in _NUMERIC:
        # String settings (rate card codes) pass through, trimmed.
        return str(raw).strip() if raw is not None else default

    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value != value:                     # NaN
        return None

    low, high = _NUMERIC[key]
    value = max(low, min(high, value))
    return int(round(value)) if isinstance(default, int) else value


def load(path=None):
    """Current fabrication settings as {key: value}, with problems reported.

    Returns (values, problems). `problems` is a list of human-readable strings — the caller
    surfaces them rather than this module printing, so the UI can show them next to the
    fields they concern.
    """
    values = {key: meta["value"] for key, meta in DEFAULTS.items()}
    problems = []

    config_path = Path(path) if path else CONFIG_PATH
    if not config_path.exists():
        return values, problems

    try:
        with open(config_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception as exc:
        problems.append(f"estimator_config.json unreadable ({exc}) — using default "
                        f"fabrication settings.")
        return values, problems

    section = data.get(SECTION) or {}
    if not isinstance(section, dict):
        problems.append(f"'{SECTION}' in estimator_config.json is not a set of settings — "
                        f"using defaults.")
        return values, problems

    for key, raw in section.items():
        if key not in DEFAULTS:
            problems.append(f"Unknown fabrication setting '{key}' ignored.")
            continue
        coerced = _coerce(key, raw)
        if coerced is None:
            problems.append(f"'{key}' = {raw!r} is not a usable number — "
                            f"using {DEFAULTS[key]['value']}.")
            continue
        values[key] = coerced

    return values, problems


def save(updates, path=None):
    """Merges `updates` into the fabrication section, leaving the rest of the file alone.

    Reads, merges and rewrites so the PM's labour rates and margin survive. Returns
    (values, problems) exactly like `load`, so a caller can round-trip and re-render from
    one result.
    """
    config_path = Path(path) if path else CONFIG_PATH

    data = {}
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            # A corrupt file must not cost the PM their labour rates silently, so the
            # original is kept beside the rewritten one.
            try:
                backup = config_path.with_suffix(".json.corrupt")
                backup.write_text(config_path.read_text(encoding="utf-8"), encoding="utf-8")
            except Exception:
                pass
            data = {}

    section = dict(data.get(SECTION) or {})
    problems = []
    for key, raw in (updates or {}).items():
        if key not in DEFAULTS:
            problems.append(f"Unknown fabrication setting '{key}' ignored.")
            continue
        coerced = _coerce(key, raw)
        if coerced is None:
            problems.append(f"'{key}' = {raw!r} is not a usable number — left unchanged.")
            continue
        section[key] = coerced

    data[SECTION] = section
    data.setdefault(
        "_fabrication_comment",
        "Curved and ring fabrication constants for the Automated Design Estimator. "
        "Edit here or in the estimator's Fabrication settings. Values marked unconfirmed "
        "in the UI are trade-practice defaults, not this workshop's measured figures.",
    )

    with open(config_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")

    values, load_problems = load(config_path)
    return values, problems + load_problems


def describe(path=None):
    """Everything the settings UI needs: current value, default, label, hint and status."""
    values, problems = load(path)
    fields = []
    for key, meta in DEFAULTS.items():
        fields.append({
            "key": key,
            "value": values[key],
            "default": meta["value"],
            "label": meta["label"],
            "hint": meta["hint"],
            "unit": meta["unit"],
            "confirmed": meta["confirmed"],
            "modified": values[key] != meta["value"],
        })
    return {
        "fields": fields,
        "problems": problems,
        "unconfirmed": [f["key"] for f in fields if not f["confirmed"] and not f["modified"]],
        "path": str(Path(path) if path else CONFIG_PATH),
    }
