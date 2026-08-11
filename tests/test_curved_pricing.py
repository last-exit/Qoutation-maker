"""Pricing of curved, ring and arched elements.

The point of these tests is not that curves cost *something* — it is that they cost more
than the flat panel the old model would have quoted, that the reason is visible in the
`basis` string a PM reads, and that a flat item still prices exactly as it always did.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import calculators  # noqa: E402
import curves  # noqa: E402


def flat_wall(**overrides):
    spec = {"item_type": "wall", "length_m": 3.0, "height_m": 2.4, "shape": "flat"}
    spec.update(overrides)
    return spec


class TestFlatIsUnchanged:
    def test_an_item_with_no_shape_behaves_exactly_as_a_flat_one(self):
        """Existing quotations must re-price to the same number after this feature."""
        without_shape = calculators.compute_item_boq(
            {"item_type": "wall", "length_m": 3.0, "height_m": 2.4})
        explicitly_flat = calculators.compute_item_boq(flat_wall())
        assert without_shape["unit_factory_cost"] == explicitly_flat["unit_factory_cost"]
        assert without_shape["net_area_m2"] == explicitly_flat["net_area_m2"]

    def test_a_flat_wall_reports_its_run_as_its_length(self):
        result = calculators.compute_item_boq(flat_wall())
        assert result["developed_run_m"] == 3.0


class TestCurvedWall:
    def test_a_curved_wall_costs_more_than_the_flat_wall_of_the_same_width(self):
        flat = calculators.compute_item_boq(flat_wall())
        curved = calculators.compute_item_boq(flat_wall(shape="curved", sagitta_m=0.4))
        assert curved["net_area_m2"] > flat["net_area_m2"]
        assert curved["unit_factory_cost"] > flat["unit_factory_cost"]

    def test_the_clad_area_is_sized_on_arc_length_not_chord(self):
        curved = calculators.compute_item_boq(flat_wall(shape="curved", sagitta_m=0.4))
        expected_run = curves.arc_length_from_chord(3.0, 0.4)
        assert curved["developed_run_m"] == pytest.approx(round(expected_run, 3))
        assert expected_run > 3.0

    def test_the_basis_string_shows_the_curve_factor_so_a_pm_can_follow_it(self):
        curved = calculators.compute_item_boq(flat_wall(shape="curved", sagitta_m=0.4))
        carpentry = [l for l in curved["labor"] if l["trade"] == "carpentry"]
        assert carpentry, "curved work must still carry carpentry hours"
        assert "curved-work factor" in carpentry[0]["basis"]

    def test_a_curve_defaults_to_flexible_skins_rather_than_eighteen_mil_board(self):
        curved = calculators.compute_item_boq(flat_wall(shape="curved", sagitta_m=0.4))
        assert curved["substrate"] == "WD-MDF-06"
        assert curved["skin_layers"] >= 2

    def test_an_explicit_substrate_choice_beats_the_curved_default(self):
        """The estimator fills a blank; it never overrides the PM."""
        curved = calculators.compute_item_boq(
            flat_wall(shape="curved", sagitta_m=0.4, substrate="WD-PLY-18M"))
        assert curved["substrate"] == "WD-PLY-18M"

    def test_a_curve_with_no_stated_rise_refuses_to_price_instead_of_quoting_it_flat(self):
        """Silently pricing the chord is the under-quote this feature exists to stop."""
        result = calculators.compute_item_boq(flat_wall(shape="curved"))
        assert result["needs_dimensions"] is True
        assert "Curve rise" in result["dimension_message"]
        assert result["unit_factory_cost"] == 0.0

    def test_curved_framing_uses_closer_centres_than_a_flat_wall(self):
        flat_total, flat_detail = calculators.stud_linear_meters(flat_wall())
        curved_total, curved_detail = calculators.stud_linear_meters(
            flat_wall(shape="curved", sagitta_m=0.4))
        assert curved_detail["spacing_m"] < flat_detail["spacing_m"]
        assert curved_total > flat_total


class TestRingShelf:
    def ring(self, **overrides):
        spec = {"item_type": "wall", "shape": "ring", "outer_r_m": 0.55,
                "inner_r_m": 0.2, "faces": 8}
        spec.update(overrides)
        return spec

    def test_a_ring_is_priced_on_annular_area_per_shelf(self):
        result = calculators.compute_item_boq(self.ring())
        expected = curves.annulus_area(0.55, 0.2) * 8
        assert result["net_area_m2"] == pytest.approx(round(expected, 3), rel=1e-3)

    def test_a_ring_is_cut_from_ordinary_board_not_bent_skins(self):
        """A disc is sawn flat. Giving it a bent build-up swaps its carcass for skins.

        The board is whatever the sheet lists for shelving — WD-MDF-12 with the shipped
        card — not the flexible 6mm skin a curved wall gets, and it is a single layer.
        """
        result = calculators.compute_item_boq(self.ring())
        board = result["materials"][0]
        assert result["skin_layers"] == 1
        assert board["code"] != "WD-MDF-06", "a ring must not be built from bent skins"

    def test_ring_cutting_wastage_is_named_in_the_basis_rather_than_hidden(self):
        result = calculators.compute_item_boq(self.ring())
        board = [m for m in result["materials"] if m["code"] == result["substrate"]]
        assert board and "ring cutting wastage" in board[0]["basis"]

    def test_a_ring_needs_only_its_radius_not_a_length_and_height(self):
        result = calculators.compute_item_boq(self.ring())
        assert result["needs_dimensions"] is False

    def test_a_ring_with_no_radius_asks_for_one(self):
        result = calculators.compute_item_boq(self.ring(outer_r_m=0))
        assert result["needs_dimensions"] is True
        assert "Outer radius" in result["dimension_message"]

    def test_a_ring_is_not_framed_as_a_stud_wall(self):
        """Inventing a carcass the drawing never described would be a fabricated cost."""
        total, _ = calculators.stud_linear_meters(self.ring())
        assert total == 0.0

    def test_edge_banding_is_left_off_the_bill_when_no_product_is_configured(self):
        result = calculators.compute_item_boq(self.ring())
        codes = [m["code"] for m in result["materials"]]
        assert all(not c.startswith("EDGE") for c in codes)


class TestArch:
    def test_an_arched_head_develops_further_than_a_square_one(self):
        square = calculators.compute_item_boq(
            {"item_type": "arch", "length_m": 2.0, "height_m": 3.0, "shape": "flat"})
        arched = calculators.compute_item_boq(
            {"item_type": "arch", "length_m": 2.0, "height_m": 3.0,
             "shape": "arch", "sagitta_m": 1.0})
        assert arched["net_area_m2"] != square["net_area_m2"]

    def test_an_arch_reports_the_shape_it_was_priced_as(self):
        arched = calculators.compute_item_boq(
            {"item_type": "arch", "length_m": 2.0, "height_m": 3.0,
             "shape": "arch", "sagitta_m": 1.0})
        assert arched["shape"] == "arch"
        assert "arc" in arched["shape_summary"]


class TestUnknownShape:
    def test_an_unrecognised_shape_falls_back_to_flat_rather_than_erroring(self):
        result = calculators.compute_item_boq(flat_wall(shape="banana"))
        assert result["shape"] == "flat"
        assert result["needs_dimensions"] is False
