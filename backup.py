"""Encrypted off-machine backup, and the restore that proves it works.

Everything this business remembers — every rate ever quoted, every client, every job and what
it cost — lives in five SQLite files and an image folder on one laptop. `db.backup()` already
takes local snapshots, but a local snapshot and the original die on the same dead SSD. This
puts a copy somewhere else.

Two decisions worth stating plainly:

*Encrypted, because the destination is a synced cloud folder.* The archive contains client
contact details and every price the company has ever charged. Handing that to a third party in
the clear because it was convenient is not a trade worth making.

*The passphrase is shown to the user, once.* A key stored only on this laptop would make the
backup useless in the exact scenario it exists for. The passphrase goes in a password manager;
a local copy is kept purely so scheduled backups can run unattended.

*Every backup is verified by restoring it.* An archive that has never been read back is a
guess, not a backup — so `create()` restores into a temporary directory and runs an integrity
check on each database before reporting success.
"""
import base64
import json
import os
import secrets
import shutil
import sqlite3
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

import logging_setup

import paths

ROOT = paths.data_root()
KEY_FILE = paths.data_path(".backup_key")
CONFIG_FILE = paths.data_path("backup_config.json")

# What goes in. Deliberately not chroma_db: it is a derived index rebuilt from the source
# documents by "Sync & Build Index", and including it would triple the archive for something
# a single click regenerates. The image store *is* included — it is derived too, but only
# from an archive folder that may itself be gone.
BACKED_UP_FILES = [
    "history.db", "catalog.db", "corrections.db", "jobs.db",
    "company.json", "terms.json", "venues.json", "sync_config.json", "bundles.json",
]
BACKED_UP_DIRS = ["images"]

DATABASES = ["history.db", "catalog.db", "corrections.db", "jobs.db"]

# OWASP's floor for PBKDF2-HMAC-SHA256. Costs a fraction of a second once per backup.
KDF_ITERATIONS = 600_000
ARCHIVE_SUFFIX = ".rcbak"
KEEP_BACKUPS = 14

log = logging_setup.get_logger("backup")


# --- Key handling -----------------------------------------------------------------------

def _derive_key(passphrase, salt):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=KDF_ITERATIONS)
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))


def generate_passphrase():
    """A passphrase a human can copy accurately. Grouped hex rather than random punctuation
    because this gets typed by hand in the worst moment, on a machine that has just been
    rebuilt."""
    return "-".join(secrets.token_hex(3) for _ in range(5))


def ensure_passphrase():
    """Returns (passphrase, is_new).

    Kept in a local file so scheduled backups run unattended. That file is useless on its own
    once the laptop is gone, which is exactly why `is_new` is surfaced — the caller must show
    the passphrase to the user and tell them to store it somewhere else.
    """
    if KEY_FILE.exists():
        return KEY_FILE.read_text(encoding="utf-8").strip(), False
    passphrase = generate_passphrase()
    KEY_FILE.write_text(passphrase, encoding="utf-8")
    os.chmod(KEY_FILE, 0o600)
    log.warning("Generated a new backup passphrase. It must be stored off this machine.")
    return passphrase, True


# --- Configuration ----------------------------------------------------------------------

def find_cloud_folders():
    """Every synced folder on this machine that could hold backups, best first.

    Google Drive is preferred because the business already keeps its quotation archive there,
    so one account covers both and there is one less thing to remember to check.

    Drive for Desktop mounts per-account under ~/Library/CloudStorage/GoogleDrive-<email>/,
    which is why this globs rather than testing a fixed path.
    """
    home = Path.home()
    candidates = []

    for mount in sorted((home / "Library" / "CloudStorage").glob("GoogleDrive-*")):
        my_drive = mount / "My Drive"
        candidates.append(("Google Drive", my_drive if my_drive.is_dir() else mount))

    # Where the older standalone Drive client put things.
    legacy = home / "Google Drive"
    if legacy.is_dir():
        candidates.append(("Google Drive", legacy))

    dropbox = home / "Dropbox"
    if dropbox.is_dir():
        candidates.append(("Dropbox", dropbox))

    icloud = home / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
    if icloud.is_dir():
        candidates.append(("iCloud Drive", icloud))

    return [{"provider": name, "path": str(path / "RedCubeBackups")}
            for name, path in candidates if path.is_dir()]


def default_destination():
    """The best synced folder available, or a local one if none is."""
    found = find_cloud_folders()
    if found:
        return found[0]["path"]
    # Better than nothing, and honest about being on the same disk as the original.
    return str(ROOT / "backups" / "offsite")


def load_config():
    config = {"destination": default_destination(), "enabled": True, "keep": KEEP_BACKUPS}
    if CONFIG_FILE.exists():
        try:
            config.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        except Exception as e:
            log.warning("Could not read backup_config.json, using defaults: %s", e)
    return config


def save_config(**changes):
    config = load_config()
    config.update({k: v for k, v in changes.items() if v is not None})
    CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return config


# --- Creating ---------------------------------------------------------------------------

def _snapshot_databases(staging):
    """Consistent copies of each database via SQLite's backup API.

    A plain file copy of a WAL database can miss committed transactions still sitting in the
    -wal sidecar and produce a snapshot that will not open — which would be discovered at
    restore time, i.e. the worst possible moment.
    """
    copied = []
    for name in DATABASES:
        source_path = ROOT / name
        if not source_path.exists():
            continue
        source = sqlite3.connect(str(source_path))
        try:
            target = sqlite3.connect(str(staging / name))
            try:
                source.backup(target)
            finally:
                target.close()
        finally:
            source.close()
        copied.append(name)
    return copied


def _build_staging(staging):
    manifest = {"created": datetime.now().isoformat(timespec="seconds"), "files": []}
    manifest["files"].extend(_snapshot_databases(staging))

    for name in BACKED_UP_FILES:
        if name in DATABASES:
            continue
        source = ROOT / name
        if source.exists():
            shutil.copy2(source, staging / name)
            manifest["files"].append(name)

    for dirname in BACKED_UP_DIRS:
        source = ROOT / dirname
        if source.is_dir():
            shutil.copytree(source, staging / dirname)
            manifest["files"].append(dirname + "/")

    (staging / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def create(destination=None, passphrase=None, verify=True):
    """Writes an encrypted, verified backup. Returns a summary dict."""
    config = load_config()
    destination = Path(destination or config["destination"])
    destination.mkdir(parents=True, exist_ok=True)

    if passphrase is None:
        passphrase, is_new = ensure_passphrase()
    else:
        is_new = False

    # Milliseconds, not seconds. Two backups in the same second — a manual one landing on top
    # of a scheduled one — would otherwise resolve to the same filename, silently overwrite
    # each other, and quietly shrink the retention window. Exactly the bug db.backup() had.
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    archive_path = destination / f"redcube_{stamp}{ARCHIVE_SUFFIX}"

    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp) / "payload"
        staging.mkdir()
        manifest = _build_staging(staging)

        tar_path = Path(tmp) / "payload.tar.gz"
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(staging, arcname=".")

        salt = secrets.token_bytes(16)
        token = Fernet(_derive_key(passphrase, salt)).encrypt(tar_path.read_bytes())

        # Salt and version sit outside the ciphertext because they are not secret and are
        # needed to decrypt. Everything that says anything about the business is inside.
        with open(archive_path, "wb") as fh:
            fh.write(b"RCBAK1\n")
            fh.write(base64.b64encode(salt) + b"\n")
            fh.write(token)

    result = {
        "path": str(archive_path),
        "bytes": archive_path.stat().st_size,
        "files": manifest["files"],
        "passphrase_is_new": is_new,
        "passphrase": passphrase if is_new else None,
        "verified": False,
    }

    if verify:
        check = verify_backup(archive_path, passphrase)
        result["verified"] = check["ok"]
        result["verification"] = check
        if not check["ok"]:
            # Say so loudly rather than reporting a success that has not been demonstrated.
            log.error("Backup written but FAILED verification: %s", check)
            return result

    prune(destination, keep=config.get("keep", KEEP_BACKUPS))
    log.info("Backup written%s: %s (%.1f MB)",
             " and verified" if result["verified"] else " (verification skipped)",
             archive_path, result["bytes"] / 1e6)
    return result


# --- Restoring --------------------------------------------------------------------------

def _decrypt_to(archive_path, passphrase, target_dir):
    with open(archive_path, "rb") as fh:
        header = fh.readline().strip()
        if header != b"RCBAK1":
            raise ValueError(f"{Path(archive_path).name} is not a Red Cube backup.")
        salt = base64.b64decode(fh.readline().strip())
        token = fh.read()

    try:
        payload = Fernet(_derive_key(passphrase, salt)).decrypt(token)
    except InvalidToken:
        raise ValueError(
            "That passphrase does not open this backup. It is the one shown when backups "
            "were first set up — check your password manager."
        )

    tar_path = Path(target_dir) / "payload.tar.gz"
    tar_path.write_bytes(payload)
    with tarfile.open(tar_path, "r:gz") as tar:
        # filter='data' refuses absolute paths and parent-directory escapes in member names.
        try:
            tar.extractall(target_dir, filter="data")
        except TypeError:
            tar.extractall(target_dir)  # Python < 3.12 has no filter argument
    tar_path.unlink()
    return Path(target_dir)


def verify_backup(archive_path, passphrase=None):
    """Restores into a temporary directory and integrity-checks every database in it.

    This is the difference between a backup and a hope. Run automatically after each write.
    """
    if passphrase is None:
        passphrase, _ = ensure_passphrase()

    report = {"ok": False, "databases": {}, "files": 0}
    try:
        with tempfile.TemporaryDirectory() as tmp:
            restored = _decrypt_to(archive_path, passphrase, tmp)
            manifest_path = restored / "MANIFEST.json"
            if not manifest_path.exists():
                report["error"] = "Archive has no manifest."
                return report

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            report["files"] = len(manifest.get("files", []))

            for name in DATABASES:
                candidate = restored / name
                if not candidate.exists():
                    continue
                conn = sqlite3.connect(str(candidate))
                try:
                    status = conn.execute("PRAGMA integrity_check").fetchone()[0]
                    tables = conn.execute(
                        "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
                    ).fetchone()[0]
                finally:
                    conn.close()
                report["databases"][name] = {"integrity": status, "tables": tables}

            checked = report["databases"]
            report["ok"] = bool(checked) and all(
                d["integrity"] == "ok" and d["tables"] > 0 for d in checked.values()
            )
    except Exception as e:
        report["error"] = str(e)
    return report


def restore(archive_path, passphrase=None, target=None, make_safety_copy=True):
    """Replaces the live data with the contents of a backup.

    A safety copy of what is being overwritten is taken first, unconditionally by default:
    restoring the wrong archive is a real mistake to make under pressure, and without this it
    would be unrecoverable.
    """
    if passphrase is None:
        passphrase, _ = ensure_passphrase()
    target = Path(target or ROOT)

    check = verify_backup(archive_path, passphrase)
    if not check["ok"]:
        raise ValueError(f"Refusing to restore an archive that fails verification: {check}")

    safety = None
    if make_safety_copy:
        safety = ROOT / "backups" / f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        safety.mkdir(parents=True, exist_ok=True)
        for name in BACKED_UP_FILES:
            if (ROOT / name).exists():
                shutil.copy2(ROOT / name, safety / name)

    restored_names = []
    with tempfile.TemporaryDirectory() as tmp:
        source = _decrypt_to(archive_path, passphrase, tmp)
        for entry in source.iterdir():
            if entry.name == "MANIFEST.json":
                continue
            destination = target / entry.name
            if entry.is_dir():
                if destination.exists():
                    shutil.rmtree(destination)
                shutil.copytree(entry, destination)
            else:
                shutil.copy2(entry, destination)
            restored_names.append(entry.name)

    # The -wal/-shm sidecars belong to the databases being replaced. Left in place they would
    # be applied on top of the restored file and undo part of the restore.
    for name in DATABASES:
        for sidecar in (f"{name}-wal", f"{name}-shm"):
            path = target / sidecar
            if path.exists():
                path.unlink()

    log.warning("Restored %s files from %s", len(restored_names), archive_path)
    return {"restored": restored_names, "safety_copy": str(safety) if safety else None}


# --- Housekeeping -----------------------------------------------------------------------

def list_backups(destination=None):
    destination = Path(destination or load_config()["destination"])
    if not destination.is_dir():
        return []
    archives = sorted(destination.glob(f"*{ARCHIVE_SUFFIX}"),
                      key=lambda p: p.stat().st_mtime, reverse=True)
    return [{
        "path": str(p),
        "name": p.name,
        "bytes": p.stat().st_size,
        "created": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
    } for p in archives]


def prune(destination=None, keep=KEEP_BACKUPS):
    destination = Path(destination or load_config()["destination"])
    removed = 0
    for old in list_backups(destination)[keep:]:
        try:
            Path(old["path"]).unlink()
            removed += 1
        except OSError:
            pass
    return removed


def status():
    """What the UI shows: whether backups are configured, and how stale the newest one is."""
    config = load_config()
    archives = list_backups(config["destination"])
    newest = archives[0] if archives else None
    age_hours = None
    if newest:
        age_hours = round(
            (datetime.now() - datetime.fromtimestamp(Path(newest["path"]).stat().st_mtime))
            .total_seconds() / 3600, 1)
    return {
        "destination": config["destination"],
        "destination_exists": Path(config["destination"]).is_dir(),
        "enabled": config.get("enabled", True),
        "count": len(archives),
        "newest": newest,
        "age_hours": age_hours,
        # Surfaced so the UI can nag rather than quietly letting backups lapse.
        "stale": age_hours is None or age_hours > 48,
        "passphrase_stored_locally": KEY_FILE.exists(),
    }
