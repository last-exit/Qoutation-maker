"""Sheet-driven material resolution.

The estimator no longer names materials in code; it scores the rate card's own Category,
Unit and Usage columns. These tests pin two things: that the shipped sheet resolves each
role to the row a joiner would expect, and that the resolution is deterministic and refuses
to invent a material when the sheet has none.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import materials  # noqa: E402
import rate_card  # noqa: E402


def card():
    return rate_card.get_rate_card()


class _FakeItem:
    def __init__(self, code, category, unit, usage, cost, description=""):
        self.code = code
        self.category = category
        self.unit = unit
        self.usage = usage
        self.avg_cost = cost
        self.description = description or code


class _FakeCard:
    """A minimal stand-in so a test can control exactly which rows exist."""
    def __init__(self, items):
        self.items = {i.code: i for i in items}

    def has(self, code):
        return code in self.items

    def get(self, code):
        return self.items[code]


class TestShippedSheet:
    def test_a_flat_wall_gets_standard_structural_board(self):
        assert materials.resolve(card(), materials.SUBSTRATE_QUERIES["wall_flat"])["code"] == "WD-MDF-18"

    def test_a_curved_wall_gets_the_flexible_cladding_board(self):
        assert materials.resolve(card(), materials.SUBSTRATE_QUERIES["wall_curved"])["code"] == "WD-MDF-06"

    def test_a_stage_gets_structural_plywood_not_mdf(self):
        assert materials.resolve(card(), materials.SUBSTRATE_QUERIES["stage"])["code"] == "WD-PLY-18M"

    def test_a_ring_gets_a_lightweight_shelving_board(self):
        assert materials.resolve(card(), materials.SUBSTRATE_QUERIES["ring"])["code"] == "WD-MDF-12"

    def test_light_framing_and_heavy_framing_are_told_apart(self):
        assert materials.resolve(card(), materials.FRAMING_QUERIES["light"])["code"] == "WD-FRM-2X2"
        assert materials.resolve(card(), materials.FRAMING_QUERIES["heavy"])["code"] == "WD-FRM-2X4"

    def test_every_finish_role_resolves(self):
        for role, query in materials.FINISH_QUERIES.items():
            assert materials.resolve(card(), query) is not None, role

    def test_a_substrate_query_never_returns_a_framing_piece(self):
        """The unit filter is what stops a Sheet query picking a stud."""
        for key in materials.SUBSTRATE_QUERIES:
            resolved = materials.resolve(card(), materials.SUBSTRATE_QUERIES[key])
            assert resolved["unit"].lower() == "sheet"


class TestScoring:
    def test_category_is_a_hard_filter(self):
        c = _FakeCard([
            _FakeItem("A", "Hardware", "Box", "assembly framing", 5),
            _FakeItem("B", "Wood & Boards", "Sheet", "structural walls", 60),
        ])
        q = materials.Query("Wood & Boards", "Sheet", prefer=("structural",))
        assert materials.resolve(c, q)["code"] == "B"

    def test_a_tie_breaks_to_the_cheaper_row_then_the_code(self):
        """Determinism: two equally-suitable rows must resolve the same way every run."""
        c = _FakeCard([
            _FakeItem("Z-CHEAP", "Wood & Boards", "Sheet", "structural walls", 40),
            _FakeItem("A-DEAR", "Wood & Boards", "Sheet", "structural walls", 80),
        ])
        q = materials.Query("Wood & Boards", "Sheet", prefer=("structural",))
        assert materials.resolve(c, q)["code"] == "Z-CHEAP"

    def test_avoid_keywords_push_a_row_down(self):
        c = _FakeCard([
            _FakeItem("PLAIN", "Wood & Boards", "Sheet", "structural walls", 60),
            _FakeItem("CURVY", "Wood & Boards", "Sheet", "structural curved walls", 30),
        ])
        q = materials.Query("Wood & Boards", "Sheet", prefer=("structural",), avoid=("curved",))
        assert materials.resolve(c, q)["code"] == "PLAIN"

    def test_no_candidate_returns_none_rather_than_a_wrong_material(self):
        c = _FakeCard([_FakeItem("X", "Hardware", "Box", "screws", 5)])
        q = materials.Query("Wood & Boards", "Sheet", prefer=("structural",))
        assert materials.resolve(c, q) is None

    def test_resolution_is_cached_per_card(self):
        c = card()
        first = materials.resolve(c, materials.SUBSTRATE_QUERIES["wall_flat"])
        second = materials.resolve(c, materials.SUBSTRATE_QUERIES["wall_flat"])
        assert first is second
