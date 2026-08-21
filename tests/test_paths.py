"""The frozen/unfrozen path split.

These matter more than their size suggests. Every one of them describes a failure that only
happens on an installed build - never on the machine that built it - which is precisely the
class of bug this project has been bitten by before.
"""

import os
import sys
from pathlib import Path

import pytest

import paths


@pytest.fixture
def frozen(tmp_path, monkeypatch):
    """Pretend to be a PyInstaller bundle rooted at tmp_path/bundle."""
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr(sys, "platform", "win32")
    return bundle


def test_unfrozen_data_root_is_the_source_folder():
    """Source runs must behave exactly as they always have - the test suite, the fixtures
    that monkeypatch DB_FILE, and the developer's working copy all assume it."""
    assert not paths.is_frozen()
    assert paths.data_root() == paths.resource_path()


def test_frozen_splits_resources_from_data(frozen, tmp_path):
    assert paths.is_frozen()
    assert paths.resource_path() == frozen
    assert paths.data_root() == tmp_path / "appdata" / paths.APP_NAME
    assert paths.data_root() != paths.resource_path()


def test_frozen_data_root_is_created(frozen):
    assert paths.data_root().is_dir()


def test_data_path_is_writable_when_the_bundle_is_not(frozen):
    """The whole point: an install under Program Files is read-only for a standard user, so
    a database opened relative to the bundle cannot be written."""
    target = paths.data_path("history.db")
    target.write_text("x", encoding="utf-8")
    assert target.read_text(encoding="utf-8") == "x"


def test_seeded_file_is_copied_out_of_the_bundle_once(frozen):
    (frozen / "master_rate_card.csv.csv").write_text("shipped", encoding="utf-8")

    first = paths.seeded_path("master_rate_card.csv.csv")
    assert first.read_text(encoding="utf-8") == "shipped"
    assert first.parent == paths.data_root()


def test_seeding_never_overwrites_an_edited_file(frozen):
    """The PM edits the rate card in Excel. An upgrade that reverted it to the shipped
    prices would be discovered while quoting, which is far too late."""
    (frozen / "master_rate_card.csv.csv").write_text("shipped", encoding="utf-8")
    paths.seeded_path("master_rate_card.csv.csv")

    edited = paths.data_root() / "master_rate_card.csv.csv"
    edited.write_text("the PM's corrected prices", encoding="utf-8")

    again = paths.seeded_path("master_rate_card.csv.csv")
    assert again.read_text(encoding="utf-8") == "the PM's corrected prices"


def test_seeded_path_is_harmless_when_the_default_is_absent(frozen):
    assert paths.seeded_path("not_shipped.json").parent == paths.data_root()


def test_unfrozen_seeding_does_not_copy_anything():
    """From source there is only one directory, so seeding must be a no-op rather than
    copying a file onto itself."""
    assert paths.seeded_path("company.json") == paths.data_root() / "company.json"


def test_frontend_is_staged_beside_the_image_store(frozen):
    """image_store.web_src() returns relative 'images/..' URLs, which pywebview's HTTP
    server resolves against the directory holding index.html. If the frontend stays in the
    bundle while photos live in the data directory, every product photo silently renders as
    a broken image."""
    for name in paths.FRONTEND_FILES:
        (frozen / name).write_text("<!-- shipped -->", encoding="utf-8")

    entry = paths.stage_frontend()

    assert Path(entry) == paths.data_root() / "index.html"
    for name in paths.FRONTEND_FILES:
        assert (paths.data_root() / name).exists()


def test_staging_refreshes_the_frontend_after_an_upgrade(frozen):
    for name in paths.FRONTEND_FILES:
        (frozen / name).write_text("old", encoding="utf-8")
    paths.stage_frontend()

    for name in paths.FRONTEND_FILES:
        source = frozen / name
        source.write_text("new", encoding="utf-8")
        # Bump past the staged copy's timestamp; a same-second write would otherwise be
        # indistinguishable from the existing one.
        stat = (paths.data_root() / name).stat()
        os.utime(source, (stat.st_atime + 10, stat.st_mtime + 10))

    paths.stage_frontend()
    for name in paths.FRONTEND_FILES:
        assert (paths.data_root() / name).read_text(encoding="utf-8") == "new"


def test_unfrozen_staging_returns_the_source_index():
    assert paths.stage_frontend() == str(paths.resource_path("index.html"))
