# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build definition for the Windows desktop app.

A spec file rather than a command line, because three of the things this build needs cannot
be expressed as flags without becoming unreadable: the exclude list, the recursion limit
torch's analysis requires, and a data path that has to be computed from the installed
chromadb package at build time.

Build with:  pyinstaller installer/quotation_engine.spec --noconfirm
"""

import pathlib
import sys

# torch's module graph is deep enough to hit the default limit during analysis. This is the
# standard remedy and has to run before Analysis().
sys.setrecursionlimit(sys.getrecursionlimit() * 5)

ROOT = pathlib.Path(SPECPATH).parent          # noqa: F821 - SPECPATH is injected
SITE_PACKAGES = pathlib.Path(__import__("chromadb").__file__).parent.parent

datas = [
    # --- frontend -----------------------------------------------------------------------
    (str(ROOT / "index.html"), "."),
    (str(ROOT / "app.js"), "."),
    (str(ROOT / "style.css"), "."),
    (str(ROOT / "assets"), "assets"),

    # --- models, pre-fetched by installer/fetch_models.py ---------------------------------
    # Without these the installed app reaches for the internet the first time someone runs a
    # search or parses a rasterised drawing, which is exactly when it will not have any.
    (str(ROOT / "models" / "all-MiniLM-L6-v2"), "models/all-MiniLM-L6-v2"),
    (str(ROOT / "models" / "easyocr"), "easyocr_models"),

    # --- documents ------------------------------------------------------------------------
    (str(ROOT / "template.xlsx"), "."),

    # --- seed copies of the user-editable configs -----------------------------------------
    # paths.seeded_path() copies these into %LOCALAPPDATA% on first run and uses that copy
    # from then on, so an upgrade never overwrites edited prices.
    (str(ROOT / "estimator_config.json"), "."),
    (str(ROOT / "master_rate_card.csv.csv"), "."),
    (str(ROOT / "company.json"), "."),
    (str(ROOT / "terms.json"), "."),
    (str(ROOT / "bundles.json"), "."),
    (str(ROOT / "venues.json"), "."),

    # --- chromadb's embedding-function schemas ---------------------------------------------
    # chromadb/utils/embedding_functions/schemas/schema_utils.py resolves this with five
    # nested dirname() calls, which land on site-packages/schemas/ - a TOP-LEVEL SIBLING of
    # chromadb/, not a subdirectory of it. collect_data_files('chromadb') therefore does not
    # find it. Leaving it out does not break startup: it raises FileNotFoundError the first
    # time an embedding function is constructed, so the build passes a smoke test and fails
    # on someone else's machine.
    (str(SITE_PACKAGES / "schemas" / "embedding_functions"), "schemas/embedding_functions"),
]

hiddenimports = [
    # chromadb's ONNXMiniLM_L6_V2.__init__ resolves these with
    # importlib.import_module("<name>") - a runtime string, invisible to static analysis.
    "onnxruntime",
    "tokenizers",
    "tqdm",
    "chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2",
    # Backend implementations chromadb selects by name at runtime.
    "chromadb.api.segment",
    "chromadb.db.impl",
    "chromadb.db.impl.sqlite",
    "chromadb.segment.impl.vector.local_hnsw",
    "chromadb.segment.impl.metadata.sqlite",
    "chromadb.migrations",
    "chromadb.migrations.embeddings_queue",
    # A top-level native package (not under chromadb/), new in the chromadb 1.x line.
    "chromadb_rust_bindings",
]

excludes = [
    # pywebview's freezing guide warns that PyInstaller collects every GUI toolkit it can
    # find, whether or not the app uses it - only EdgeChromium is used here.
    "PyQt5", "PyQt6", "PySide2", "PySide6", "gi", "tkinter",
    # Hangers-on of torch and scipy, dragged in by easyocr. Several hundred MB of nothing.
    "matplotlib", "IPython", "notebook", "pytest", "_pytest",
]

a = Analysis(                                  # noqa: F821
    [str(ROOT / "app.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)                              # noqa: F821

exe = EXE(                                     # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="QuotationEngine",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # No console window. The app is a desktop window; a flashing terminal behind it looks
    # broken to anyone who is not a developer.
    console=False,
    disable_windowed_traceback=False,
    icon=str(ROOT / "assets" / "app.ico"),
)

# One-folder, deliberately. A one-file build of this size unpacks the entire ~2 GB bundle
# into %TEMP% on every single launch before the first line of Python runs, needs that much
# free space again on top of the install, and orphans the temp copy permanently whenever the
# app is killed from Task Manager.
coll = COLLECT(                                # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="QuotationEngine",
)
