"""File logging for a desktop app whose console nobody ever sees.

Failures used to surface two ways, both useless to the person running the app: a `print()` to
a terminal that does not exist when launched from Finder, or a raw `str(exception)` pushed
into the UI. A PM cannot act on "list index out of range", and once the window is closed
there is no record that anything went wrong at all.

`report()` is the bridge between those worlds: it writes the full traceback to disk for
whoever debugs it later, and returns a short, plain sentence for the UI.
"""
import logging
import os
import platform
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "logs"
LOG_FILE = LOG_DIR / "quotation_engine.log"

_configured = False


def setup(level=logging.INFO):
    """Installs a rotating file handler plus console output. Safe to call more than once."""
    global _configured
    if _configured:
        return logging.getLogger("quotation")

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("quotation")
    logger.setLevel(level)
    logger.propagate = False

    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")

    # 2 MB x 5 keeps a few weeks of a single user's activity without unbounded growth.
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)

    _configured = True
    logger.info("--- Quotation Engine started (pid %s) ---", os.getpid())
    return logger


def get_logger(name="quotation"):
    setup()
    return logging.getLogger(name if name.startswith("quotation") else f"quotation.{name}")


def collect_diagnostics(dest_dir=None):
    """Bundles the logs and environment into one file the PM can send on.

    The log lives at logs/quotation_engine.log, which is a path nobody hunts for on their
    own — so a failure on the only machine that matters stays invisible to whoever could
    fix it. This puts a single file on the Desktop instead, to be attached to a WhatsApp
    message the same way quotations already go out (see sharing.py).

    Deliberately logs and environment only. The databases hold real client records, and a
    support bundle is not a reason to move those off the machine.
    """
    dest = Path(dest_dir) if dest_dir else (Path.home() / "Desktop")
    if not dest.is_dir():
        dest = Path.home()

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    out_path = dest / f"quotation-engine-diagnostics_{stamp}.txt"

    header = [
        "Quotation Engine diagnostics",
        f"Generated : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Platform  : {platform.platform()}",
        f"Python    : {sys.version.split()[0]}",
        f"App path  : {ROOT}",
    ]

    try:
        import design_parser
        header.append(f"OCR       : {design_parser.ocr_status()}")
    except Exception as exc:                      # diagnostics must never fail on its own
        header.append(f"OCR       : unavailable ({exc})")

    # Newest log first, then the rotated backups, so the most recent failure is at the top
    # rather than buried under weeks of startup lines.
    sections = []
    for log_path in [LOG_FILE] + sorted(LOG_DIR.glob(f"{LOG_FILE.name}.*")):
        try:
            sections.append(f"\n\n===== {log_path.name} =====\n{log_path.read_text(encoding='utf-8', errors='replace')}")
        except FileNotFoundError:
            continue
        except Exception as exc:
            sections.append(f"\n\n===== {log_path.name} (unreadable: {exc}) =====")

    try:
        out_path.write_text("\n".join(header) + "".join(sections), encoding="utf-8")
    except Exception as exc:
        return report("Saving the diagnostics file", exc)

    return {"success": True, "path": str(out_path)}


def report(operation, exc, user_message=None):
    """Logs an exception with its traceback and returns the JS API's error envelope.

    The message handed to the UI names the operation and points at the log, instead of
    leaking an exception string that means nothing outside a Python REPL.
    """
    logger = get_logger()
    logger.exception("%s failed: %s", operation, exc)
    friendly = user_message or f"{operation} failed. See logs/{LOG_FILE.name} for details."
    return {"success": False, "error": friendly, "detail": str(exc)}
