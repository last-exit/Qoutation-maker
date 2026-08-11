"""Contract between app.js and ExtractorApi.

Borrowed from the parent project's `test_js_api_contract.py`, for the same reason: a Python
suite that never reads the frontend cannot see the failure mode where the UI calls a method
that does not exist. This is deliberately coarse — it catches a missing method, not a wrong
value, which is the failure that takes the whole window down.
"""
import inspect
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# encoding is explicit: read_text() otherwise uses the locale default, which is cp1252 on
# Windows — the platform this runs on.
APP_JS = (ROOT / "app.js").read_text(encoding="utf-8")


def test_shell_imports_headlessly():
    """pywebview only loads a GUI toolkit inside webview.start(), so importing the shell must
    work on a machine with no display. If that stops being true, fail here with an obvious
    message rather than confusingly at collection."""
    import main

    assert hasattr(main, "ExtractorApi")


def test_the_shell_is_ours_not_the_quotation_app(temp_store):
    """The folder above holds modules with adjacent names. If `sys.path` order ever put that
    one first, every test here would pass while testing the wrong code."""
    import extract
    import main

    for module in (main, extract, temp_store):
        assert Path(module.__file__).resolve().parent == ROOT


def test_every_method_the_ui_calls_exists_on_the_api():
    import main

    called = set(re.findall(r"bridge\.([a-zA-Z_]\w*)\s*\(", APP_JS))
    assert called, "found no bridge calls in app.js — the regex or the UI changed"

    available = {name for name, _ in inspect.getmembers(main.ExtractorApi, inspect.isfunction)
                 if not name.startswith("_")}
    assert called <= available, f"app.js calls methods the API does not have: {called - available}"


def test_the_ui_reads_only_fields_extraction_actually_returns(temp_store, make_xlsx):
    """The counts line and every card caption read these by name."""
    import extract

    result = extract.extract_files([make_xlsx()])
    for key in ("success", "files", "images", "skipped", "warnings", "counts"):
        assert key in result
    for key in ("documents", "images", "unique", "skipped"):
        assert key in result["counts"]
    for key in ("image_src", "source_file", "location", "kind"):
        assert key in result["images"][0]
