"""Editable fabrication settings.

These constants drive every curved price, so the tests care about two things above all: a
bad value must never reach the arithmetic, and saving one must never cost the PM the
labour rates that live in the same file.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import shop_config  # noqa: E402


@pytest.fixture
def config_file(tmp_path):
    """A config file shaped like the real one, with labour rates already in it."""
    path = tmp_path / "estimator_config.json"
    path.write_text(json.dumps({
        "labor_rates": {"carpentry": 45.0, "painting": 38.0},
        "margin_pct": 35.0,
    }), encoding="utf-8")
    return path


class TestLoading:
    def test_a_missing_file_gives_defaults_rather_than_failing(self, tmp_path):
        values, problems = shop_config.load(tmp_path / "nothing.json")
        assert values["curved_skin_layers"] == 2
        assert problems == []

    def test_unreadable_json_falls_back_and_says_so(self, tmp_path):
        path = tmp_path / "broken.json"
        path.write_text("{not json", encoding="utf-8")
        values, problems = shop_config.load(path)
        assert values["curve_labour_factor"] == shop_config.DEFAULTS["curve_labour_factor"]["value"]
        assert problems and "unreadable" in problems[0]

    def test_a_configured_value_is_used(self, config_file):
        data = json.loads(config_file.read_text(encoding="utf-8"))
        data["fabrication"] = {"curve_labour_factor": 1.8}
        config_file.write_text(json.dumps(data), encoding="utf-8")
        values, _ = shop_config.load(config_file)
        assert values["curve_labour_factor"] == 1.8

    def test_nonsense_is_rejected_and_reported_not_used(self, config_file):
        """A stray string in the config must not become part of a price."""
        data = json.loads(config_file.read_text(encoding="utf-8"))
        data["fabrication"] = {"curve_labour_factor": "very curvy"}
        config_file.write_text(json.dumps(data), encoding="utf-8")
        values, problems = shop_config.load(config_file)
        assert values["curve_labour_factor"] == 1.45
        assert problems and "not a usable number" in problems[0]

    def test_an_out_of_range_value_is_clamped_rather_than_obeyed(self, config_file):
        data = json.loads(config_file.read_text(encoding="utf-8"))
        data["fabrication"] = {"curve_labour_factor": 500}
        config_file.write_text(json.dumps(data), encoding="utf-8")
        values, _ = shop_config.load(config_file)
        assert values["curve_labour_factor"] == 4.0

    def test_a_labour_factor_below_one_cannot_make_curves_cheaper_than_flat(self, config_file):
        data = json.loads(config_file.read_text(encoding="utf-8"))
        data["fabrication"] = {"curve_labour_factor": 0.2}
        config_file.write_text(json.dumps(data), encoding="utf-8")
        values, _ = shop_config.load(config_file)
        assert values["curve_labour_factor"] >= 1.0


class TestSaving:
    def test_saving_a_setting_keeps_the_labour_rates_in_the_same_file(self, config_file):
        """The fabrication block shares a file with the PM's labour rates."""
        shop_config.save({"curved_skin_layers": 3}, config_file)
        data = json.loads(config_file.read_text(encoding="utf-8"))
        assert data["labor_rates"]["carpentry"] == 45.0
        assert data["margin_pct"] == 35.0
        assert data["fabrication"]["curved_skin_layers"] == 3

    def test_saving_returns_what_was_actually_stored(self, config_file):
        values, problems = shop_config.save({"curved_stud_spacing_m": 0.3}, config_file)
        assert values["curved_stud_spacing_m"] == 0.3
        assert problems == []

    def test_an_unknown_setting_is_ignored_and_named(self, config_file):
        _, problems = shop_config.save({"nonsense_key": 1}, config_file)
        assert problems and "nonsense_key" in problems[0]

    def test_a_corrupt_file_is_kept_beside_the_rewrite(self, tmp_path):
        """Never silently destroy a PM's labour rates, even when the file is broken."""
        path = tmp_path / "estimator_config.json"
        path.write_text("{broken", encoding="utf-8")
        shop_config.save({"curved_skin_layers": 2}, path)
        assert (tmp_path / "estimator_config.json.corrupt").exists()


class TestDescribe:
    def test_every_field_is_offered_to_the_ui(self):
        described = shop_config.describe()
        keys = {f["key"] for f in described["fields"]}
        assert keys == set(shop_config.DEFAULTS)

    def test_guessed_defaults_are_flagged_as_unconfirmed(self):
        """A number this project invented must never look like the workshop's own."""
        described = shop_config.describe()
        assert "curve_labour_factor" in described["unconfirmed"]

    def test_a_value_taken_from_the_rate_card_is_not_flagged(self):
        described = shop_config.describe()
        assert "curved_substrate_code" not in described["unconfirmed"]
