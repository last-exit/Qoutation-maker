"""Packages the app into a zip that installs on another machine with one double-click.

The problem this solves: handing the estimator to a colleague meant a page of terminal
instructions. This produces a single zip containing the app plus a setup script for each
platform. The recipient unzips it, double-clicks one file, and the app builds its own
virtual environment, installs its dependencies and launches.

**What is deliberately NOT included, and why it matters.** This folder holds live client
data — `invoices.db`, `history.db`, `catalog.db`, `corrections.db`, the Chroma index and
dated backups of all of them. A packaging routine built on "everything except a few
patterns" would ship every one of those to whoever the zip is sent to the first time
someone adds a new database file. So the rule here is an **allowlist**: a file is included
only if it is named, or matches an extension, in the lists below. Anything unrecognised is
left out. Getting this backwards leaks a client list, so it is worth the inconvenience.
"""

import io
import os
import stat
import zipfile
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent

# Whole folders that travel with the app.
INCLUDED_DIRS = ("assets", "tests", "docs", "models")

# Individual files at the root, by exact name.
INCLUDED_FILES = (
    "requirements.txt", "master_rate_card.csv", "master_rate_card.csv.csv",
    "estimator_config.json", "company.json", "bundles.json",
    "index.html", "app.js", "style.css",
    "README.md", "HANDOVER.md", "DESIGN.md", "CLAUDE.md",
    "credentials.json.template", ".gitignore",
)

# Root-level extensions that are always safe: source code, never data.
INCLUDED_ROOT_EXTENSIONS = (".py",)

# Never packaged, even if a rule above would otherwise catch it. Belt and braces — the
# allowlist should already exclude these, and this makes the intent unmissable.
NEVER_PACKAGE = (
    ".db", ".db-wal", ".db-shm", ".sqlite", ".sqlite3", ".env", ".pem", ".key",
    # Torch model weights. `models/` is packaged because the Mac zip needs the ONNX search
    # model, but installer/fetch_models.py also drops ~98 MB of easyocr weights in there for
    # the Windows build, and those have no business in a source distribution - a Mac install
    # gets them from easyocr itself.
    ".pth",
)
NEVER_PACKAGE_NAMES = ("credentials.json", "token.json", "invoices.db")
NEVER_PACKAGE_DIRS = (
    "venv", ".venv", "__pycache__", ".git", ".pytest_cache", "chroma_db",
    "backups", "graphify-out", "node_modules", ".claude", ".impeccable",
    "sample_quotes", "images", "logs",
    # Windows installer build tree and its output.
    "build", "dist", "build-venv", "redist",
)


def _is_safe(relative_path):
    """True when a path is allowed into the package."""
    parts = relative_path.parts
    if any(part in NEVER_PACKAGE_DIRS or part.startswith("chroma_db_backup")
           or part.startswith("corrections_backup") for part in parts):
        return False
    if relative_path.name in NEVER_PACKAGE_NAMES:
        return False
    if relative_path.suffix.lower() in NEVER_PACKAGE:
        return False
    return True


def collect_files(root=None):
    """Every file that belongs in the package, as (absolute_path, archive_name) pairs."""
    root = Path(root or _ROOT)
    picked = []

    for entry in sorted(root.iterdir()):
        relative = entry.relative_to(root)
        if not _is_safe(relative):
            continue
        if entry.is_file():
            if (entry.name in INCLUDED_FILES
                    or entry.suffix.lower() in INCLUDED_ROOT_EXTENSIONS):
                picked.append((entry, relative))
        elif entry.is_dir() and entry.name in INCLUDED_DIRS:
            for path in sorted(entry.rglob("*")):
                if path.is_file():
                    child = path.relative_to(root)
                    if _is_safe(child):
                        picked.append((path, child))

    return picked


# --- Setup scripts ----------------------------------------------------------------------
# One per platform, each doing the same three things: make a virtual environment, install
# the pinned dependencies, start the app. Written to be double-clickable, because a script
# that needs a terminal is exactly the barrier this is meant to remove.

_WINDOWS_SETUP = r"""@echo off
setlocal
cd /d "%~dp0"
title Quotation Engine - Setup

echo.
echo   Setting up the Quotation Engine. This takes a few minutes the first time.
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo   Python was not found.
  echo   Install Python 3.10 or newer from https://python.org/downloads
  echo   IMPORTANT: tick "Add Python to PATH" in the installer.
  echo.
  pause
  exit /b 1
)

if not exist venv (
  echo   Creating the virtual environment...
  python -m venv venv
)

echo   Installing dependencies...
venv\Scripts\python.exe -m pip install --upgrade pip --quiet
venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo   Something went wrong installing dependencies. The messages above say what.
  pause
  exit /b 1
)

echo.
echo   Done. Starting the app - use Run.bat next time.
echo.
venv\Scripts\python.exe app.py
pause
"""

_WINDOWS_RUN = r"""@echo off
cd /d "%~dp0"
if not exist venv (
  echo Run "Setup Windows.bat" first.
  pause
  exit /b 1
)
start "" venv\Scripts\pythonw.exe app.py
"""

_MAC_SETUP = r"""#!/bin/bash
cd "$(dirname "$0")"
echo
echo "  Setting up the Quotation Engine. This takes a few minutes the first time."
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "  Python 3 was not found."
  echo "  Install it from https://python.org/downloads and run this again."
  read -n 1 -s -r -p "  Press any key to close."
  exit 1
fi

if [ ! -d venv ]; then
  echo "  Creating the virtual environment..."
  python3 -m venv venv
fi

echo "  Installing dependencies..."
venv/bin/python -m pip install --upgrade pip --quiet
if ! venv/bin/python -m pip install -r requirements.txt; then
  echo
  echo "  Something went wrong installing dependencies. The messages above say what."
  read -n 1 -s -r -p "  Press any key to close."
  exit 1
fi

echo
echo "  Done. Starting the app - use Run.command next time."
echo
venv/bin/python app.py
"""

_MAC_RUN = r"""#!/bin/bash
cd "$(dirname "$0")"
if [ ! -d venv ]; then
  echo "Run 'Setup Mac or Linux.command' first."
  read -n 1 -s -r -p "Press any key to close."
  exit 1
fi
venv/bin/python app.py
"""

_READ_ME = """# Quotation Engine

## Installing

**Windows** — double-click **Setup Windows.bat**
**Mac or Linux** — double-click **Setup Mac or Linux.command**

That is the whole installation. It builds a self-contained environment inside this folder
and starts the app. It takes a few minutes the first time and needs an internet connection.

Afterwards, start the app with **Run.bat** (Windows) or **Run.command** (Mac).

If macOS refuses to open the file because it is from an unidentified developer:
right-click it, choose Open, then confirm.

## Reading dimensions off drawings

Vector PDFs are read exactly and need nothing extra. Drawings exported as flat images need
an OCR reader, which is a large optional install:

    venv/bin/python -m pip install easyocr        (Mac or Linux)
    venv\\Scripts\\python.exe -m pip install easyocr  (Windows)

It downloads roughly 2GB and needs internet the first time it runs. Without it the app
still works — pages that cannot be read ask you to type the dimensions in, and say so
clearly rather than pretending the drawing was empty.

## Your prices

Prices come from `master_rate_card.csv`. Edit it in Excel and the app picks the new numbers
up on the next calculation. Labour rates and the curved-work settings are in
`estimator_config.json`, and are also editable from Workspace Settings inside the app.

## What is not in this package

No quotations, invoices, client records or search index — this is the application only.
The machine you install it on starts with an empty database.
"""


def build(destination=None, root=None):
    """Writes the package and returns (path, file_count, size_bytes)."""
    root = Path(root or _ROOT)
    stamp = datetime.now().strftime("%Y%m%d")
    if destination:
        target = Path(destination)
    else:
        onedrive_desktop = Path.home() / "OneDrive" / "Desktop"
        desktop = onedrive_desktop if onedrive_desktop.is_dir() else Path.home() / "Desktop"
        target = desktop / f"QuotationEngine-{stamp}.zip"
    target.parent.mkdir(parents=True, exist_ok=True)

    files = collect_files(root)
    folder = "QuotationEngine"

    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for source, relative in files:
            archive.write(source, f"{folder}/{relative.as_posix()}")

        archive.writestr(f"{folder}/Setup Windows.bat", _WINDOWS_SETUP)
        archive.writestr(f"{folder}/Run.bat", _WINDOWS_RUN)
        archive.writestr(f"{folder}/READ ME FIRST.md", _READ_ME)

        # The mac scripts need their executable bit, or a double-click opens them in a text
        # editor instead of running them. Zip carries that in the high bits of external_attr.
        for name, body in (("Setup Mac or Linux.command", _MAC_SETUP),
                           ("Run.command", _MAC_RUN)):
            info = zipfile.ZipInfo(f"{folder}/{name}")
            info.date_time = datetime.now().timetuple()[:6]
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o755) << 16
            archive.writestr(info, body)

    return target, len(files) + 5, target.stat().st_size


if __name__ == "__main__":
    path, count, size = build()
    print(f"Wrote {path} — {count} files, {size / 1_000_000:.1f} MB")
