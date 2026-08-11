"""Rate card parsing and lookup.

The card is a hand-maintained CSV, so these lean on the cases a human editing a spreadsheet
actually produces: currency symbols typed into a number column, thousands separators, a
range written with whichever dash was to hand, and a code referenced before its row exists.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import rate_card as rc  # noqa: E402


def item(code, avg_cost=10.0, category="Board", description="Test item", unit="sheet"):
    return rc.RateItem(code=code, category=category, description=description, unit=unit,
                       avg_cost=avg_cost, low=avg_cost, high=avg_cost, usage="")


def card_of(*items, labor_rates=None, margin_pct=25.0):
    return rc.RateCard({i.code: i for i in items},
                       labor_rates or {"carpentry": 45.0},
                       margin_pct, Path("test_card.csv"))


# --- Cell parsing ----------------------------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ("58", 58.0),
    ("58.50", 58.5),
    ("1,250.00", 1250.0),          # thousands separator
    ("AED 75.00", 75.0),           # currency prefix typed into the cell
    ("  92.5  ", 92.5),
    ("", 0.0),
    (None, 0.0),
    ("n/a", 0.0),                  # text where a number was expected
])
def test_to_float_tolerates_hand_typed_cells(raw, expected):
    assert rc._to_float(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("58.00 – 72.00", (58.0, 72.0)),   # en-dash, as shipped
    ("58.00 - 72.00", (58.0, 72.0)),        # hyphen, as hand-edited
    ("1,100 – 1,400", (1100.0, 1400.0)),
    ("65", (65.0, 65.0)),                   # single value -> degenerate range
    ("", (0.0, 0.0)),
    (None, (0.0, 0.0)),
])
def test_parse_range_accepts_either_dash(raw, expected):
    assert rc._parse_range(raw) == expected


@pytest.mark.parametrize("header, expected", [
    ("Item Code", "itemcode"),
    ("ITEM CODE", "itemcode"),
    ("item_code", "itemcode"),
    ("Avg. Cost (AED)", "avgcostaed"),
])
def test_headers_normalize_so_column_casing_does_not_matter(header, expected):
    assert rc._normalize_header(header) == expected


# --- Lookup ----------------------------------------------------------------------------

def test_a_missing_code_raises_rather_than_costing_zero():
    """A silent 0.00 line reads as a free material on the client quotation — the one
    failure mode that costs real money."""
    card = card_of(item("WD-MDF-18"))

    with pytest.raises(rc.MissingRateError) as excinfo:
        card.cost_of("WD-DOES-NOT-EXIST")

    assert excinfo.value.code == "WD-DOES-NOT-EXIST"
    assert "WD-DOES-NOT-EXIST" in str(excinfo.value)


def test_missing_rate_error_is_a_keyerror_so_existing_handlers_still_catch_it():
    assert issubclass(rc.MissingRateError, KeyError)


def test_cost_of_returns_the_average():
    assert card_of(item("WD-MDF-18", avg_cost=62.5)).cost_of("WD-MDF-18") == 62.5


def test_has_does_not_raise_for_unknown_codes():
    card = card_of(item("WD-MDF-18"))
    assert card.has("WD-MDF-18") is True
    assert card.has("NOPE") is False


# --- Labor rates -----------------------------------------------------------------------

def test_a_labor_row_in_the_csv_overrides_the_json_config():
    """Documented behaviour: adding Labor rows lets the card become the single source of
    truth without touching estimator_config.json."""
    card = card_of(
        item("LB-CAR", avg_cost=90.0, category="Labor", unit="hour"),
        labor_rates={"carpentry": 45.0},
    )
    assert card.labor_rate("carpentry") == 90.0


def test_labor_falls_back_to_the_config_when_the_csv_has_no_row():
    assert card_of(item("WD-MDF-18"), labor_rates={"carpentry": 45.0}).labor_rate("carpentry") == 45.0


def test_an_unknown_trade_falls_back_to_carpentry_rather_than_zero():
    card = card_of(item("WD-MDF-18"), labor_rates={"carpentry": 45.0})
    assert card.labor_rate("basket-weaving") == 45.0


def test_a_non_labor_row_sharing_the_prefix_does_not_hijack_the_rate():
    """LB- is only authoritative when the row is actually categorised as labor."""
    card = card_of(
        item("LB-CAR", avg_cost=7.0, category="Board"),   # miscategorised material
        labor_rates={"carpentry": 45.0},
    )
    assert card.labor_rate("carpentry") == 45.0


# --- Search ----------------------------------------------------------------------------

def test_search_matches_code_and_description_and_ignores_case():
    card = card_of(
        item("WD-MDF-18", description="MDF board 18mm"),
        item("PT-PU-01L", description="PU topcoat", category="Paint"),
    )

    assert [i.code for i in card.search("mdf")] == ["WD-MDF-18"]
    assert [i.code for i in card.search("TOPCOAT")] == ["PT-PU-01L"]
    assert card.search("") == []


def test_search_respects_its_limit():
    card = card_of(*[item(f"WD-{n:03d}", description="board") for n in range(40)])
    assert len(card.search("board", limit=5)) == 5


# --- The shipped card itself -----------------------------------------------------------

def test_the_real_rate_card_loads_and_prices_the_codes_the_estimator_uses():
    """Guards the actual file the PM depends on: every finish role must resolve to a real
    row on the sheet, or the estimator quietly leaves part of a finish uncosted."""
    card = rc.get_rate_card()

    assert len(card.items) > 0
    assert card.margin_pct >= 0

    import materials
    roles_used = {c["role"] for bundle in materials.FINISH_BUNDLES.values()
                  for c in bundle["components"]}
    unresolved = sorted(role for role in roles_used
                        if materials.resolve(card, materials.FINISH_QUERIES[role]) is None)
    assert not unresolved, f"finish roles the sheet cannot fill: {unresolved}"
