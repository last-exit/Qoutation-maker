"""Line geometry, page classification, and splitting a sheet into elements.

The decomposition tests build a real PDF with real vector linework rather than mocking the
geometry, because the thing being tested is precisely whether a drawing's own lines can be
turned back into the objects they describe.
"""

import os
import sys

import fitz
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import design_parser as dp  # noqa: E402
import page_geometry as pg  # noqa: E402


# --- Fixtures ---------------------------------------------------------------------------

def _elevation(path, elements):
    """A flat elevation carrying one dimensioned rectangle per entry in `elements`.

    Each entry is (x0, y0, x1, y1, width_label, height_label, name).
    """
    doc = fitz.open()
    page = doc.new_page(width=600, height=400)
    for x0, y0, x1, y1, width_label, height_label, name in elements:
        page.draw_rect(fitz.Rect(x0, y0, x1, y1), width=1.2)
        page.draw_line(fitz.Point(x0, y0 - 20), fitz.Point(x1, y0 - 20), width=1.0)
        page.insert_text(fitz.Point(x0 + 10, y0 - 25), width_label, fontsize=9)
        page.draw_line(fitz.Point(x0 - 20, y0), fitz.Point(x0 - 20, y1), width=1.0)
        page.insert_text(fitz.Point(max(2, x0 - 50), (y0 + y1) / 2), height_label,
                         fontsize=9)
        page.insert_text(fitz.Point(x0 + 10, y1 + 20), name, fontsize=10)
    doc.save(str(path))
    doc.close()
    return str(path)


TOWER = (60, 80, 170, 320, "110.0 cm", "240.0 cm", "Display Tower")
PORTAL = (360, 90, 485, 320, "125.0 cm", "230.0 cm", "Entrance Arch")


# --- Segment primitives -------------------------------------------------------------------

class TestSegments:
    def test_a_horizontal_line_is_recognised_as_horizontal(self):
        seg = pg._segment(0, 10, 100, 10)
        assert seg["axis"] == "h"
        assert seg["length"] == pytest.approx(100.0)

    def test_a_vertical_line_is_recognised_as_vertical(self):
        assert pg._segment(10, 0, 10, 80)["axis"] == "v"

    def test_a_diagonal_is_marked_oblique_rather_than_forced_onto_an_axis(self):
        assert pg._segment(0, 0, 100, 100)["axis"] == "o"

    def test_vector_linework_is_read_off_a_pdf_page(self, tmp_path):
        path = _elevation(tmp_path / "one.pdf", [TOWER])
        doc = fitz.open(path)
        try:
            segments = pg.segments_from_pdf_page(doc.load_page(0))
        finally:
            doc.close()
        assert len(segments) >= 4
        assert any(s["axis"] == "h" for s in segments)
        assert any(s["axis"] == "v" for s in segments)


class TestPageClassification:
    def test_an_axis_aligned_drawing_reads_as_flat(self):
        segments = ([pg._segment(0, y, 500, y) for y in range(0, 200, 20)]
                    + [pg._segment(x, 0, x, 300) for x in range(0, 200, 20)])
        kind, detail = pg.classify_page(segments)
        assert kind == "flat"
        assert detail["axis_aligned_ratio"] > 0.9

    def test_a_page_of_receding_edges_reads_as_perspective(self):
        segments = [pg._segment(0, 0, 100 + i, 60 + i * 3) for i in range(20)]
        kind, _ = pg.classify_page(segments)
        assert kind == "perspective"

    def test_too_little_linework_falls_back_to_the_conservative_pipeline(self):
        """Guessing 'flat' on an unreadable page would licence page-wide scaling."""
        kind, detail = pg.classify_page([pg._segment(0, 0, 50, 0)])
        assert kind == "perspective"
        assert "too little" in detail["reason"]


class TestMeasuredSpans:
    def test_a_callout_is_tied_to_the_line_it_sits_on(self):
        segments = [pg._segment(100, 50, 300, 50)]
        tokens = [{"text": "2.0 m", "meters": 2.0, "bbox": (180, 35, 220, 48)}]
        spans, unattached = pg.measure(tokens, segments, (600, 400))
        assert not unattached
        assert len(spans) == 1
        assert spans[0]["axis"] == "h"
        # 200 px of line describing 2 m of object.
        assert spans[0]["px_per_m"] == pytest.approx(100.0)

    def test_a_callout_with_no_line_near_it_is_reported_not_guessed(self):
        segments = [pg._segment(100, 50, 300, 50)]
        tokens = [{"text": "2.0 m", "meters": 2.0, "bbox": (10, 380, 50, 395)}]
        spans, unattached = pg.measure(tokens, segments, (600, 400))
        assert spans == []
        assert len(unattached) == 1

    def test_page_scale_takes_the_median_so_one_misread_cannot_drag_it(self):
        spans = [{"px_per_m": 100.0}, {"px_per_m": 102.0}, {"px_per_m": 99.0},
                 {"px_per_m": 600.0}]
        scale, outliers = pg.page_scale(spans)
        assert scale == pytest.approx(101.0, abs=2.0)
        assert len(outliers) == 1
        assert outliers[0]["px_per_m"] == 600.0


class TestClustering:
    def test_overlapping_spans_describe_one_object(self):
        spans = [
            {"bbox": (0, 0, 100, 10), "axis": "h", "value_m": 1.0, "px_per_m": 100,
             "token": "1 m"},
            {"bbox": (0, 0, 10, 100), "axis": "v", "value_m": 2.0, "px_per_m": 100,
             "token": "2 m"},
        ]
        clusters = pg.cluster(spans)
        assert len(clusters) == 1
        assert len(clusters[0]["spans"]) == 2

    def test_spans_far_apart_describe_different_objects(self):
        spans = [
            {"bbox": (0, 0, 50, 10), "axis": "h", "value_m": 1.0, "px_per_m": 100,
             "token": "1 m"},
            {"bbox": (500, 300, 550, 310), "axis": "h", "value_m": 2.0, "px_per_m": 100,
             "token": "2 m"},
        ]
        assert len(pg.cluster(spans)) == 2


# --- End to end -----------------------------------------------------------------------------

class TestPageDecomposition:
    def test_a_sheet_with_two_objects_yields_two_items_not_one(self, tmp_path):
        """The original failure: eight elements on a page collapsed into a single row."""
        path = _elevation(tmp_path / "two.pdf", [TOWER, PORTAL])
        page = dp.parse_files([path])["drawings"][0]
        assert len(page["elements"]) == 2

    def test_each_item_gets_the_dimensions_that_belong_to_it(self, tmp_path):
        path = _elevation(tmp_path / "two.pdf", [TOWER, PORTAL])
        page = dp.parse_files([path])["drawings"][0]
        by_label = {e["label"]: e for e in page["elements"]}
        assert by_label["Display Tower"]["length_m"] == pytest.approx(1.10)
        assert by_label["Display Tower"]["height_m"] == pytest.approx(2.40)
        assert by_label["Entrance Arch"]["length_m"] == pytest.approx(1.25)
        assert by_label["Entrance Arch"]["height_m"] == pytest.approx(2.30)

    def test_an_item_is_typed_from_its_own_label_not_the_sheets_other_labels(self, tmp_path):
        """A tower beside an 'Entrance Arch' label must not itself become an arch."""
        path = _elevation(tmp_path / "two.pdf", [TOWER, PORTAL])
        page = dp.parse_files([path])["drawings"][0]
        by_label = {e["label"]: e for e in page["elements"]}
        assert by_label["Entrance Arch"]["item_type"] == "arch"
        assert by_label["Display Tower"]["item_type"] != "arch"

    def test_an_elevation_is_classified_as_flat(self, tmp_path):
        path = _elevation(tmp_path / "two.pdf", [TOWER, PORTAL])
        page = dp.parse_files([path])["drawings"][0]
        assert page["page_kind"] == "flat"

    def test_every_item_carries_a_box_so_the_ui_can_point_at_it(self, tmp_path):
        path = _elevation(tmp_path / "two.pdf", [TOWER, PORTAL])
        page = dp.parse_files([path])["drawings"][0]
        assert all(e["bbox_px"] for e in page["elements"])

    def test_each_dimension_records_which_callout_it_came_from(self, tmp_path):
        path = _elevation(tmp_path / "two.pdf", [TOWER, PORTAL])
        page = dp.parse_files([path])["drawings"][0]
        for element in page["elements"]:
            assert element["provenance"]
            assert all("token" in p for p in element["provenance"])

    def test_a_page_with_no_attachable_dimensions_still_parses_as_one_item(self, tmp_path):
        """Decomposition adds items; it must never leave a sheet with none."""
        doc = fitz.open()
        page = doc.new_page(width=400, height=300)
        page.insert_text(fitz.Point(50, 50), "Feature Wall 3000 x 2400", fontsize=11)
        target = str(tmp_path / "textonly.pdf")
        doc.save(target)
        doc.close()

        parsed = dp.parse_files([target])["drawings"][0]
        assert len(parsed["elements"]) == 1
        assert parsed["elements"][0]["length_m"] > 0


class TestCutoutsSurviveDecomposition:
    def test_an_opening_is_kept_and_flagged_rather_than_dropped(self, tmp_path):
        """Cutouts are found against the sheet, not against one element.

        Splitting the page must not lose them: a dropped TV recess silently removes a real
        deduction and the quote goes out high with nothing to show why.
        """
        doc = fitz.open()
        page = doc.new_page(width=600, height=400)
        x0, y0, x1, y1 = 60, 80, 170, 320
        page.draw_rect(fitz.Rect(x0, y0, x1, y1), width=1.2)
        page.draw_line(fitz.Point(x0, y0 - 20), fitz.Point(x1, y0 - 20), width=1.0)
        page.insert_text(fitz.Point(x0 + 10, y0 - 25), "110.0 cm", fontsize=9)
        page.draw_line(fitz.Point(x0 - 20, y0), fitz.Point(x0 - 20, y1), width=1.0)
        page.insert_text(fitz.Point(2, (y0 + y1) / 2), "240.0 cm", fontsize=9)
        page.insert_text(fitz.Point(x0 + 10, y1 + 20), "Display Tower", fontsize=10)
        page.insert_text(fitz.Point(250, 200), "WINDOW 600 x 400", fontsize=9)
        target = str(tmp_path / "cutout.pdf")
        doc.save(target)
        doc.close()

        parsed = dp.parse_files([target])["drawings"][0]
        carried = [c for e in parsed["elements"] for c in (e.get("cutouts") or [])]
        assert carried, "the opening must survive decomposition"
        assert any("not tied to one item" in w for w in parsed["warnings"])


class TestReconciliation:
    def test_the_same_object_on_two_sheets_is_quoted_once(self, tmp_path):
        """Splitting pages without this turns a 25-page deck into a systematic over-quote."""
        first = _elevation(tmp_path / "a.pdf", [TOWER])
        second = _elevation(tmp_path / "b.pdf", [TOWER])
        drawings = dp.parse_files([first, second])["drawings"]

        included = [e for page in drawings for e in page["elements"] if e["include"]]
        excluded = [e for page in drawings for e in page["elements"] if not e["include"]]
        assert len(included) == 1
        assert len(excluded) == 1
        assert excluded[0]["duplicate_of"]["file"].endswith("a.pdf")

    def test_a_duplicate_is_switched_off_rather_than_deleted(self, tmp_path):
        first = _elevation(tmp_path / "a.pdf", [TOWER])
        second = _elevation(tmp_path / "b.pdf", [TOWER])
        drawings = dp.parse_files([first, second])["drawings"]
        # Still present on its own page, so the PM can turn it back on.
        assert len(drawings[1]["elements"]) == 1

    def test_two_genuinely_different_objects_are_both_quoted(self, tmp_path):
        first = _elevation(tmp_path / "a.pdf", [TOWER])
        second = _elevation(tmp_path / "b.pdf", [PORTAL])
        drawings = dp.parse_files([first, second])["drawings"]
        included = [e for page in drawings for e in page["elements"] if e["include"]]
        assert len(included) == 2


class TestReliabilityFixes:
    def test_the_image_border_is_not_counted_as_flat_linework(self):
        """A perspective render sits inside a rectangular image; that rectangle must not
        drag the page over the line into 'flat'."""
        page = (1000, 700)
        border = [
            pg._segment(0, 0, 1000, 0), pg._segment(0, 700, 1000, 700),
            pg._segment(0, 0, 0, 700), pg._segment(1000, 0, 1000, 700),
        ]
        receding = [pg._segment(100, 100, 300 + i * 20, 180 + i * 30) for i in range(12)]
        kind, detail = pg.classify_page(border + receding, page_size=page)
        assert kind == "perspective"

    def test_an_elevation_still_reads_as_flat_after_border_removal(self):
        page = (1000, 700)
        border = [pg._segment(0, 0, 1000, 0), pg._segment(0, 700, 1000, 700)]
        interior = ([pg._segment(200, y, 700, y) for y in range(150, 550, 40)]
                    + [pg._segment(x, 150, x, 550) for x in range(200, 600, 40)])
        kind, _ = pg.classify_page(border + interior, page_size=page)
        assert kind == "flat"


class TestJunkLabelsRejected:
    def test_ocr_noise_is_not_used_as_an_item_name(self, tmp_path):
        r"""OCR noise and a bare dimension are meaningless names; the sheet title stands in."""
        doc = fitz.open()
        page = doc.new_page(width=500, height=360)
        page.insert_text(fitz.Point(60, 40), "Reception Counter", fontsize=13)
        page.insert_text(fitz.Point(60, 300), "—=s\\", fontsize=11)
        page.insert_text(fitz.Point(200, 300), "50.0cm", fontsize=11)
        target = str(tmp_path / "junk.pdf")
        doc.save(target)
        doc.close()

        page_out = dp.parse_files([target])["drawings"][0]
        for element in page_out["elements"]:
            assert "=s" not in element["label"]
            assert element["label"] != "50.0cm"


class TestIncrementalImport:
    """Pages are parsed one at a time so each appears as it is read. The result must match
    a single-shot parse exactly, or the fast UI would be quietly quoting something else."""

    def test_page_count_is_known_before_parsing(self, tmp_path):
        path = _elevation(tmp_path / "deck.pdf", [TOWER, PORTAL])
        assert dp.page_count(path) == 1

    def test_a_slice_returns_only_that_page(self, tmp_path):
        path = _elevation(tmp_path / "one.pdf", [TOWER])
        result = dp.parse_page_range(path, 0, 1)
        assert result["success"] and len(result["drawings"]) == 1

    def test_incremental_matches_a_single_shot_parse(self, tmp_path):
        path = _elevation(tmp_path / "two.pdf", [TOWER, PORTAL])

        incremental = []
        for index in range(dp.page_count(path)):
            incremental.extend(dp.parse_page_range(path, index, 1)["drawings"])
        dp.reconcile(incremental)

        one_shot = dp.parse_files([path])["drawings"]

        def signature(pages):
            return [(p["page_number"], e["label"], e["length_m"], e["height_m"],
                     e["include"]) for p in pages for e in p["elements"]]

        assert signature(incremental) == signature(one_shot)

    def test_a_missing_file_reports_rather_than_raising(self, tmp_path):
        result = dp.parse_page_range(str(tmp_path / "nope.pdf"), 0, 1)
        assert result["success"] is False and result["drawings"] == []
