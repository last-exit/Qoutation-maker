"""Corrections — specifically that they no longer freeze fields the PM never touched.

The bug these cover: every review action used to snapshot rate, unit and venue together, and
the re-index blindly re-applied all three. Setting a venue in bulk, or merely dismissing a
flag, therefore pinned that item's price permanently — a later price change in the source
spreadsheet could never reach the app again.
"""


def parsed_item(rate=500.0, unit="Pcs", venue="Venue Unspecified"):
    return {
        "file_name": "Cost Sheet.xlsx",
        "original_description": "Pirate Ship",
        "historical_rate": rate,
        "unit": unit,
        "venue": venue,
        "rate_confidence": "low",
        "venue_confidence": "low",
        "needs_review": True,
        "flag_reason": "unverified",
    }


def test_venue_only_correction_does_not_pin_the_rate(temp_corrections):
    temp_corrections.save_correction(
        "Cost Sheet.xlsx", "Pirate Ship", venue="Al Barsha", corrected_fields=["venue"]
    )
    fix = temp_corrections.get_all_corrections()[("Cost Sheet.xlsx", "pirate ship")]

    # The source file has since been re-priced from 500 to 750.
    item = temp_corrections.apply_correction(parsed_item(rate=750.0), fix)

    assert item["venue"] == "Al Barsha"
    assert item["historical_rate"] == 750.0, "a venue fix must not freeze the price"


def test_dismissal_pins_nothing_but_clears_the_flag(temp_corrections):
    temp_corrections.save_correction(
        "Cost Sheet.xlsx", "Pirate Ship", rate=0.0, unit="Pcs", venue="Al Barsha",
        corrected_fields=[],
    )
    fix = temp_corrections.get_all_corrections()[("Cost Sheet.xlsx", "pirate ship")]
    item = temp_corrections.apply_correction(parsed_item(rate=750.0, venue="Kite Beach"), fix)

    assert item["needs_review"] is False
    assert item["historical_rate"] == 750.0
    assert item["venue"] == "Kite Beach"


def test_rate_correction_is_reapplied(temp_corrections):
    temp_corrections.save_correction(
        "Cost Sheet.xlsx", "Pirate Ship", rate=1234.0, corrected_fields=["rate"]
    )
    fix = temp_corrections.get_all_corrections()[("Cost Sheet.xlsx", "pirate ship")]
    item = temp_corrections.apply_correction(parsed_item(rate=500.0), fix)

    assert item["historical_rate"] == 1234.0
    assert item["rate_confidence"] == "high"
    assert item["needs_review"] is False


def test_later_correction_adds_to_pinned_fields(temp_corrections):
    """Fixing a venue today must not un-pin a rate corrected last month."""
    temp_corrections.save_correction(
        "Cost Sheet.xlsx", "Pirate Ship", rate=1234.0, corrected_fields=["rate"]
    )
    temp_corrections.save_correction(
        "Cost Sheet.xlsx", "Pirate Ship", venue="Kite Beach", corrected_fields=["venue"]
    )
    fix = temp_corrections.get_all_corrections()[("Cost Sheet.xlsx", "pirate ship")]

    assert set(fix["corrected_fields"]) == {"rate", "venue"}
    item = temp_corrections.apply_correction(parsed_item(rate=500.0), fix)
    assert item["historical_rate"] == 1234.0
    assert item["venue"] == "Kite Beach"


def test_lookup_key_is_case_insensitive(temp_corrections):
    temp_corrections.save_correction(
        "Cost Sheet.xlsx", "PIRATE SHIP", rate=99.0, corrected_fields=["rate"]
    )
    assert ("Cost Sheet.xlsx", "pirate ship") in temp_corrections.get_all_corrections()


def test_unknown_field_names_are_ignored(temp_corrections):
    """A typo'd or renamed field must not silently pin something unexpected."""
    temp_corrections.save_correction(
        "Cost Sheet.xlsx", "Pirate Ship", rate=1.0, corrected_fields=["rate", "sabotage"]
    )
    fix = temp_corrections.get_all_corrections()[("Cost Sheet.xlsx", "pirate ship")]
    assert fix["corrected_fields"] == ["rate"]


def test_delete_lets_the_item_reparse(temp_corrections):
    temp_corrections.save_correction(
        "Cost Sheet.xlsx", "Pirate Ship", rate=1234.0, corrected_fields=["rate"]
    )
    assert temp_corrections.delete_correction("Cost Sheet.xlsx", "Pirate Ship") == 1
    assert temp_corrections.get_all_corrections() == {}


def test_legacy_rows_backfill_without_pinning_a_zero_rate(tmp_path, monkeypatch):
    """A pre-existing row with rate 0 is the signature of the old snapshot bug, not an edit.

    Pinning it would permanently suppress the "missing unit rate" flag on a broken item.
    """
    import sqlite3

    import corrections_db

    legacy = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(legacy))
    conn.execute("""CREATE TABLE corrections (
        file_name TEXT NOT NULL, original_description TEXT NOT NULL, rate REAL, unit TEXT,
        venue TEXT, corrected_at TEXT, PRIMARY KEY (file_name, original_description))""")
    conn.execute("INSERT INTO corrections VALUES ('a.xlsx','transport',0.0,'Pcs','Al Barsha','2026-01-01')")
    conn.execute("INSERT INTO corrections VALUES ('b.xlsx','pirate ship',4200.0,'Pcs','Kite Beach','2026-01-01')")
    conn.commit()
    conn.close()

    monkeypatch.setattr(corrections_db, "DB_FILE", str(legacy))
    corrections_db.init_db()
    fixes = corrections_db.get_all_corrections()

    assert set(fixes[("a.xlsx", "transport")]["corrected_fields"]) == {"unit", "venue"}
    assert set(fixes[("b.xlsx", "pirate ship")]["corrected_fields"]) == {"rate", "unit", "venue"}
