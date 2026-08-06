"""Shared fixtures.

Every store keeps its path in a module-level `DB_FILE` and runs `init_db()` at import, so
tests redirect that constant at a tmp path and re-run the migrations. Nothing here touches
the real databases in the project root.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import catalog_db  # noqa: E402
import corrections_db  # noqa: E402
import history_db  # noqa: E402
import image_store  # noqa: E402


@pytest.fixture
def temp_history(tmp_path, monkeypatch):
    monkeypatch.setattr(history_db, "DB_FILE", str(tmp_path / "history.db"))
    history_db.init_db()
    return history_db


@pytest.fixture
def temp_catalog(tmp_path, monkeypatch):
    monkeypatch.setattr(catalog_db, "DB_FILE", str(tmp_path / "catalog.db"))
    catalog_db.init_db()
    return catalog_db


@pytest.fixture
def temp_corrections(tmp_path, monkeypatch):
    monkeypatch.setattr(corrections_db, "DB_FILE", str(tmp_path / "corrections.db"))
    corrections_db.init_db()
    return corrections_db


@pytest.fixture
def temp_images(tmp_path, monkeypatch):
    monkeypatch.setattr(image_store, "IMAGE_DIR", tmp_path / "images")
    return image_store


@pytest.fixture
def png_bytes():
    """A small real PNG. Built rather than committed so the suite has no binary fixtures."""
    import io

    from PIL import Image

    def make(color=(200, 30, 30), size=(64, 48)):
        buf = io.BytesIO()
        Image.new("RGB", size, color).save(buf, format="PNG")
        return buf.getvalue()

    return make
