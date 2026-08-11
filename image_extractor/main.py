"""Desktop shell for the document image extractor. Run it: `python image_extractor/main.py`.

Named `main` rather than `app` for the same reason `store` is not `image_store` - the
quotation app one folder up owns those module names, and nothing here should ever be able to
shadow them.

A pywebview window over `extract` and `export`. The window is deliberately thin: every
decision about what an image is and where it came from lives in `extract.py`, and this file
only moves paths in and records out.

Two details are load-bearing and worth keeping if this is ever rewritten:

* `http_server=True` serves this folder over localhost, which is what lets the page show
  thumbnails with a plain `<img src="store/ab/....jpg">` instead of pushing megabytes of
  base64 across the JS bridge on every render.
* Dropped documents arrive as bytes through `extract_uploads`, not as paths. A webview's
  drop event hands the page a File object with no filesystem path; pywebview can sometimes
  attach one via `pywebviewFullPath`, and when that binding does not fire, dropping a
  document silently does nothing at all. Reading the file in the page is the route that
  works every time.
"""
import base64
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import webview

import clipboard
import export
import extract
import store

ROOT = Path(__file__).resolve().parent

FILE_TYPES = (
    'Documents (*.xlsx;*.xlsm;*.docx;*.pdf)',
    'Excel (*.xlsx;*.xlsm)',
    'Word (*.docx)',
    'PDF (*.pdf)',
)


class ExtractorApi:
    """The JS API. Every method returns {"success": bool, ...} so the UI never has to guess."""

    def __init__(self):
        self.last_result = None

    # --- Input -------------------------------------------------------------------------

    def pick_files(self):
        """Native multi-select dialog. The drop zone is the other way in."""
        try:
            window = webview.windows[0]
            result = window.create_file_dialog(
                webview.OPEN_DIALOG, allow_multiple=True, file_types=FILE_TYPES
            )
            if not result:
                return {"success": False, "error": "No files selected."}
            return {"success": True, "paths": list(result)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def pick_output_folder(self):
        try:
            window = webview.windows[0]
            result = window.create_file_dialog(webview.FOLDER_DIALOG)
            if not result:
                return {"success": False, "error": "No folder selected."}
            return {"success": True, "path": str(result[0])}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # --- Work --------------------------------------------------------------------------

    def extract(self, paths):
        """Extracts every embedded image from the given documents."""
        try:
            if not paths:
                return {"success": False, "error": "No documents to read."}
            self.last_result = extract.extract_files(list(paths))
            return self.last_result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def extract_uploads(self, uploads):
        """Extracts from documents handed over as bytes rather than paths.

        This is the drag-and-drop route. A webview's drop event gives the page a File object
        but never a filesystem path — pywebview can sometimes attach one, and when it cannot,
        dropping a document silently did nothing. Reading the file in the page and sending it
        here removes that dependency: the drop works the same way on every platform.

        `uploads` is [{"name": ..., "data": <base64>}]. The bytes are written to a temporary
        directory only long enough to be parsed; the images themselves are already in the
        store by then, so nothing is lost when it is removed.
        """
        try:
            if not uploads:
                return {"success": False, "error": "No documents to read."}

            workspace = Path(tempfile.mkdtemp(prefix="image_extractor_"))
            try:
                paths, rejected = [], []
                for upload in uploads:
                    name = Path(str((upload or {}).get("name") or "")).name
                    if not name:
                        continue
                    payload = (upload or {}).get("data") or ""
                    try:
                        raw = base64.b64decode(payload.split(",", 1)[-1])
                    except Exception:
                        rejected.append({"file": name, "path": name,
                                         "reason": "That file could not be read from the drop."})
                        continue
                    destination = workspace / name
                    destination.write_bytes(raw)
                    paths.append(destination)

                result = extract.extract_files(paths)
                # The temp directory is an implementation detail; report the names the user
                # actually dropped.
                for record in result["images"]:
                    record["source_path"] = record["source_file"]
                for entry in result["files"] + result["skipped"]:
                    entry["path"] = entry["file"]
                result["skipped"].extend(rejected)
                result["counts"]["skipped"] = len(result["skipped"])

                self.last_result = result
                return result
            finally:
                shutil.rmtree(workspace, ignore_errors=True)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def export(self, out_dir=None):
        """Writes the last run to readable files plus manifest.json."""
        try:
            if not self.last_result or not self.last_result.get("images"):
                return {"success": False, "error": "Nothing extracted yet."}
            return export.export(self.last_result, out_dir or None)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def clear(self):
        self.last_result = None
        return {"success": True}

    # --- Clipboard ---------------------------------------------------------------------

    def copy_image(self, ref):
        """Puts one extracted image on the system clipboard, ready to paste anywhere.

        Takes a ref rather than bytes: the picture is already on disk under its hash, so
        nothing has to cross the JS bridge to be copied.
        """
        try:
            raw = store.read_bytes(ref)
            if raw is None:
                return {"success": False, "error": "That image is no longer in the store."}
            ok, error = clipboard.copy_image(raw)
            return {"success": True} if ok else {"success": False, "error": error}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def copy_all_images(self):
        """Copies the last run's images one after another is impossible — a clipboard holds
        one thing. Copies their file paths instead, which is what a file manager or an email
        attachment dialog actually wants."""
        try:
            if not self.last_result or not self.last_result.get("images"):
                return {"success": False, "error": "Nothing extracted yet."}
            seen, paths = set(), []
            for image in self.last_result["images"]:
                path = store.path_for(image.get("ref"))
                if path and path.exists() and str(path) not in seen:
                    seen.add(str(path))
                    paths.append(str(path))
            if not paths:
                return {"success": False, "error": "None of those images are in the store."}
            ok, error = clipboard.copy_text("\n".join(paths))
            return {"success": True, "count": len(paths)} if ok else {"success": False, "error": error}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # --- Housekeeping ------------------------------------------------------------------

    def stats(self):
        try:
            return {"success": True, "store": store.stats(),
                    "store_dir": str(store.IMAGE_DIR),
                    "out_dir": str(export.DEFAULT_OUT_DIR)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def reveal(self, path):
        """Opens a folder in the platform's file manager."""
        try:
            target = Path(path or export.DEFAULT_OUT_DIR)
            if not target.exists():
                return {"success": False, "error": "That folder does not exist yet."}
            if sys.platform == "win32":
                os.startfile(str(target))  # noqa: S606 - the path is ours, not user input
            elif sys.platform == "darwin":
                subprocess.run(["open", str(target)], check=False)
            else:
                subprocess.run(["xdg-open", str(target)], check=False)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}


def main():
    # The window's HTML, its stylesheet and the image store are all resolved relative to the
    # working directory by pywebview's http_server, so anchor it here rather than wherever
    # the shell happened to be when this was launched.
    os.chdir(ROOT)

    api = ExtractorApi()
    webview.create_window(
        'Document Image Extractor',
        'index.html',
        js_api=api,
        width=1180,
        height=820,
        resizable=True,
        background_color='#0a0a0b',
    )
    # Devtools are opt-in rather than always on.
    debug = os.environ.get("IE_DEBUG", "").lower() in ("1", "true", "yes")
    webview.start(debug=debug, http_server=True)


if __name__ == '__main__':
    main()
