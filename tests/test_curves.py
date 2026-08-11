"""Curve geometry, checked against numbers you can work out by hand.

Every expected value here is derived from school geometry rather than from running the
code and pasting the answer, which is the only way these tests can catch a formula being
quietly wrong rather than merely changed.
"""

import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import curves  # noqa: E402


class TestArcLength:
    def test_a_quarter_circle_of_radius_two_is_half_pi_times_two(self):
        # Quarter of a circle: circumference 2*pi*r = 4*pi, so a quarter is pi.
        assert curves.arc_length(2.0, 90.0) == pytest.approx(math.pi)

    def test_a_full_turn_is_the_whole_circumference(self):
        assert curves.arc_length(1.5, 360.0) == pytest.approx(2 * math.pi * 1.5)

    def test_no_radius_gives_no_length_rather_than_an_error(self):
        assert curves.arc_length(0, 90) == 0.0
        assert curves.arc_length(None, None) == 0.0


class TestRadiusFromChordAndSagitta:
    def test_a_semicircle_recovers_its_own_radius(self):
        # A semicircle on a 2 m chord bulges 1 m, and its radius is 1 m.
        assert curves.radius_from_chord_and_sagitta(2.0, 1.0) == pytest.approx(1.0)

    def test_a_shallow_bow_recovers_the_textbook_radius(self):
        # r = c^2/(8h) + h/2 = 64/(8*1) + 0.5 = 8.5
        assert curves.radius_from_chord_and_sagitta(8.0, 1.0) == pytest.approx(8.5)

    def test_a_missing_rise_gives_no_radius(self):
        assert curves.radius_from_chord_and_sagitta(3.0, 0) == 0.0


class TestIncludedAngle:
    def test_a_semicircle_subtends_one_hundred_and_eighty_degrees(self):
        assert curves.included_angle_deg(2.0, 1.0, 1.0) == pytest.approx(180.0)

    def test_a_major_arc_is_reported_as_reflex_not_folded_back(self):
        """A curve bulging past its own centre must not read as its shallow twin.

        This is the trap the atan2 form exists to avoid: with asin, a sagitta of 1.5 m on a
        2 m chord comes back as an acute angle and halves the developed length.
        """
        radius = curves.radius_from_chord_and_sagitta(2.0, 1.5)
        angle = curves.included_angle_deg(2.0, radius, 1.5)
        assert angle > 180.0

    def test_a_chord_longer_than_the_diameter_clamps_instead_of_erroring(self):
        assert curves.included_angle_deg(10.0, 1.0) == 180.0


class TestArcLengthFromChord:
    def test_a_semicircle_develops_to_half_its_circumference(self):
        # 2 m chord, 1 m rise -> radius 1, half circumference = pi.
        assert curves.arc_length_from_chord(2.0, 1.0) == pytest.approx(math.pi, rel=1e-6)

    def test_a_curve_always_develops_longer_than_its_chord(self):
        assert curves.arc_length_from_chord(3.0, 0.4) > 3.0

    def test_no_rise_falls_back_to_the_chord_rather_than_inventing_a_curve(self):
        assert curves.arc_length_from_chord(3.0, 0) == 3.0

    def test_a_negligible_bow_is_treated_as_flat(self):
        """A rounded corner must not be priced as curved joinery."""
        assert curves.arc_length_from_chord(3.0, 0.0005) == 3.0


class TestAnnulus:
    def test_a_solid_disc_is_pi_r_squared(self):
        assert curves.annulus_area(1.0) == pytest.approx(math.pi)

    def test_a_ring_subtracts_its_hole(self):
        # pi * (2^2 - 1^2) = 3*pi
        assert curves.annulus_area(2.0, 1.0) == pytest.approx(3 * math.pi)

    def test_an_inner_radius_larger_than_the_outer_cannot_go_negative(self):
        assert curves.annulus_area(1.0, 5.0) == 0.0

    def test_a_ring_is_edged_on_both_circumferences(self):
        assert curves.annulus_edge_length(2.0, 1.0) == pytest.approx(
            2 * math.pi * 2.0 + 2 * math.pi * 1.0)

    def test_a_disc_is_edged_only_once(self):
        assert curves.annulus_edge_length(2.0) == pytest.approx(2 * math.pi * 2.0)


class TestArchBandRun:
    def test_a_semicircular_head_runs_further_than_a_square_one(self):
        """The old flat model used (2 x height) + opening. An arched head is longer."""
        opening, height = 2.0, 3.0
        square_headed = (2 * height) + opening
        arched = curves.arch_band_run(opening, height, sagitta_m=1.0)
        assert arched > 0
        # Legs shorten by the rise, but the head develops from 2.0 m to pi m.
        expected = 2 * (height - 1.0) + math.pi
        assert arched == pytest.approx(expected, rel=1e-6)
        assert arched != pytest.approx(square_headed)

    def test_an_unstated_rise_assumes_a_semicircle(self):
        run = curves.arch_band_run(2.0, 3.0)
        assert run == pytest.approx(2 * (3.0 - 1.0) + math.pi, rel=1e-6)

    def test_a_head_cannot_be_taller_than_the_portal(self):
        run = curves.arch_band_run(2.0, 1.0, sagitta_m=5.0)
        assert run == pytest.approx(math.pi, rel=1e-6)   # legs vanish, head remains


class TestShapeClassification:
    def test_a_ring_is_curved_but_never_bent(self):
        """A disc is sawn flat out of board; it must not get a bent skin build-up."""
        assert curves.is_curved("ring") is True
        assert curves.is_bent("ring") is False

    def test_a_curved_wall_is_both(self):
        assert curves.is_curved("curved") is True
        assert curves.is_bent("curved") is True

    def test_a_flat_panel_is_neither(self):
        assert curves.is_curved("flat") is False
        assert curves.is_bent("flat") is False


class TestDescribe:
    def test_a_ring_names_both_radii(self):
        text = curves.describe("ring", {"outer_r_m": 0.55, "inner_r_m": 0.2})
        assert "0.550" in text and "0.200" in text

    def test_an_arc_without_a_rise_says_so_rather_than_implying_one(self):
        assert "not stated" in curves.describe("curved", {})
