"""Backup and restore.

The tests that matter here are the ones that prove the archive can be read back. Everything
this business remembers lives in a handful of files on one laptop; an archive nobody has ever
restored is a guess.
"""
import json
import sqlite3

import pytest

import backup


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """A throwaway app directory with real databases in it."""
    monkeypatch.setattr(backup, "ROOT", tmp_path)
    monkeypatch.setattr(backup, "KEY_FILE", tmp_path / ".backup_key")
    monkeypatch.setattr(backup, "CONFIG_FILE", tmp_path / "backup_config.json")

    for name in ("history.db", "jobs.db"):
        conn = sqlite3.connect(str(tmp_path / name))
        conn.execute("CREATE TABLE things (id INTEGER PRIMARY KEY, label TEXT)")
        conn.execute("INSERT INTO things (label) VALUES ('from " + name + "')")
        conn.commit()
        conn.close()

    (tmp_path / "company.json").write_text(json.dumps({"name": "RED CUBE"}))
    images = tmp_path / "images" / "ab"
    images.mkdir(parents=True)
    (images / "photo.jpg").write_bytes(b"\xff\xd8not-really-a-jpeg")

    destination = tmp_path / "offsite"
    return {"root": tmp_path, "destination": destination}


# --- Creating ---------------------------------------------------------------------------

def test_backup_is_created_and_verifies(workspace):
    result = backup.create(destination=workspace["destination"], verify=True)
    assert result["verified"] is True
    assert result["bytes"] > 0
    assert "history.db" in result["files"]
    assert "images/" in result["files"]


def test_first_backup_surfaces_the_passphrase(workspace):
    """A passphrase kept only on this laptop would be gone in the exact situation the backup
    exists for, so the caller has to be told to store it elsewhere."""
    result = backup.create(destination=workspace["destination"])
    assert result["passphrase_is_new"] is True
    assert result["passphrase"]

    second = backup.create(destination=workspace["destination"])
    assert second["passphrase_is_new"] is False
    assert second["passphrase"] is None


def test_archive_is_not_readable_without_the_passphrase(workspace):
    """The destination is a synced cloud folder holding every price the company charges."""
    result = backup.create(destination=workspace["destination"])
    blob = open(result["path"], "rb").read()

    assert b"RED CUBE" not in blob
    assert b"from history.db" not in blob
    assert blob.startswith(b"RCBAK1")


def test_wrong_passphrase_is_refused_clearly(workspace):
    result = backup.create(destination=workspace["destination"])
    check = backup.verify_backup(result["path"], passphrase="not-the-passphrase")
    assert check["ok"] is False
    assert "passphrase" in check["error"].lower()


def test_verification_checks_every_database(workspace):
    result = backup.create(destination=workspace["destination"])
    report = result["verification"]
    assert set(report["databases"]) == {"history.db", "jobs.db"}
    assert all(d["integrity"] == "ok" for d in report["databases"].values())


def test_a_corrupt_archive_fails_verification(workspace):
    result = backup.create(destination=workspace["destination"])
    path = result["path"]
    data = bytearray(open(path, "rb").read())
    data[-20] ^= 0xFF  # flip a bit inside the ciphertext
    open(path, "wb").write(bytes(data))

    assert backup.verify_backup(path)["ok"] is False


def test_a_foreign_file_is_rejected(workspace):
    workspace["destination"].mkdir(parents=True, exist_ok=True)
    stray = workspace["destination"] / "notes.rcbak"
    stray.write_bytes(b"just some bytes")
    assert backup.verify_backup(stray)["ok"] is False


# --- Restoring --------------------------------------------------------------------------

def test_restore_brings_the_data_back(workspace):
    root = workspace["root"]
    result = backup.create(destination=workspace["destination"])

    # Lose everything.
    (root / "history.db").unlink()
    (root / "company.json").unlink()
    import shutil
    shutil.rmtree(root / "images")

    backup.restore(result["path"], make_safety_copy=False)

    assert (root / "history.db").exists()
    assert (root / "images" / "ab" / "photo.jpg").exists()
    assert json.loads((root / "company.json").read_text())["name"] == "RED CUBE"

    conn = sqlite3.connect(str(root / "history.db"))
    try:
        assert conn.execute("SELECT label FROM things").fetchone()[0] == "from history.db"
    finally:
        conn.close()


def test_restore_takes_a_safety_copy_of_what_it_overwrites(workspace):
    """Restoring the wrong archive is a real mistake to make under pressure."""
    root = workspace["root"]
    result = backup.create(destination=workspace["destination"])

    conn = sqlite3.connect(str(root / "history.db"))
    conn.execute("INSERT INTO things (label) VALUES ('added after the backup')")
    conn.commit()
    conn.close()

    outcome = backup.restore(result["path"])
    safety = outcome["safety_copy"]
    assert safety

    from pathlib import Path
    saved = sqlite3.connect(str(Path(safety) / "history.db"))
    try:
        labels = [r[0] for r in saved.execute("SELECT label FROM things")]
    finally:
        saved.close()
    assert "added after the backup" in labels, "the overwritten state must be recoverable"


def test_restore_refuses_an_archive_that_does_not_verify(workspace):
    result = backup.create(destination=workspace["destination"])
    data = bytearray(open(result["path"], "rb").read())
    data[-20] ^= 0xFF
    open(result["path"], "wb").write(bytes(data))

    with pytest.raises(ValueError):
        backup.restore(result["path"])


def test_restore_clears_wal_sidecars(workspace):
    """A leftover -wal would be applied on top of the restored file and undo part of it."""
    root = workspace["root"]
    result = backup.create(destination=workspace["destination"])
    (root / "history.db-wal").write_bytes(b"stale wal")

    backup.restore(result["path"], make_safety_copy=False)
    assert not (root / "history.db-wal").exists()


# --- Housekeeping -----------------------------------------------------------------------

def test_backups_in_the_same_second_do_not_overwrite_each_other(workspace):
    """A manual backup landing on top of a scheduled one must not silently replace it, or
    the retention window quietly shrinks to one."""
    for _ in range(5):
        backup.create(destination=workspace["destination"], verify=False)
    assert len(backup.list_backups(workspace["destination"])) == 5


def test_old_backups_are_pruned(workspace):
    for _ in range(5):
        backup.create(destination=workspace["destination"], verify=False)
    backup.prune(workspace["destination"], keep=3)
    assert len(backup.list_backups(workspace["destination"])) == 3


def test_status_reports_staleness_when_there_is_nothing(workspace):
    backup.save_config(destination=str(workspace["destination"]))
    state = backup.status()
    assert state["count"] == 0
    assert state["stale"] is True, "no backup at all is the stalest state there is"


def test_status_after_a_backup(workspace):
    backup.save_config(destination=str(workspace["destination"]))
    backup.create(destination=workspace["destination"])
    state = backup.status()
    assert state["count"] == 1
    assert state["stale"] is False
    assert state["age_hours"] < 1


def test_default_destination_is_a_synced_folder_when_one_exists(workspace):
    assert "RedCubeBackups" in backup.default_destination()


def test_google_drive_is_preferred_over_other_providers(tmp_path, monkeypatch):
    """The quotation archive already lives in Drive, so one account covers both."""
    monkeypatch.setattr(backup.Path, "home", staticmethod(lambda: tmp_path))
    (tmp_path / "Library/CloudStorage/GoogleDrive-me@example.com/My Drive").mkdir(parents=True)
    (tmp_path / "Library/Mobile Documents/com~apple~CloudDocs").mkdir(parents=True)
    (tmp_path / "Dropbox").mkdir()

    found = backup.find_cloud_folders()
    assert found[0]["provider"] == "Google Drive"
    assert "My Drive" in found[0]["path"]
    assert {f["provider"] for f in found} == {"Google Drive", "Dropbox", "iCloud Drive"}


def test_falls_back_to_a_local_folder_with_no_cloud_provider(tmp_path, monkeypatch):
    monkeypatch.setattr(backup.Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.setattr(backup, "ROOT", tmp_path / "app")
    assert backup.find_cloud_folders() == []
    assert "offsite" in backup.default_destination()
