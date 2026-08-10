"""Pricing math for the design estimator.

These cover the arithmetic that decides what a client is charged. The failure mode they
exist for is not a crash — it is a number that looks entirely reasonable and is wrong,
because that is the one that gets sent out and honoured.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import calculators as calc  # noqa: E402


def spec_for(item_type, **dims):
    base = {"item_type": item_type, "label": "Test item", "faces": 1, "quantity": 1}
    base.update(dims)
    return base


# --- Missing dimensions must never price ----------------------------------------------
#
# Regression: the guard used to test only `gross_m2 <= 0`, which catches an item with no
# face at all but not one whose *remaining* dimensions still form a face. A counter given a
# length and a height but no depth kept its front fascia, quietly borrowed DEFAULT_DEPTH_M
# for the worktop and end panels, and priced at AED 1,092.91 with no warning attached.

@pytest.mark.parametrize("item_type, dims, missing", [
    ("wall",    {"length_m": 5.0, "height_m": 0.0},                    "height_m"),
    ("wall",    {"length_m": 0.0, "height_m": 2.4},                    "length_m"),
    ("counter", {"length_m": 4.0, "height_m": 1.1, "depth_m": 0.0},    "depth_m"),
    ("counter", {"length_m": 4.0, "height_m": 0.0, "depth_m": 0.6},    "height_m"),
    ("stage",   {"length_m": 6.0, "depth_m": 0.0},                     "depth_m"),
    ("stage",   {"length_m": 0.0, "depth_m": 4.0},                     "length_m"),
    ("arch",    {"length_m": 3.0, "height_m": 0.0},                    "height_m"),
])
def test_a_missing_required_dimension_refuses_to_price(item_type, dims, missing):
    boq = calc.compute_item_boq(spec_for(item_type, **dims))

    assert boq["needs_dimensions"] is True
    assert boq["factory_cost"] == 0.0
    assert boq["material_cost"] == 0.0
    assert boq["labor_cost"] == 0.0
    # The message has to name the field, or the PM cannot act on it.
    assert calc._DIM_LABELS[missing] in boq["dimension_message"]


@pytest.mark.parametrize("item_type, dims", [
    ("wall",    {"length_m": 5.0, "height_m": 2.4}),
    ("counter", {"length_m": 4.0, "height_m": 1.1, "depth_m": 0.6}),
    ("stage",   {"length_m": 6.0, "depth_m": 4.0}),
    ("arch",    {"length_m": 3.0, "height_m": 2.5}),
])
def test_a_complete_spec_still_prices(item_type, dims):
    """The other half of the guard: it must not become so strict it blocks real work."""
    boq = calc.compute_item_boq(spec_for(item_type, **dims))

    assert boq["needs_dimensions"] is False
    assert boq["factory_cost"] > 0
    assert boq["gross_area_m2"] > 0


def test_depth_defaults_only_where_it_is_construction_thickness():
    """wall/arch depth is a build detail; counter/stage depth is half the object."""
    assert calc.missing_required_dims("wall", {"length_m": 5, "height_m": 2.4}) == []
    assert calc.missing_required_dims("arch", {"length_m": 3, "height_m": 2.5}) == []
    assert calc.missing_required_dims("counter", {"length_m": 4, "height_m": 1.1}) == ["depth_m"]
    assert calc.missing_required_dims("stage", {"length_m": 6}) == ["depth_m"]


def test_counter_depth_materially_changes_the_price():
    """Guards the premise of the rule above — if depth were near-free, requiring it
    would be pedantry rather than protection."""
    shallow = calc.compute_item_boq(spec_for("counter", length_m=4.0, height_m=1.1, depth_m=0.6))
    deep = calc.compute_item_boq(spec_for("counter", length_m=4.0, height_m=1.1, depth_m=1.2))

    assert deep["factory_cost"] > shallow["factory_cost"] * 1.15


# --- Area arithmetic -------------------------------------------------------------------

def test_cutouts_are_subtracted_from_gross_area():
    plain = spec_for("wall", length_m=5.0, height_m=2.4)
    with_door = spec_for("wall", length_m=5.0, height_m=2.4,
                         cutouts=[{"width_m": 1.0, "height_m": 2.1, "count": 1}])

    a = calc.compute_item_boq(plain)
    b = calc.compute_item_boq(with_door)

    assert a["cutout_area_m2"] == 0
    assert b["cutout_area_m2"] == pytest.approx(2.1)
    assert b["net_area_m2"] == pytest.approx(a["net_area_m2"] - 2.1)


def test_cutout_count_multiplies():
    spec = spec_for("wall", length_m=10.0, height_m=3.0,
                    cutouts=[{"width_m": 1.0, "height_m": 2.0, "count": 3}])
    assert calc.compute_item_boq(spec)["cutout_area_m2"] == pytest.approx(6.0)


def test_over_declared_cutouts_floor_at_zero_rather_than_going_negative():
    """A drawing can declare more opening than wall. Net area must not go negative and
    hand back a negative cost."""
    spec = spec_for("wall", length_m=2.0, height_m=2.0,
                    cutouts=[{"width_m": 5.0, "height_m": 5.0, "count": 1}])
    boq = calc.compute_item_boq(spec)

    assert boq["net_area_m2"] == 0
    assert boq["factory_cost"] >= 0


def test_sheets_required_applies_wastage_before_rounding_up():
    """Sheets are bought whole; wastage has to be inside the ceiling, not after it."""
    assert calc.sheets_required(0) == (0, 0.0)

    count, with_wastage = calc.sheets_required(calc.SHEET_AREA_M2)
    assert with_wastage == pytest.approx(calc.SHEET_AREA_M2 * (1 + calc.WASTAGE_FACTOR))
    assert count == 2          # one sheet plus any wastage cannot fit in one sheet
    assert isinstance(count, int)


# --- Quantity and margin ---------------------------------------------------------------

def test_quantity_scales_cost_and_area_linearly():
    one = calc.compute_item_boq(spec_for("wall", length_m=5.0, height_m=2.4, quantity=1))
    two = calc.compute_item_boq(spec_for("wall", length_m=5.0, height_m=2.4, quantity=2))

    assert two["unit_material_cost"] == one["unit_material_cost"]
    assert two["material_cost"] == pytest.approx(one["material_cost"] * 2)
    assert two["factory_cost"] == pytest.approx(one["factory_cost"] * 2)


def test_margin_is_a_markup_on_factory_cost_not_a_discount_off_selling():
    """25% margin means selling = factory x 1.25. Getting this backwards (treating it as a
    gross-margin divisor) underprices every quote by a predictable amount."""
    boq = calc.compute_item_boq(spec_for("wall", length_m=5.0, height_m=2.4))
    result = calc.aggregate([boq], margin_pct=25)

    assert result["margin_amount"] == pytest.approx(result["factory_cost"] * 0.25, abs=0.02)
    assert result["selling_price"] == pytest.approx(result["factory_cost"] * 1.25, abs=0.02)


def test_negative_margin_is_clamped_rather_than_selling_below_cost():
    boq = calc.compute_item_boq(spec_for("wall", length_m=5.0, height_m=2.4))
    result = calc.aggregate([boq], margin_pct=-50)

    assert result["margin_pct"] == 0
    assert result["selling_price"] == result["factory_cost"]


def test_aggregate_totals_track_the_items_it_was_given():
    a = calc.compute_item_boq(spec_for("wall", length_m=5.0, height_m=2.4))
    b = calc.compute_item_boq(spec_for("counter", length_m=4.0, height_m=1.1, depth_m=0.6))
    result = calc.aggregate([a, b], margin_pct=0)

    assert result["item_count"] == 2
    assert result["factory_cost"] == pytest.approx(a["factory_cost"] + b["factory_cost"], abs=0.02)
    assert result["total_material_cost"] == pytest.approx(
        a["material_cost"] + b["material_cost"], abs=0.02)


def test_same_material_across_drawings_becomes_one_purchase_line():
    """The factory orders against the consolidated take-off, so two walls using the same
    board must merge into a single row rather than appearing twice."""
    a = calc.compute_item_boq(spec_for("wall", length_m=5.0, height_m=2.4))
    b = calc.compute_item_boq(spec_for("wall", length_m=3.0, height_m=2.4))
    result = calc.aggregate([a, b])

    codes = [m["code"] for m in result["consolidated_materials"]]
    assert len(codes) == len(set(codes)), f"duplicate purchase lines: {codes}"


def test_items_needing_dimensions_contribute_nothing_to_the_total():
    """An un-priceable item must not quietly drag the quote total down or up."""
    good = calc.compute_item_boq(spec_for("wall", length_m=5.0, height_m=2.4))
    blocked = calc.compute_item_boq(spec_for("counter", length_m=4.0, height_m=1.1))

    alone = calc.aggregate([good], margin_pct=20)
    together = calc.aggregate([good, blocked], margin_pct=20)

    assert together["factory_cost"] == alone["factory_cost"]
    assert together["selling_price"] == alone["selling_price"]
