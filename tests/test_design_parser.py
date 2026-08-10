"""Drawing text -> dimensions.

This is where a wrong answer is most expensive and least visible: every figure here feeds
straight into the area math, and a unit read as centimetres instead of millimetres changes
a quote by 10x while still looking like a plausible drawing callout.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import design_parser as dp  # noqa: E402


def meters_for(text):
    return [d["meters"] for d in dp.extract_dimensions(text)]


# --- Explicit units are never guessed --------------------------------------------------

@pytest.mark.parametrize("text, expected_m", [
    ("2400mm", 2.4),
    ("2400 mm", 2.4),
    ("240cm", 2.4),
    ("2.4m", 2.4),
    ("2400MM", 2.4),        # casing varies between CAD exports
])
def test_a_stated_unit_is_honoured(text, expected_m):
    dims = dp.extract_dimensions(text)
    assert dims, f"no dimension found in {text!r}"
    assert dims[0]["meters"] == pytest.approx(expected_m)
    assert dims[0]["assumed_unit"] is False


def test_a_paired_callout_yields_both_components():
    dims = dp.extract_dimensions("5000 x 2400 mm")
    assert dims
    pair = dims[0]
    assert pair["kind"] == "pair"
    assert [c["meters"] for c in pair["components"]] == pytest.approx([5.0, 2.4])


# --- Bare numbers are inferred, and flagged as inferred ---------------------------------

@pytest.mark.parametrize("value, expected_m, expected_unit", [
    (2400, 2.4, "mm"),      # trade convention: bare numbers are millimetres
    (100, 0.1, "mm"),
    (50, 0.5, "cm"),
    (10, 0.1, "cm"),
    (2.4, 2.4, "m"),
])
def test_bare_numbers_follow_the_documented_thresholds(value, expected_m, expected_unit):
    assert dp._infer_bare_unit(value) == expected_unit
    assert dp._to_meters(value, expected_unit) == pytest.approx(expected_m)


def test_an_inferred_unit_is_marked_so_the_ui_can_show_it_as_a_guess():
    """The PM has to be able to tell a measured value from an assumed one."""
    dims = dp.extract_dimensions("5000 x 2400")
    assert dims
    assert dims[0]["assumed_unit"] is True


def test_a_stated_unit_on_a_pair_applies_to_both_numbers():
    dims = dp.extract_dimensions("5000 x 2400 mm")
    assert dims[0]["assumed_unit"] is False
    assert all(c["assumed_unit"] is False for c in dims[0]["components"])


# --- Noise rejection --------------------------------------------------------------------

def test_a_page_with_no_dimensions_returns_nothing_rather_than_guessing():
    assert dp.extract_dimensions("") == []
    assert dp.extract_dimensions("REVISION HISTORY") == []


def test_comma_decimals_are_read_as_decimals_not_thousands():
    """European-style CAD exports write 2,4m for 2.4m — reading it as 24 would be a 10x
    error in the client's favour or the factory's, depending on the axis."""
    dims = dp.extract_dimensions("2,4 x 1,2 m")
    assert dims
    assert [c["meters"] for c in dims[0]["components"]] == pytest.approx([2.4, 1.2])


# --- Item classification ----------------------------------------------------------------

@pytest.mark.parametrize("text, expected", [
    ("RECEPTION COUNTER PLAN", "counter"),
    ("FEATURE WALL ELEVATION", "wall"),
    ("MAIN STAGE LAYOUT", "stage"),
    ("ENTRANCE ARCH DETAIL", "arch"),
])
def test_item_type_is_classified_from_the_drawing_title(text, expected):
    item_type, matched = dp.classify_item_type(text)
    assert item_type == expected
    assert matched


def test_an_unrecognised_title_falls_back_to_wall_and_reports_no_match():
    """`matched` is what tells the UI the type was defaulted rather than read, so the PM
    knows to check it."""
    import calculators as calc

    item_type, matched = dp.classify_item_type("SHEET 3 OF 7")

    assert item_type == calc.DEFAULT_ITEM_TYPE == "wall"
    assert matched is None


# --- OCR availability is reported honestly ----------------------------------------------

def test_ocr_status_always_reports_a_backend_field():
    """The estimator branches on this, and a raster page with no OCR must be able to say so
    rather than silently producing zero dimensions."""
    status = dp.ocr_status()
    assert "available" in status
    assert "backend" in status
    if not status["available"]:
        # Without a hint the PM has no way to know why a PNG produced nothing.
        assert status.get("hint")


def test_parse_files_reports_unreadable_files_instead_of_raising(tmp_path):
    """One bad file in a batch must not take the whole import down."""
    bogus = tmp_path / "not-a-drawing.pdf"
    bogus.write_text("this is not a pdf")

    result = dp.parse_files([str(bogus)])

    assert result["success"] is True
    assert result["drawings"] == []
    assert result["skipped"], "an unreadable file should be reported as skipped"


def test_parse_files_ignores_unsupported_extensions(tmp_path):
    doc = tmp_path / "notes.txt"
    doc.write_text("hello")

    result = dp.parse_files([str(doc)])

    assert result["drawings"] == []
    assert result["skipped"]
