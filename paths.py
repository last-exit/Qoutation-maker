"""Where things live, running from source or frozen into an installed app.

For its whole life this app has run from its own source folder, so code and data shared a
directory and nothing had to tell them apart. Frozen by PyInstaller and installed under
`C:\\Program Files\\`, that assumption breaks in a specific and nasty way: the install
directory is read-only for a standard user, so the app starts fine and then cannot save a
quotation, write a log, or record a correction.

So there are three kinds of path here, and the difference matters:

  resource_path()  read-only things shipped inside the bundle - the ONNX model, the
                   frontend, fonts, the Excel template.
  data_path()      per-user writable things - the five SQLite databases, the Chroma index,
                   product photos, logs, backups.
  seeded_path()    files the user edits that ship with a default - the rate card, company
                   details, terms. Copied out of the bundle on first run and used from the
                   data directory ever after, so that reinstalling a new version never
                   overwrites the prices someone spent an afternoon correcting.

Running from source, `data_root()` deliberately returns the source folder, exactly as before.
The whole test suite, the fixtures that monkeypatch `DB_FILE`, and the developer's own
working copy all depend on that, and none of them should have to care that this module now
exists. The new behaviour applies only to frozen builds.
"""

import ctypes
import os
import shutil
import sys
from pathlib import Path

APP_NAME = "QuotationEngine"


def is_frozen():
    """True inside a PyInstaller bundle.

    `sys._MEIPASS` is set in both one-dir and one-file mode - it points at the bundled
    resource directory either way - so this one check covers both.
    """
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def resource_path(relative=""):
    """A read-only file shipped inside the bundle.

    Never write here. One-dir builds put it inside the install directory, which a standard
    user cannot write to; one-file builds put it in a temp directory that is deleted on exit.
    """
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    return Path(base) / relative if relative else Path(base)


def _windows_local_appdata():
    """`%LOCALAPPDATA%` via SHGetKnownFolderPath.

    The environment variable is correct in any normal interactive session, but can be absent
    or stale under service accounts, `runas`, and impersonation. This is the authoritative
    answer for those cases, and reaching it through ctypes means no extra dependency for
    PyInstaller to collect.
    """
    class GUID(ctypes.Structure):
        _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort),
                    ("Data3", ctypes.c_ushort), ("Data4", ctypes.c_ubyte * 8)]

    # FOLDERID_LocalAppData - {F1B32785-6FBA-4FCF-9D55-7B8E7F157091}
    folder_id = GUID(0xF1B32785, 0x6FBA, 0x4FCF,
                     (ctypes.c_ubyte * 8)(0x9D, 0x55, 0x7B, 0x8E, 0x7F, 0x15, 0x70, 0x91))
    buffer = ctypes.c_wchar_p()
    if ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(folder_id), 0, None, ctypes.byref(buffer)) != 0:
        raise OSError("SHGetKnownFolderPath(FOLDERID_LocalAppData) failed")
    try:
        return buffer.value
    finally:
        ctypes.windll.ole32.CoTaskMemFree(buffer)


def data_root():
    """The writable per-user directory. Created if missing.

    Local app data, not roaming. A roaming profile is copied over the network at logon, and
    an open SQLite database copied mid-write is a corrupted SQLite database - which is a
    tedious way to lose a company's quotation history.
    """
    if not is_frozen():
        # Source runs keep everything where it has always been.
        return Path(__file__).resolve().parent

    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or _windows_local_appdata()
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")

    root = Path(base) / APP_NAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def data_path(relative):
    """A writable per-user file or directory."""
    return data_root() / relative


# Files the user is expected to edit, shipped with a working default. The rate card is the
# one that matters most: the PM edits it in Excel, and an upgrade that silently reverted it
# to the shipped prices would be discovered at the worst possible moment.
SEEDED_FILES = (
    "estimator_config.json",
    "master_rate_card.csv.csv",
    "company.json",
    "terms.json",
    "bundles.json",
    "venues.json",
)


def seeded_path(name):
    """A user-editable file, copied out of the bundle on first run only.

    Unfrozen this is just the file in the source folder, so nothing is copied and nothing
    changes.
    """
    target = data_root() / name
    if not target.exists():
        source = resource_path(name)
        if source.exists() and source.resolve() != target.resolve():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    return target


def seed_all():
    """Copy every seeded default into the data directory. Safe to call on every start."""
    if not is_frozen():
        return
    for name in SEEDED_FILES:
        seeded_path(name)


# The frontend files, which have to sit in the same served directory as `images/`.
FRONTEND_FILES = ("index.html", "app.js", "style.css")
FRONTEND_DIRS = ("assets",)


def stage_frontend():
    """Puts the frontend next to the image store, and returns the page to open.

    pywebview's bundled HTTP server roots itself at the directory containing the page it was
    given, and serves everything relative to that. `image_store.web_src()` returns paths like
    `images/ab/abcd...jpg`, which is deliberate - it keeps megabytes of photo out of the JS
    bridge - but it does mean the frontend and the image store must live in the same
    directory.

    Running from source they always have. Frozen, the frontend is inside the read-only
    bundle and the photos are in the user's data directory, so every product photo in a
    quotation would silently render as a broken image. Copying the frontend out to the data
    directory - about 300 KB - is the cheapest way to put them back together.

    Re-staged whenever the bundled copy is newer, so an upgrade actually ships its new UI.
    """
    if not is_frozen():
        return str(resource_path("index.html"))

    root = data_root()
    for name in FRONTEND_FILES:
        source = resource_path(name)
        target = root / name
        if source.exists() and (not target.exists()
                                or source.stat().st_mtime > target.stat().st_mtime):
            shutil.copy2(source, target)

    for name in FRONTEND_DIRS:
        source = resource_path(name)
        target = root / name
        if source.is_dir():
            # dirs_exist_ok keeps this idempotent across upgrades.
            shutil.copytree(source, target, dirs_exist_ok=True)

    return str(root / "index.html")
