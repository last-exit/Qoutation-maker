"""Contract tests between app.js and QuotationApi.

These exist because a green test suite is exactly what let a real breakage ship. Making
`get_history` omit line items was a good change on its own terms and had a passing test —
but `app.js` rendered a per-quote line count from `q.items.length`, so the whole Invoices
table died on `undefined`. Nothing in the Python suite could see that, because nothing in
the Python suite knew what the frontend reads.

So these tests read `app.js` itself and check two things:

  1. Every `api().method(...)` the frontend calls exists on QuotationApi.
  2. Every field the list-rendering code reads is actually present in the response.

They are deliberately coarse. They will not catch a wrong value, only a missing one — which
is the failure mode that takes a whole screen down rather than showing one wrong number.
"""
import inspect
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP_JS = (ROOT / "app.js").read_text()


@pytest.fixture(scope="module")
def api_class():
    import app
    return app.QuotationApi


def called_methods():
    return set(re.findall(r"api\(\)\.([a-z_]+)\(", APP_JS))


def test_every_method_the_frontend_calls_exists(api_class):
    """A renamed or removed backend method shows up as a silent no-op in the UI."""
    available = {
        name for name, _ in inspect.getmembers(api_class, inspect.isfunction)
        if not name.startswith("_")
    }
    missing = sorted(called_methods() - available)
    assert not missing, f"app.js calls methods that no longer exist: {missing}"


def test_frontend_calls_are_not_empty():
    """Guards the regex above: if it silently matched nothing, the test would pass vacuously."""
    assert len(called_methods()) > 20


# --- Response shape -------------------------------------------------------------------

@pytest.fixture
def api(tmp_path, monkeypatch):
    """A QuotationApi on throwaway stores, with one saved quotation to render."""
    import app
    import catalog_db
    import corrections_db
    import db
    import history_db
    import image_store

    monkeypatch.setattr(app, "DB_PATH", str(tmp_path / "chroma"))
    monkeypatch.setattr(image_store, "IMAGE_DIR", tmp_path / "images")
    monkeypatch.setattr(db, "BACKUP_DIR", tmp_path / "backups")
    for module, name in ((history_db, "history.db"), (catalog_db, "catalog.db"),
                         (corrections_db, "corrections.db")):
        monkeypatch.setattr(module, "DB_FILE", str(tmp_path / name))
        module.init_db()

    history_db.save_quotation_history({
        "client_name": "Acme360", "client_phone": "0501234567", "venue": "Kite Beach",
        "quote_date": "2026-08-01", "quote_number": "Q-1",
        "items": [{"description": "Pirate Ship", "qty": 1, "rate": 500.0},
                  {"description": "Delivery", "qty": 1, "rate": 50.0}],
        "subtotal": 550.0, "vat": 27.5, "grand_total": 577.5, "valid_until": "2026-08-15",
    })
    return app.QuotationApi()


# Fields renderHistoryTable() reads off each row. `item_count` is the one that broke.
HISTORY_ROW_FIELDS = [
    "id", "client_name", "venue", "quote_date", "valid_until", "item_count",
    "grand_total", "status", "payment_status", "amount_paid",
]


@pytest.mark.parametrize("field", HISTORY_ROW_FIELDS)
def test_history_row_has_every_field_the_table_renders(api, field):
    rows = api.get_history(300)["items"]
    assert rows, "fixture should have saved a quotation"
    assert field in rows[0], f"renderHistoryTable() reads q.{field}"


def test_history_table_does_not_read_items_directly():
    """Pins the fix. Shipping every line item for a 300-row list was the expensive mistake;
    reading `.length` off the omitted field was the breaking one."""
    assert "q.items.length" not in APP_JS, (
        "renderHistoryTable must use q.item_count — get_history() omits line items by design"
    )


def test_history_item_detail_includes_items_and_image_src(api):
    """Cloning a past quote back into the draft needs the lines and their photo URLs."""
    detail = api.get_history_item(1)
    assert detail["success"]
    assert len(detail["item"]["items"]) == 2
    for line in detail["item"]["items"]:
        assert "image_src" in line, "the draft renders <img src> from image_src"


def test_client_ledger_shape(api):
    ledger = api.get_client_ledger("Acme360", "0501234567")["ledger"]
    for key in ("items", "total_billed", "total_paid", "total_outstanding"):
        assert key in ledger


def test_analytics_shape(api):
    stats = api.get_analytics()
    for key in ("total_items", "avg_price", "min_price", "max_price",
                "year_min", "year_max", "venues", "needs_review"):
        assert key in stats


def test_margin_summary_shape(api):
    summary = api.get_margin_summary(30)["summary"]
    for key in ("total_margin", "items_with_cost", "period_days"):
        assert key in summary


def test_search_returns_image_src_not_base64(api):
    """The match cards render <img src="${m.image_src}">."""
    result = api.search_items("anything")
    assert result["success"]
    for match in result["matches"]:
        assert "image_src" in match
        assert not match["image_src"].startswith("data:")


def test_review_queue_row_shape(api):
    result = api.get_review_queue()
    assert result["success"]
    for row in result["items"]:
        for key in ("id", "description", "rate", "unit", "venue", "flag_reason"):
            assert key in row


def test_catalog_row_shape(api):
    import catalog_db
    catalog_db.add_catalog_item("Pirate Ship", rate=500, cost_price=300)
    rows = api.get_catalog_items()["items"]
    for key in ("id", "description", "unit", "rate", "cost_price", "category"):
        assert key in rows[0]


def test_every_api_method_returns_a_dict_the_bridge_can_serialize(api):
    """pywebview serializes return values to JSON. A method returning a raw object surfaces
    in the UI as a silent failure rather than an error."""
    import json

    for name in ("get_db_status", "get_company_info", "get_analytics",
                 "get_catalog_items", "get_review_queue", "get_history",
                 "get_storage_report", "list_corrections", "get_clients"):
        result = getattr(api, name)()
        assert isinstance(result, dict), f"{name} returned {type(result)}"
        json.dumps(result)  # raises if anything in there is not serializable
