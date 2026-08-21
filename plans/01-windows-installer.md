# Plan 01 — A real Windows installer

> **Status, 2026-08-21.** Phases 2, 3 and 4 are **built**: `paths.py` and the 17-site
> refactor, `installer/quotation_engine.spec`, `installer/quotation_engine.iss`,
> `installer/fetch_models.py`, `installer/build_installer.bat`, `tools/make_icon.py`.
> Verified on macOS: 449 tests pass, model fetch works, frozen-mode paths resolve correctly
> under a simulated bundle. **Not yet run on Windows** — PyInstaller cannot cross-build and
> Inno Setup is Windows-only, so Phase 1 (the freeze spike) and Phase 5 (clean-machine
> verification) both still need the Windows PC. The chromadb freezing risk below is
> unchanged and still the thing most likely to bite.

Goal: the PM double-clicks `QuotationEngine-1.0.0-Setup.exe`, clicks Next a few times, and
gets a working app with a Start Menu entry, a Desktop icon, and an entry in Add/Remove
Programs. No Python. No terminal. No `pip`. No internet needed after the download.

## Scope, as decided

| Decision | Choice | Consequence |
|---|---|---|
| Platforms | **Windows only** this pass | macOS keeps today's `packager.py` zip + `Setup Mac or Linux.command`. No Apple Developer account, no notarization work. |
| OCR (easyocr) | **Always bundled** | Installer is ~2–2.5 GB. No optional-feature machinery, no post-install download, no terminal ever. Every raster drawing reads out of the box. |
| Build & delivery | **Built by hand on a Windows PC**, sent manually | No CI packaging job. A `build_installer.bat` that one person runs. PyInstaller cannot cross-build from macOS, so the Windows PC is required, not optional. |
| Updates | **One-shot** | New version = rebuild, resend, run the new installer over the old one. No auto-update. `AppId` stays fixed so upgrades replace cleanly. |

Non-goals: code signing (the .exe will show a SmartScreen "unknown publisher" warning —
see Phase 5), auto-update, an MSI, per-machine multi-user data sharing.

---

## Phase 0 — Documentation discovery (COMPLETE)

Done. Findings below are read from official docs and from the actual shipped package source
of the pinned versions in `requirements.txt`. **Treat this as the Allowed APIs list. Do not
invent flags or directives beyond it.**

### Allowed APIs / directives, with sources

**PyInstaller** — [runtime-information](https://pyinstaller.org/en/stable/runtime-information.html),
[operating-mode](https://pyinstaller.org/en/stable/operating-mode.html),
[spec-files](https://pyinstaller.org/en/stable/spec-files.html)

- Frozen detection: `getattr(sys, 'frozen', False)` and `sys._MEIPASS`. `_MEIPASS` is set in
  **both** one-dir and one-file mode — one idiom covers both.
- Flags in use: `--onedir`, `--windowed`, `--name`, `--icon`, `--add-data` (Windows separator
  is `;`), `--hidden-import`, `--exclude-module`, `--collect-all`.
- Spec-level: `excludes`, `hiddenimports`, `datas`, `binaries`, `module_collection_mode`.
- **PyInstaller ≥ 6.0 is mandatory** — `hook-torch.py` gates on it.

**pywebview 6.2.1** — [Freezing guide](https://pywebview.flowrl.com/guide/freezing.html), plus
`webview/guilib.py`, `webview/util.py`, `webview/platforms/winforms.py` read from the wheel

- Platform backends are imported **statically** (`import webview.platforms.winforms as guilib`,
  and `from . import edgechromium as Chromium`). PyInstaller's graph follows them.
  **`--hidden-import webview.platforms.edgechromium` is unnecessary** — the real risk is
  *over*-collection, which `excludes` fixes.
- `pyinstaller-hooks-contrib` ships **`hook-webview.py`** (Windows-only), which collects
  `webview/lib/*.dll` and `webview/lib/runtimes/win-*/native/WebView2Loader.dll`. Just make
  sure `pyinstaller-hooks-contrib` is installed.
- `webview/util.py::get_app_root()` already returns `sys._MEIPASS` when frozen — pywebview is
  PyInstaller-aware.
- Windows deps: `pythonnet` (the `clr` module), `proxy_tools`, `bottle`, `typing_extensions`.

**WebView2** — [Microsoft: Distribute your app and the WebView2 Runtime](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution)

- Included in Windows 11. "The vast majority" of Windows 10 devices have it; Microsoft says to
  handle the gap.
- Detect via `pv (REG_SZ)` under
  `HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}`
  or the `HKCU\Software\...` equivalent. Absent / empty / `0.0.0.0` = not installed.
- Silent install: `MicrosoftEdgeWebview2Setup.exe /silent /install` (~2 MB bootstrapper).

**Inno Setup 6** — [ishelp](https://jrsoftware.org/ishelp/)

- Free for commercial use (custom permissive licence; a commercial licence is *requested*, not
  required). Windows-only compiler.
- Directives in use: `AppId`, `AppName`, `AppVersion`, `DefaultDirName={autopf}`,
  `PrivilegesRequired`, `ArchitecturesAllowed=x64compatible`,
  `ArchitecturesInstallIn64BitMode=x64compatible` (**not** the outdated `x64`),
  `UninstallDisplayIcon`, `Compression=lzma2/max`, `SolidCompression`, `WizardStyle=modern`.
- `DiskSpanning=yes` is required only above **4,200,000,000 compressed bytes**. At 2–2.5 GB we
  are under it — but with less headroom than it looks.
- Finish-screen launch checkbox = `[Run]` entry with `Flags: postinstall nowait skipifsilent`.

**Windows per-user data** — [KNOWNFOLDERID](https://learn.microsoft.com/en-us/windows/win32/shell/knownfolderid)

- Use `FOLDERID_LocalAppData` (`%LOCALAPPDATA%`), **not** Roaming. Roaming profiles copy the
  file over the network at logon and are a classic source of SQLite corruption.
- Resolve with `os.environ["LOCALAPPDATA"]`, falling back to `ctypes` →
  `SHGetKnownFolderPath`. **No new dependency** — `platformdirs` is not worth the extra
  PyInstaller surface for a 15-line function.

### Anti-patterns — do NOT do these

- ❌ `--onefile`. At 2.5 GB it extracts the entire bundle to `%TEMP%` on **every launch**
  (minutes), needs 2.5 GB of free temp space on top of the install, and orphans the temp
  folder permanently if the app is killed from Task Manager. Docs: *"a one-file app is a
  little slower to start"* — that is written for normal-sized apps, not this one. **`--onedir`.**
- ❌ `--collect-all onnxruntime`. `hook-onnxruntime.py` already does
  `collect_dynamic_libs("onnxruntime")`. `--collect-all` drags in test data. The widespread
  `--collect-all` advice predates the hook.
- ❌ `collect_data_files('chromadb')` to find the `schemas/` directory. It is a **top-level
  sibling of `chromadb/` in site-packages**, not inside the package — see Phase 3.
- ❌ Writing anything to `sys._MEIPASS`. One-dir it is inside Program Files (read-only for a
  standard user); one-file it is a temp dir that vanishes.
- ❌ `ArchitecturesInstallIn64BitMode=x64` (outdated syntax).
- ❌ `import fitz`. Standardize on `import pymupdf` — an abandoned unrelated PyPI package
  named `fitz` breaks the legacy alias.
- ❌ Assuming easyocr/chromadb will download what they need at runtime. The installed app must
  work with no network.

---

## Phase 1 — De-risk spike (DO THIS FIRST, on the Windows PC)

**Why this phase exists.** Three integrations in this stack have no confirmed working
PyInstaller recipe, and one of them may be a wall rather than a speed bump. Finding that out
after building the whole installer pipeline would waste days.

The highest risk: **chromadb under PyInstaller.**
[chroma #1589](https://github.com/chroma-core/chroma/issues/1589) and
[#3947](https://github.com/chroma-core/chroma/issues/3947) are **both still open and
unresolved**; #3947 reports a **segfault** inside
`chromadb/segment/impl/vector/local_hnsw.py` during `collection.add()` in a frozen build. The
hidden-imports and data-file fixes in Phase 3 address *import* and *missing-file* failures —
they cannot be assumed to fix a segfault. Second risk: `pythonnet`/`clr` under PyInstaller
([pywebview #1215](https://github.com/r0x0r/pywebview/issues/1215), "Failed to resolve
Python.Runtime").

### Tasks

1. **Check the Python version first — this can block everything.** `onnxruntime==1.19.2`
   ships wheels for **cp38–cp312 only**. The build venv must be Python 3.11 or 3.12 (CI uses
   3.11 — match it). On Python 3.13+ there is no onnxruntime 1.19.2 to bundle at all.
   ```bat
   python --version
   ```
2. Create a clean build venv on the Windows PC, install `requirements.txt` **plus** `easyocr`
   (now a shipped dependency, not an optional extra), plus `pyinstaller>=6.0` and
   `pyinstaller-hooks-contrib`.
3. Write `spike/spike.py` (throwaway, ~40 lines) that does exactly three things:
   - opens a `webview.create_window(...)` + `webview.start()` window and closes it
   - creates a `chromadb.PersistentClient`, `collection.add()` one document, then queries it
   - constructs `easyocr.Reader(['en'], gpu=False, download_enabled=False, model_storage_directory=...)`
     against pre-downloaded weights and reads one test image
4. Freeze it: `pyinstaller spike/spike.py --onedir --windowed`
5. Run the frozen `.exe`. Record which of the three fail and how.

### Verification checklist

- [ ] `python --version` reports 3.11 or 3.12
- [ ] The frozen spike opens a pywebview window (proves pythonnet/clr survives freezing)
- [ ] The frozen spike writes **and reads back** a chromadb record without a segfault
- [ ] The frozen spike OCRs an image with `download_enabled=False` (proves offline OCR)

### 🚩 CHECKPOINT — stop and report to Fazal

If the **chromadb write path segfaults when frozen**, this plan needs a decision before
continuing. Options, in order of preference:

- **A.** Pin a different chromadb version and retest (1.5.9's Rust bindings are new; the open
  issues predate them and may not apply — or may be the cause).
- **B.** Replace chromadb with a plain-SQLite + numpy cosine-similarity index. The app already
  bundles a 88 MB ONNX embedder and `numpy`; chromadb is doing vector search over a few
  thousand rows, which is a `numpy` dot product. This removes the single riskiest dependency
  and shrinks the bundle. Non-trivial work in `app.py` and `embedder.py`.
- **C.** Ship the app frozen with semantic search disabled and everything else working.

Do not silently pick one. Report the failure and the options.

---

## Phase 2 — Split resource paths from data paths

**This is the core refactor and the largest code change.** Today **14 modules** anchor
everything — code assets *and* writable data — to `Path(__file__).resolve().parent`. Frozen
and installed under `C:\Program Files\`, that directory is **read-only for a standard user**,
so every database write, log write, and config save fails.

### Current state (audited)

| Module | Line | What it anchors |
|---|---|---|
| `history_db.py` | 27 | `history.db` |
| `catalog_db.py` | 25 | `catalog.db` |
| `jobs_db.py` | 23 | `jobs.db` |
| `invoices_db.py` | 22 | `invoices.db` |
| `corrections_db.py` | 18 | `corrections.db` |
| `app.py` | 36 | `chroma_db/` |
| `image_store.py` | 29 | `images/` |
| `logging_setup.py` | 20 | `logs/` |
| `db.py` | 19 | `backups/` |
| `backup.py` | 39–41 | `.backup_key`, `backup_config.json`, `backups/offsite` |
| `maintenance.py` | 32 | `chroma_db/chroma.sqlite3` |
| `shop_config.py` | 26 | `estimator_config.json` (**written** at line 216) |
| `rate_card.py` | 24, 217–223 | `estimator_config.json` (**written** at 257), `master_rate_card.csv.csv` (**appended** at 375) |
| `embedder.py` | 28 | `models/all-MiniLM-L6-v2` (read-only) |
| `parsing.py` | 118 | `venues.json` (read-only) |
| `doc_generator.py` | 35, 76 | `company.json`, `terms.json` |
| `app.py` | 66 | `sync_config.json` |

Three categories, and the split is not "code vs data" — it is **three** buckets:

1. **Read-only, bundled** — `models/`, `assets/`, `index.html`, `app.js`, `style.css`,
   `venues.json`, `bundles.json`, `template.xlsx`. → `resource_path()`
2. **Writable user data** — all five `.db` files, `chroma_db/`, `images/`, `logs/`,
   `backups/`, `.backup_key`, `backup_config.json`, `sync_config.json`. → `data_path()`
3. **Seeded-then-writable** — `estimator_config.json`, `master_rate_card.csv.csv`,
   `company.json`, `terms.json`. Ship a default in the bundle; **copy it into the data dir on
   first run** and use the data-dir copy from then on. The PM edits the rate card in Excel;
   that edit must survive an app upgrade, which it will not if it lives in Program Files.

### Tasks

1. **Create `paths.py`** — the single new module. No new dependencies.

   ```python
   """Where things live, frozen or not.

   Running from source, code and data share a folder and always have. Frozen and installed
   under Program Files, that folder is read-only for a standard user — so the two must be
   told apart. resource_path() is the bundle (read-only); data_path() is per-user and
   writable. Getting these backwards produces an app that starts and then cannot save.
   """
   import ctypes
   import os
   import shutil
   import sys
   from pathlib import Path

   APP_NAME = "QuotationEngine"


   def is_frozen() -> bool:
       # The documented idiom; _MEIPASS is set in both one-dir and one-file mode.
       return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


   def resource_path(relative: str = "") -> Path:
       """Read-only bundled resources: models, assets, the frontend, seed configs."""
       base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
       return Path(base) / relative if relative else Path(base)


   def _local_appdata() -> str:
       """SHGetKnownFolderPath(FOLDERID_LocalAppData) — authoritative when the env var is
       missing or stale (service accounts, runas, impersonation)."""
       class GUID(ctypes.Structure):
           _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort),
                       ("Data3", ctypes.c_ushort), ("Data4", ctypes.c_ubyte * 8)]
       fid = GUID(0xF1B32785, 0x6FBA, 0x4FCF,
                  (ctypes.c_ubyte * 8)(0x9D, 0x55, 0x7B, 0x8E, 0x7F, 0x15, 0x70, 0x91))
       ptr = ctypes.c_wchar_p()
       if ctypes.windll.shell32.SHGetKnownFolderPath(
               ctypes.byref(fid), 0, None, ctypes.byref(ptr)) != 0:
           raise OSError("SHGetKnownFolderPath failed")
       try:
           return ptr.value
       finally:
           ctypes.windll.ole32.CoTaskMemFree(ptr)


   def data_root() -> Path:
       """Per-user writable root. Local, not Roaming: SQLite in a roaming profile gets
       copied over the network at logon and can be captured mid-write."""
       if not is_frozen():
           return Path(__file__).resolve().parent      # source runs stay in-place
       if sys.platform == "win32":
           base = os.environ.get("LOCALAPPDATA") or _local_appdata()
       else:
           base = os.path.expanduser("~/Library/Application Support") \
               if sys.platform == "darwin" else os.path.expanduser("~/.local/share")
       root = Path(base) / APP_NAME
       root.mkdir(parents=True, exist_ok=True)
       return root


   def data_path(relative: str) -> Path:
       return data_root() / relative


   # Files the user edits, shipped with a default and copied out on first run so an upgrade
   # never overwrites the PM's rate card.
   SEEDED = ("estimator_config.json", "master_rate_card.csv.csv",
             "company.json", "terms.json", "bundles.json")


   def seeded_path(name: str) -> Path:
       target = data_root() / name
       if not target.exists():
           source = resource_path(name)
           if source.exists():
               target.parent.mkdir(parents=True, exist_ok=True)
               shutil.copy2(source, target)
       return target
   ```

   **Note the source-run behaviour**: unfrozen, `data_root()` returns the repo folder exactly
   as today. This keeps the whole existing test suite and the developer workflow working
   unchanged, and confines the new behaviour to frozen builds.

2. **Rewrite the 17 anchor sites** in the table above to call `resource_path()`,
   `data_path()`, or `seeded_path()` per its bucket. Mechanical, one line each.
3. **Fix the `http_server` / `images/` conflict.** `app.py:2136` calls
   `webview.start(http_server=True)`, which serves the app's own directory, and the UI loads
   product photos as relative `<img src="images/...">` (this is deliberate — see the comment
   at `app.py:2133`: it avoids pushing megabytes of base64 through the JS bridge). Frozen, the
   frontend is in the bundle and `images/` is in `%LOCALAPPDATA%`, so the relative URL breaks.
   Recommended fix: **`os.chdir(data_root())` before `webview.start()`**, and seed the data dir
   with copies of / symlinks to `index.html`, `app.js`, `style.css` — *or*, cleaner, pass an
   absolute `file://`-independent served root. Investigate which pywebview 6.2.1 actually
   supports before choosing; if neither is clean, serve photos through a `js_api` method
   returning a data URI for the few places it matters.
   **Do not skip this** — silently broken product photos is exactly the kind of bug that only
   appears on the PM's machine.
4. **Migrate existing data on first run.** The PM already has real databases. Add a one-time
   step: if `data_root()` is empty and a legacy install folder is present, copy the five `.db`
   files, `chroma_db/`, `images/` and `company.json` across. Otherwise Phase 5's handover
   becomes a manual file-copy exercise (today's `HANDOVER.md` §4).

### Verification checklist

- [ ] `python -m pytest tests/ -q` — full suite green, **unchanged**, from source
- [ ] `python -c "import app; print('ok')"` still passes (CI's headless-import guard)
- [ ] `grep -rn --include='*.py' 'Path(__file__).resolve().parent' *.py` returns only
      `paths.py` and legitimate read-only lookups
- [ ] New `tests/test_paths.py`: frozen-mode `data_root()` returns a `%LOCALAPPDATA%` path
      (monkeypatch `sys.frozen`/`sys._MEIPASS`); `seeded_path()` copies once and does not
      overwrite on the second call

### Anti-pattern guards

- Do not change `data_root()`'s unfrozen behaviour. The tests, `conftest.py` monkeypatching,
  and the developer's own working folder all depend on it staying the repo directory.
- Do not move `master_rate_card.csv.csv` or "fix" its double extension — `rate_card.py`
  depends on that exact name (`HANDOVER.md` calls this out explicitly).

---

## Phase 3 — PyInstaller spec

### Tasks

1. **Pre-download the two model sets into the build tree.** Both are gitignored and normally
   fetched at runtime — the installed app must not need a network.
   - `models/all-MiniLM-L6-v2/` (88 MB). `embedder.py` already has `MODEL_URLS` and a
     download routine; call it from the build script.
   - easyocr weights: `craft_mlt_25k.pth` (detector) + `english_g2.pth` (recognizer), unzipped
     flat into `models/easyocr/`.
   - **Also**: chromadb's *own* default embedding function downloads to
     `~/.cache/chroma/onnx_models/all-MiniLM-L6-v2/` from
     `https://chroma-onnx-models.s3.amazonaws.com/...`. Either pre-seed that path from the
     installer or — better — pass chromadb an explicit embedding function backed by the
     `models/all-MiniLM-L6-v2` we already ship. Two copies of the same MiniLM in a 2.5 GB
     bundle is silly; one is enough.
2. **Point easyocr at the bundled weights** in `design_parser.py:509`, replacing
   `easyocr.Reader(["en"], gpu=False, verbose=False)`:
   ```python
   _ocr_reader = easyocr.Reader(
       ["en"], gpu=False, verbose=False,
       model_storage_directory=str(paths.data_path("easyocr_models")),
       download_enabled=False,
   )
   ```
   `Reader.__init__` unconditionally `mkdir`s that directory, so it **must** be writable —
   hence `data_path()`, not `resource_path()`. Copy the bundled weights there via the seeding
   mechanism on first run. `download_enabled=False` makes a missing file fail loudly instead
   of silently reaching for the network on a machine that has none.
3. **Write `installer/quotation_engine.spec`.** Command-line flags do not scale to what this
   needs (`excludes`, `module_collection_mode`, the recursion limit), so go straight to a spec.

   ```python
   # installer/quotation_engine.spec
   import pathlib, sys
   import chromadb

   # torch's analysis blows the default recursion limit.
   sys.setrecursionlimit(sys.getrecursionlimit() * 5)

   _sp = pathlib.Path(chromadb.__file__).parent.parent   # site-packages

   datas = [
       ('../index.html', '.'), ('../app.js', '.'), ('../style.css', '.'),
       ('../assets', 'assets'),
       ('../models/all-MiniLM-L6-v2', 'models/all-MiniLM-L6-v2'),
       ('../models/easyocr', 'easyocr_models'),
       ('../template.xlsx', '.'), ('../venues.json', '.'),
       # Seed copies of the user-editable configs.
       ('../estimator_config.json', '.'), ('../master_rate_card.csv.csv', '.'),
       ('../company.json', '.'), ('../terms.json', '.'), ('../bundles.json', '.'),
       # chromadb resolves this via five dirname() calls from
       # chromadb/utils/embedding_functions/schemas/schema_utils.py, landing on
       # site-packages/schemas/ — a TOP-LEVEL SIBLING of chromadb/, so
       # collect_data_files('chromadb') does not find it. Missing, this raises
       # FileNotFoundError only when an embedding function is first constructed —
       # i.e. it passes a smoke test and fails in the field.
       (str(_sp / 'schemas' / 'embedding_functions'), 'schemas/embedding_functions'),
   ]

   hiddenimports = [
       # ONNXMiniLM_L6_V2.__init__ loads these with importlib.import_module(<string>),
       # which static analysis cannot see.
       'onnxruntime', 'tokenizers', 'tqdm',
       'chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2',
       'chromadb.api.segment',
       'chromadb.db.impl', 'chromadb.db.impl.sqlite',
       'chromadb.segment.impl.vector.local_hnsw',
       'chromadb.segment.impl.metadata.sqlite',
       'chromadb.migrations', 'chromadb.migrations.embeddings_queue',
       'chromadb_rust_bindings',   # top-level native pkg, new in chromadb 1.x
   ]

   excludes = [
       # pywebview's own docs warn PyInstaller collects every GUI toolkit it finds even
       # when only EdgeChromium is used. Plus torch/scipy hangers-on.
       'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'gi', 'tkinter',
       'matplotlib', 'IPython', 'pytest', 'notebook',
   ]
   ```
   Then the standard `Analysis` / `PYZ` / `EXE` / `COLLECT` blocks, with
   `console=False`, `icon='../assets/app.ico'`, `name='QuotationEngine'`.
4. **Generate `assets/app.ico`.** Only `assets/red_cube_logo.png` exists today. Convert it to a
   multi-resolution `.ico` (16/32/48/256) with Pillow — already a dependency.
5. **Write `installer/build_installer.bat`** — one double-click on the Windows PC: create/refresh
   the venv, install requirements + easyocr + pyinstaller, fetch both model sets, run
   PyInstaller against the spec, then invoke the Inno Setup compiler (`ISCC.exe`) from Phase 4.
6. **Rely on the existing hooks; do not hand-roll around them.** `pyinstaller-hooks-contrib`
   already provides working hooks for `webview`, `onnxruntime`, `torch`, `cv2`, `easyocr`,
   `openpyxl`, `docx`, `cryptography`. `hook-torch.py` sets
   `module_collection_mode = "pyz+py"` — torch's JIT reads its own source at runtime, so this
   is required, and it is why torch dominates the bundle size.
7. **Use `opencv-python-headless`**, which is what easyocr's own metadata requires. Full
   `opencv-python` adds a Qt/GUI stack for nothing.

### Verification checklist

- [ ] `dist\QuotationEngine\QuotationEngine.exe` launches and shows the window
- [ ] `dist\QuotationEngine\_internal\schemas\embedding_functions\` exists and is non-empty
- [ ] `dist\QuotationEngine\_internal\models\all-MiniLM-L6-v2\model.onnx` is ~88 MB
- [ ] With the network **disabled**: a semantic search returns results, and OCR reads a raster
      test drawing. This is the real test — both features silently reach for the internet on
      first use today.
- [ ] Report the actual `dist\` size. Estimate is 2–2.5 GB, extrapolated from wheel sizes
      (torch 122 MB, cv2-headless 44 MB, scipy 37 MB compressed) — **not measured**.

### Anti-pattern guards

- Do not add `--collect-all onnxruntime`, `--collect-all torch`, or
  `--hidden-import webview.platforms.edgechromium`. The hooks handle all three; these only add
  bulk and mask real errors.
- Do not delete the `schemas/embedding_functions` datas line because "the app still starts".
  It fails on first embedding-function construction, not at startup.

---

## Phase 4 — The Inno Setup wizard

### Tasks

1. Install Inno Setup 6 on the Windows PC (free, from jrsoftware.org).
2. **Generate the `AppId` GUID exactly once** and never change it. It is the key for upgrade
   detection and the Add/Remove Programs entry; changing it later gives the PM two installed
   copies.
3. Write `installer/quotation_engine.iss` — the full working skeleton, with every directive
   traceable to the docs, is in the research notes and should be copied rather than
   reconstructed. Wizard flow: Welcome → (optional licence) → Install location → Desktop-icon
   checkbox → Installing → Finish (with "Launch now").
4. **Bundle the WebView2 bootstrapper.** Download `MicrosoftEdgeWebview2Setup.exe` (~2 MB) into
   `installer/redist/`, ship it in `[Files]` with `Flags: deleteafterinstall`, and run it from
   `[Run]` with `Parameters: "/silent /install"` gated on a `Check:` function that reads the
   documented registry key. At 2.5 GB, 2 MB for "works on a Windows 10 machine that lacks the
   runtime" is free insurance — and without WebView2 the app shows no window at all.
5. **Compression: `Compression=lzma2/max`, `SolidCompression=no`.** The payload is dominated by
   already-incompressible binaries (`.pth` weights, DLLs, torch libs), so solid mode buys
   little ratio while making extraction strictly slower — the docs note that in solid mode
   Setup "can no longer randomly access the files."
6. **Leave `DiskSpanning` at the default `no`**, but check the compressed output size. The
   hard threshold is 4,200,000,000 bytes.

### Verification checklist

- [ ] `ISCC.exe installer\quotation_engine.iss` compiles with no warnings
- [ ] The wizard shows every screen; the Desktop-icon checkbox works both ways
- [ ] Start Menu entry and Desktop icon launch the app
- [ ] "Quotation Engine 1.0.0" appears in Settings → Apps, and **Uninstall removes the install
      folder** — while **leaving `%LOCALAPPDATA%\QuotationEngine` intact**. Uninstalling must
      never delete the PM's quotations.
- [ ] Re-running the installer over an existing install upgrades in place (same `AppId`)

---

## Phase 5 — Clean-machine verification and handover

**The single most valuable phase, and the one most likely to be skipped.** `HANDOVER.md` §1
already records why, from experience: `cryptography` was missing from `requirements.txt` for
months and nobody noticed, because it was present in the developer's venv. Every handover-eve
bug on this project has been the same shape — true on the build machine, false everywhere else.
A frozen bundle multiplies that class of bug rather than removing it.

### Tasks

1. **Install on a machine that has never had Python or this project on it.** A fresh Windows VM
   with a snapshot to roll back to is ideal. Not the build PC.
2. Run the full flow end to end on that machine, **with the network turned off after install**:
   drawing → estimate → quotation → Excel/Word → invoice.
3. Verify data lands in `%LOCALAPPDATA%\QuotationEngine` and survives an uninstall/reinstall.
4. Test as a **standard (non-admin) user**, not just as the admin who installed it. The whole
   Phase 2 refactor exists for this case.
5. **Rewrite the docs.** `README.md` "Installing on another machine" and `HANDOVER.md` §1–§3
   currently describe the zip + `run.bat` + "pip install easyocr" + "download the model while
   you have internet" flow. With a bundled installer, §2 and §3 largely **disappear** — say so
   rather than leaving stale instructions that contradict the installer.
6. **Keep `packager.py` and its tests.** It still serves the macOS/source path and has an
   allowlist worth preserving. Reframe it in `README.md` as "source distribution / macOS",
   with the Windows installer as the primary route. `tests/test_packager.py` stays green.
7. **Warn Fazal about SmartScreen.** The installer is unsigned, so Windows will show
   *"Windows protected your PC — unknown publisher"* on first run; the PM must click
   *More info → Run anyway*. This is the Windows equivalent of the macOS Gatekeeper note
   already in `README.md`. A code-signing certificate (~$100–400/yr, OV/EV) removes it —
   flagging as a decision, not assuming it.

### Verification checklist

- [ ] App installs and runs on a machine with no Python, as a non-admin user
- [ ] Full quote flow completes **offline**
- [ ] Semantic search and raster OCR both work offline on first use
- [ ] Uninstall leaves user data; reinstall picks it back up
- [ ] `README.md` and `HANDOVER.md` describe the installer, with no leftover
      `pip install easyocr` / `venv\Scripts\python.exe` instructions
- [ ] `python -m pytest tests/ -q` still green; CI still green

---

## Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| chromadb segfaults when frozen | **Medium** | **Blocks the plan** | Phase 1 spike; checkpoint with three fallbacks |
| pythonnet/clr fails to freeze | Medium | High | Phase 1 spike |
| Build Python is 3.13+ → no onnxruntime 1.19.2 | Low | High | First check in Phase 1 |
| Product photos break under `http_server` | **High** | Medium | Phase 2 task 3 — designed for explicitly |
| Bundle exceeds Inno's 4.2 GB limit | Low | Medium | Measure in Phase 3; `excludes` trims |
| Missing `schemas/` → field-only failure | High if skipped | High | Phase 3 datas entry + explicit check |
| Stale docs contradict the installer | High | Low | Phase 5 task 5 |

## Open decisions for Fazal

1. **After Phase 1** — if chromadb will not freeze, pick A / B / C. (Recommendation: try A
   first, it is an afternoon; B is the right long-term answer but is real work.)
2. **Code signing** (~$100–400/yr) to remove the SmartScreen warning. Default: skip it, tell
   the PM to click through once.
3. **App version number** for `AppVersion` / the installer filename. Suggest `1.0.0`.
