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
import sys
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


def report(operation, exc, user_message=None):
    """Logs an exception with its traceback and returns the JS API's error envelope.

    The message handed to the UI names the operation and points at the log, instead of
    leaking an exception string that means nothing outside a Python REPL.
    """
    logger = get_logger()
    logger.exception("%s failed: %s", operation, exc)
    friendly = user_message or f"{operation} failed. See logs/{LOG_FILE.name} for details."
    return {"success": False, "error": friendly, "detail": str(exc)}
