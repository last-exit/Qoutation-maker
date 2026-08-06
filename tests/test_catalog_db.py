"""The catalog: uniqueness, and a lookup that can actually match a real quote line."""
import pytest


def test_same_description_upserts_instead_of_duplicating(temp_catalog):
    """Without this the lookup returned an arbitrary duplicate, so the cost behind a margin
    figure was nondeterministic."""
    first = temp_catalog.add_catalog_item("Pirate Ship", rate=100, cost_price=60)
    second = temp_catalog.add_catalog_item("Pirate  Ship!", rate=120, cost_price=70)

    assert first == second
    assert temp_catalog.count_items() == 1
    assert temp_catalog.find_catalog_item_by_description("Pirate Ship")["cost_price"] == 70


def test_exact_match(temp_catalog):
    temp_catalog.add_catalog_item("Pirate Ship", cost_price=60)
    match = temp_catalog.find_catalog_item_by_description("pirate ship")
    assert match["match"] == "exact"


def test_title_line_match_handles_real_quote_lines(temp_catalog):
    """Quote descriptions carry a spec block under the product name, which is why the old
    exact-equality lookup never matched and every quote recorded cost_price: None."""
    temp_catalog.add_catalog_item("Jungle Gym Playhouse", cost_price=2100)
    match = temp_catalog.find_catalog_item_by_description(
        "Jungle Gym Playhouse\n10m Height x 5m Length\n- Slide (yellow)"
    )
    assert match["match"] == "title"
    assert match["cost_price"] == 2100


def test_containment_match(temp_catalog):
    temp_catalog.add_catalog_item("Pirate Ship", cost_price=60)
    match = temp_catalog.find_catalog_item_by_description("Large Pirate Ship for beach event")
    assert match["match"] == "contains"


def test_very_short_entries_do_not_match_everything(temp_catalog):
    """A 3-character catalog name is contained in almost any description."""
    temp_catalog.add_catalog_item("Mat", cost_price=5)
    assert temp_catalog.find_catalog_item_by_description("Automatic gate installation") is None


def test_no_match_returns_none(temp_catalog):
    temp_catalog.add_catalog_item("Pirate Ship", cost_price=60)
    assert temp_catalog.find_catalog_item_by_description("Helicopter Rental") is None


def test_empty_description_is_rejected(temp_catalog):
    with pytest.raises(ValueError):
        temp_catalog.add_catalog_item("   ")


def test_update_can_clear_a_cost(temp_catalog):
    item_id = temp_catalog.add_catalog_item("Pirate Ship", cost_price=60)
    temp_catalog.update_catalog_item(item_id, cost_price="")
    assert temp_catalog.find_catalog_item_by_description("Pirate Ship")["cost_price"] is None


def test_update_leaves_cost_alone_when_not_supplied(temp_catalog):
    item_id = temp_catalog.add_catalog_item("Pirate Ship", cost_price=60)
    temp_catalog.update_catalog_item(item_id, rate=999)
    assert temp_catalog.find_catalog_item_by_description("Pirate Ship")["cost_price"] == 60


def test_renaming_keeps_the_normalized_key_in_sync(temp_catalog):
    item_id = temp_catalog.add_catalog_item("Pirate Ship", cost_price=60)
    temp_catalog.update_catalog_item(item_id, description="Galleon")
    assert temp_catalog.find_catalog_item_by_description("Galleon") is not None
    assert temp_catalog.find_catalog_item_by_description("Pirate Ship") is None


def test_legacy_duplicates_are_collapsed_by_migration(tmp_path, monkeypatch):
    """An existing install can already hold duplicates; the unique index cannot be built
    until they are merged, and a captured cost must not be lost in the process."""
    import sqlite3

    import catalog_db

    legacy = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(legacy))
    conn.execute("""CREATE TABLE catalog_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT, description TEXT NOT NULL, unit TEXT,
        rate REAL, cost_price REAL, category TEXT, created_at TEXT, updated_at TEXT)""")
    conn.execute("INSERT INTO catalog_items (description, rate, cost_price, updated_at) "
                 "VALUES ('Pirate Ship', 100, 55, '2026-01-01')")
    conn.execute("INSERT INTO catalog_items (description, rate, cost_price, updated_at) "
                 "VALUES ('Pirate Ship', 120, NULL, '2026-06-01')")
    conn.commit()
    conn.close()

    monkeypatch.setattr(catalog_db, "DB_FILE", str(legacy))
    catalog_db.init_db()

    assert catalog_db.count_items() == 1
    survivor = catalog_db.find_catalog_item_by_description("Pirate Ship")
    assert survivor["rate"] == 120, "the most recent row wins"
    assert survivor["cost_price"] == 55, "a cost from the older row is inherited, not lost"
