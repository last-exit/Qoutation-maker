"""The merged shape list and its migration from the old type+shape pair."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import calculators  # noqa: E402
import shapes  # noqa: E402


class TestNormalization:
    def test_a_merged_key_expands_to_its_legacy_pair(self):
        out = shapes.normalize({"shape": "wall_curved"})
        assert out["item_type"] == "wall"
        assert out["shape"] == "curved"
        assert out["shape_key"] == "wall_curved"

    def test_a_legacy_pair_is_left_untouched(self):
        out = shapes.normalize({"item_type": "counter", "shape": "flat"})
        assert out["item_type"] == "counter"
        assert out["shape"] == "flat"

    def test_a_square_headed_arch_is_not_forced_into_an_arched_head(self):
        """Legacy arch+flat is a square-headed portal with no merged key; it must survive."""
        out = shapes.normalize({"item_type": "arch", "shape": "flat"})
        assert out["shape"] == "flat"

    def test_an_unknown_shape_falls_back_to_a_flat_wall(self):
        assert shapes.key_of({"shape": "banana"}) == "wall_flat"


class TestMigrationPricesIdentically:
    def test_merged_curved_wall_matches_the_legacy_pair(self):
        merged = calculators.compute_item_boq(
            {"shape": "wall_curved", "length_m": 3.0, "height_m": 2.4, "sagitta_m": 0.4})
        legacy = calculators.compute_item_boq(
            {"item_type": "wall", "shape": "curved", "length_m": 3.0, "height_m": 2.4,
             "sagitta_m": 0.4})
        assert merged["unit_factory_cost"] == legacy["unit_factory_cost"]

    def test_merged_stage_matches_the_legacy_pair(self):
        merged = calculators.compute_item_boq(
            {"shape": "stage", "length_m": 6.0, "depth_m": 4.0})
        legacy = calculators.compute_item_boq(
            {"item_type": "stage", "length_m": 6.0, "depth_m": 4.0})
        assert merged["unit_factory_cost"] == legacy["unit_factory_cost"]


class TestDimensionFields:
    def test_a_ring_offers_radii_not_a_length(self):
        fields = [f for f, _ in shapes.dim_fields("ring")]
        assert "outer_r_m" in fields
        assert "length_m" not in fields

    def test_a_flat_wall_offers_no_curve_rise(self):
        fields = [f for f, _ in shapes.dim_fields("wall_flat")]
        assert "sagitta_m" not in fields

    def test_a_curved_wall_offers_a_curve_rise(self):
        fields = [f for f, _ in shapes.dim_fields("wall_curved")]
        assert "sagitta_m" in fields

    def test_the_options_payload_lists_all_seven_shapes(self):
        payload = shapes.options_payload()
        assert len(payload) == 7
        assert all("dims" in entry and entry["dims"] for entry in payload)
