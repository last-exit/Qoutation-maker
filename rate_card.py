"""Loader for the master rate card CSV that prices the automated design estimator.

The card is the single source of material cost. Nothing in the estimator invents a
price: every line in a generated BOQ resolves to an `Item Code` in this file, so a
change to the CSV moves the quote and nothing else does.

Deliberately stdlib-only (`csv`, not pandas) — pandas is not a dependency of this
app and adding a ~50MB wheel to price 58 rows would be the tail wagging the dog.
"""

import csv
import json
import os
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent

# The file ships as `master_rate_card.csv.csv` (a double extension from the export that
# produced it). The spec calls it `master_rate_card.csv`. Accept either rather than
# renaming the operator's file underneath them, preferring the clean name if it appears.
RATE_CARD_CANDIDATES = ("master_rate_card.csv", "master_rate_card.csv.csv")

LABOR_CONFIG_PATH = _ROOT / "estimator_config.json"

# Labor is NOT in the material rate card — all 58 rows there are materials. These are the
# fallback trade rates, in AED/hour, and they live in `estimator_config.json` so a PM can
# edit them without touching code. If the CSV ever grows a `Labor` category, those rows win
# (see `RateCard.labor_rate`), which is the migration path to a single-file source of truth.
_DEFAULT_LABOR = {
    "carpentry": 45.0,
    "painting": 38.0,
    "electrical": 55.0,
    "assembly": 35.0,
    "finishing": 42.0,
}

# Margin applied to factory cost to reach the client selling price. Overridable per-quote
# from the UI; this is only the starting position.
_DEFAULT_MARGIN_PCT = 35.0


class RateItem:
    """One priced row of the rate card."""

    __slots__ = ("code", "category", "description", "unit", "avg_cost", "low", "high", "usage")

    def __init__(self, code, category, description, unit, avg_cost, low, high, usage):
        self.code = code
        self.category = category
        self.description = description
        self.unit = unit
        self.avg_cost = avg_cost
        self.low = low
        self.high = high
        self.usage = usage

    def to_dict(self):
        return {
            "code": self.code,
            "category": self.category,
            "description": self.description,
            "unit": self.unit,
            "avg_cost": self.avg_cost,
            "low": self.low,
            "high": self.high,
            "usage": self.usage,
        }

    def __repr__(self):
        return f"<RateItem {self.code} {self.avg_cost} AED/{self.unit}>"


class MissingRateError(KeyError):
    """Raised when a BOQ line references an item code the card does not contain.

    Deliberately loud rather than defaulting to zero: a silent 0.00 AED line reads as a
    free material on the client quotation, which is the one failure mode that costs money.
    """


def _to_float(raw):
    """Pulls the first number out of a cell, tolerating currency text and thousands commas."""
    if raw is None:
        return 0.0
    text = str(raw).strip().replace(",", "")
    if not text:
        return 0.0
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else 0.0


def _parse_range(raw):
    """`"58.00 – 72.00"` -> `(58.0, 72.0)`.

    The separator in the shipped file is an en-dash (U+2013), not a hyphen; both are
    accepted so a hand-edited row does not silently collapse to a single-value range.
    """
    text = str(raw or "").replace(",", "")
    numbers = re.findall(r"\d+(?:\.\d+)?", text)
    if len(numbers) >= 2:
        return float(numbers[0]), float(numbers[1])
    if len(numbers) == 1:
        value = float(numbers[0])
        return value, value
    return 0.0, 0.0


def _normalize_header(name):
    return re.sub(r"[^a-z]", "", (name or "").lower())


# Header text varies between exports of this card ("Avg. Cost (AED)" vs "Avg Cost"), so
# columns are matched on letters-only keys rather than exact strings.
_COLUMN_ALIASES = {
    "category": ("category",),
    "code": ("itemcode", "code"),
    "description": ("descriptionspecification", "description", "specification"),
    "unit": ("unit",),
    "range": ("pricerangeaed", "pricerange", "range"),
    "avg": ("avgcostaed", "avgcost", "averagecostaed", "averagecost", "cost"),
    "usage": ("typicalusage", "usage"),
}


def _build_column_map(fieldnames):
    normalized = {_normalize_header(name): name for name in (fieldnames or [])}
    mapping = {}
    for key, aliases in _COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                mapping[key] = normalized[alias]
                break
    return mapping


class RateCard:
    """Indexed, read-only view over the rate card CSV plus the labor rate config."""

    def __init__(self, items, labor_rates, margin_pct, source_path):
        self.items = items                      # code -> RateItem
        self.labor_rates = labor_rates          # trade -> AED/hour
        self.margin_pct = margin_pct
        self.source_path = source_path

        self._by_category = {}
        for item in items.values():
            self._by_category.setdefault(item.category, []).append(item)

    # --- lookup ---------------------------------------------------------------

    def get(self, code):
        """Returns the RateItem for `code`, or raises MissingRateError."""
        item = self.items.get(code)
        if item is None:
            raise MissingRateError(
                f"Item code '{code}' is not in the rate card ({self.source_path.name}). "
                f"Add a row for it, or point the estimator at a different code."
            )
        return item

    def cost_of(self, code):
        """Average unit cost in AED for `code`."""
        return self.get(code).avg_cost

    def has(self, code):
        return code in self.items

    def categories(self):
        return sorted(self._by_category.keys())

    def in_category(self, category):
        return list(self._by_category.get(category, []))

    def labor_rate(self, trade):
        """AED/hour for a trade.

        A `Labor` category in the CSV takes precedence over the JSON config, so the card
        can become the single source of truth simply by adding rows to it.
        """
        code = f"LB-{trade.upper()[:3]}"
        if code in self.items and self.items[code].category.lower().startswith("labor"):
            return self.items[code].avg_cost
        return self.labor_rates.get(trade, self.labor_rates.get("carpentry", 45.0))

    def search(self, needle, limit=25):
        """Substring match over code, description and usage — powers the material swap
        dropdowns in the estimator UI."""
        needle = (needle or "").strip().lower()
        if not needle:
            return []
        hits = []
        for item in self.items.values():
            haystack = f"{item.code} {item.description} {item.usage} {item.category}".lower()
            if needle in haystack:
                hits.append(item)
        hits.sort(key=lambda i: (i.category, i.code))
        return hits[:limit]

    def to_dict(self):
        return {
            "source": str(self.source_path),
            "count": len(self.items),
            "categories": self.categories(),
            "labor_rates": dict(self.labor_rates),
            "margin_pct": self.margin_pct,
            "items": [item.to_dict() for item in self.items.values()],
        }


def _resolve_card_path(explicit=None):
    if explicit:
        path = Path(explicit)
        if not path.is_absolute():
            path = _ROOT / path
        if not path.exists():
            raise FileNotFoundError(f"Rate card not found at {path}")
        return path

    for name in RATE_CARD_CANDIDATES:
        candidate = _ROOT / name
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "No rate card found. Expected one of "
        + " or ".join(RATE_CARD_CANDIDATES)
        + f" in {_ROOT}"
    )


def load_labor_config():
    """Reads estimator_config.json, writing it with defaults on first run."""
    if LABOR_CONFIG_PATH.exists():
        try:
            with open(LABOR_CONFIG_PATH, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            labor = {**_DEFAULT_LABOR, **(data.get("labor_rates") or {})}
            margin = float(data.get("margin_pct", _DEFAULT_MARGIN_PCT))
            return labor, margin
        except Exception as exc:
            print(f"estimator_config.json unreadable ({exc}); falling back to default rates.")
            return dict(_DEFAULT_LABOR), _DEFAULT_MARGIN_PCT

    payload = {
        "_comment": (
            "Labor rates in AED/hour and the default margin for the Automated Design "
            "Estimator. The material rate card carries no labor rows, so these live here. "
            "Adding a 'Labor' category to the rate card CSV overrides these values."
        ),
        "labor_rates": _DEFAULT_LABOR,
        "margin_pct": _DEFAULT_MARGIN_PCT,
    }
    try:
        with open(LABOR_CONFIG_PATH, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
    except Exception as exc:
        print(f"Could not write estimator_config.json ({exc}); using in-memory defaults.")
    return dict(_DEFAULT_LABOR), _DEFAULT_MARGIN_PCT


def load_rate_card(path=None):
    """Parses the rate card CSV into a RateCard. Raises if the file is missing or headerless."""
    card_path = _resolve_card_path(path)

    items = {}
    with open(card_path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = _build_column_map(reader.fieldnames)

        missing = [key for key in ("code", "unit", "avg") if key not in columns]
        if missing:
            raise ValueError(
                f"Rate card {card_path.name} is missing required column(s): {', '.join(missing)}. "
                f"Found headers: {reader.fieldnames}"
            )

        for row in reader:
            code = (row.get(columns["code"]) or "").strip()
            if not code:
                continue

            low, high = _parse_range(row.get(columns.get("range", ""), ""))
            avg = _to_float(row.get(columns["avg"]))
            # A blank average is recoverable from the range; a row with neither is a data
            # error and is skipped loudly rather than priced at zero.
            if avg <= 0 and (low or high):
                avg = round((low + high) / 2.0, 2)
            if avg <= 0:
                print(f"Rate card row '{code}' has no usable cost — skipped.")
                continue

            items[code] = RateItem(
                code=code,
                category=(row.get(columns.get("category", ""), "") or "Uncategorized").strip(),
                description=(row.get(columns.get("description", ""), "") or "").strip(),
                unit=(row.get(columns["unit"]) or "Unit").strip(),
                avg_cost=avg,
                low=low or avg,
                high=high or avg,
                usage=(row.get(columns.get("usage", ""), "") or "").strip(),
            )

    if not items:
        raise ValueError(f"Rate card {card_path.name} parsed to zero priced rows.")

    labor_rates, margin_pct = load_labor_config()
    return RateCard(items, labor_rates, margin_pct, card_path)


# --- module-level cache -------------------------------------------------------------
# The card is re-read when the file's mtime changes, so a PM editing prices in Excel sees
# the new numbers on the next calculation without restarting the desktop app.

_cache = {"card": None, "mtime": None, "path": None}


def get_rate_card(path=None, force=False):
    global _cache
    try:
        card_path = _resolve_card_path(path)
        mtime = os.path.getmtime(card_path)
    except (FileNotFoundError, OSError):
        if _cache["card"] is not None and not force:
            return _cache["card"]
        raise

    stale = (
        force
        or _cache["card"] is None
        or _cache["mtime"] != mtime
        or _cache["path"] != card_path
    )
    if stale:
        _cache = {"card": load_rate_card(card_path), "mtime": mtime, "path": card_path}
    return _cache["card"]


if __name__ == "__main__":
    card = get_rate_card()
    print(f"Loaded {len(card.items)} items from {card.source_path.name}")
    for category in card.categories():
        rows = card.in_category(category)
        print(f"  {category:<20} {len(rows):>3} items")
    print(f"Labor rates: {card.labor_rates}")
    print(f"Default margin: {card.margin_pct}%")
