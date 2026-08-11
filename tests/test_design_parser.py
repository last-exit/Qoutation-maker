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
    bogus.write_text("this is not a pdf", encoding="utf-8")

    result = dp.parse_files([str(bogus)])

    assert result["success"] is True
    assert result["drawings"] == []
    assert result["skipped"], "an unreadable file should be reported as skipped"


def test_parse_files_ignores_unsupported_extensions(tmp_path):
    doc = tmp_path / "notes.txt"
    doc.write_text("hello", encoding="utf-8")

    result = dp.parse_files([str(doc)])

    assert result["drawings"] == []
    assert result["skipped"]


# --- Labelled dimensions ----------------------------------------------------------------
#
# Draughtsmen routinely write one dimension against its own name rather than in an LxH
# callout ("RECEPTION COUNTER / 3600 x 1100 mm / DEPTH 600 mm"). Reading only the paired
# callouts discarded it, so a counter whose depth was stated plainly on the sheet still
# arrived with depth_m = 0 and had to be typed in by hand.

@pytest.mark.parametrize("text, field, expected_m", [
    ("DEPTH 600 mm", "depth_m", 0.6),
    ("DEPTH: 600mm", "depth_m", 0.6),
    ("depth = 600 mm", "depth_m", 0.6),
    ("HEIGHT 2400 mm", "height_m", 2.4),
    ("HT 2400", "height_m", 2.4),
    ("LENGTH 5000 mm", "length_m", 5.0),
    ("WIDTH 5000 mm", "length_m", 5.0),
])
def test_labelled_dimensions_are_read(text, field, expected_m):
    found = dp.extract_labelled_dimensions(text)
    assert found[field] == pytest.approx(expected_m)


def test_the_trailing_form_is_not_read_but_does_not_break():
    """"600 DEEP" is a real way to write it and is not supported — the label has to come
    first. Documented here so the limitation is a known gap rather than a surprise: the
    dimension is simply left for the PM, which the pricing guard already asks for."""
    assert dp.extract_labelled_dimensions("600 DEEP") == {}


def test_a_labelled_depth_fills_the_gap_a_paired_callout_leaves():
    assigned = {"length_m": 3.6, "height_m": 1.1, "depth_m": 0.0,
                "confidence": "medium", "source_text": "3600 x 1100 mm"}
    filled = dp._apply_labelled_dimensions("3600 x 1100 mm\nDEPTH 600 mm", assigned)

    assert filled == ["depth_m"]
    assert assigned["depth_m"] == pytest.approx(0.6)
    assert "labelled depth" in assigned["source_text"]


def test_a_measured_dimension_is_never_overwritten_by_a_label():
    """The paired callout is the stronger signal; labels only fill what is still zero."""
    assigned = {"length_m": 5.0, "height_m": 2.4, "depth_m": 0.0,
                "confidence": "medium", "source_text": "5000 x 2400"}
    dp._apply_labelled_dimensions("5000 x 2400\nHEIGHT 9999 mm", assigned)

    assert assigned["height_m"] == pytest.approx(2.4)


def test_board_thickness_is_not_mistaken_for_item_depth():
    """`THK 18` names the MDF, not how deep the counter is. Treating it as depth would
    quote a 4 m counter with an 18 mm worktop."""
    found = dp.extract_labelled_dimensions("MDF THK 18mm\nTHICKNESS 18")
    assert "depth_m" not in found


def test_the_first_mention_of_a_dimension_wins():
    found = dp.extract_labelled_dimensions("DEPTH 600 mm\nDEPTH 300 mm")
    assert found["depth_m"] == pytest.approx(0.6)


def test_a_counter_stating_its_depth_now_prices_end_to_end():
    """The whole point: this drawing used to stop at 'Enter Depth'."""
    import calculators as calc

    assigned = {"length_m": 3.6, "height_m": 1.1, "depth_m": 0.0,
                "confidence": "medium", "source_text": ""}
    dp._apply_labelled_dimensions("3600 x 1100 mm\nDEPTH 600 mm", assigned)

    spec = dict(assigned, item_type="counter", label="Reception counter", faces=1, quantity=1)
    boq = calc.compute_item_boq(spec)

    assert boq["needs_dimensions"] is False
    assert boq["factory_cost"] > 0


# --- Why a page produced nothing -----------------------------------------------------------
# One generic "drawing gave no usable value" hid the difference between a drawing with
# nothing on it and a machine with no OCR reader installed. The second is a pip install away
# from working, and a PM who is not told that retypes a whole deck by hand.

class TestReadStateMessaging:
    def test_a_missing_reader_says_so_and_gives_the_command(self):
        state = dp._read_state({"available": False, "backend": None,
                                "hint": "No OCR backend installed."})
        assert state == dp.READ_STATE_NO_READER
        message = dp.read_state_message(state)
        assert "pip install easyocr" in message
        assert "type the dimensions" in message.lower()

    def test_a_broken_reader_is_told_apart_from_a_missing_one(self):
        state = dp._read_state({"available": False, "backend": "easyocr",
                                "hint": "OCR backend failed to start: model download"})
        assert state == dp.READ_STATE_READER_FAILED
        assert "could not start" in dp.read_state_message(state, "model download")

    def test_a_working_reader_that_found_nothing_blames_neither(self):
        state = dp._read_state({"available": True, "backend": "easyocr"})
        assert state == dp.READ_STATE_NOTHING_FOUND
        message = dp.read_state_message(state)
        assert "install" not in message.lower()

    def test_the_page_carries_the_reason_it_could_not_read(self, tmp_path):
        """A blank PDF page has no text; the page must say why, not just stay silent."""
        import fitz
        doc = fitz.open()
        doc.new_page(width=300, height=200)
        target = str(tmp_path / "blank.pdf")
        doc.save(target)
        doc.close()

        page = dp.parse_files([target])["drawings"][0]
        assert page["read_state"] != dp.READ_STATE_OK
        assert page["read_message"]
