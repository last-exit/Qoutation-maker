"""Writes an extraction run out in the form a human can actually use.

The store keeps one copy of every image under its hash, which is right for deduplication and
useless for browsing: `store/a3/a3f9...jpg` tells you nothing about where the picture came
from. So a run is also exported as readable files - `out/<document>/<document>_<where>.jpg` -
next to a `manifest.json` that carries the full record for anything reading this
programmatically.

An image appearing in two documents is still written once. The manifest lists it twice, once
per place it was found, both entries pointing at the same exported file.
"""
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import store

ROOT = Path(__file__).resolve().parent
DEFAULT_OUT_DIR = ROOT / "out"
MANIFEST_SCHEMA = 1

# Windows rejects these outright and they break paths everywhere else. Control characters go
# too - a sheet name can legally contain them, a filename cannot.
_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
# Whitespace and dashes collapse; the underscore does not, because it is the separator
# between a name's own fields (document_where_nn).
_COLLAPSE = re.compile(r"[\s-]+")
MAX_NAME_PART = 60


def slugify(value, fallback="image"):
    """A filename-safe fragment: illegal characters out, runs of separators collapsed."""
    text = _ILLEGAL.sub("-", str(value or "")).strip()
    text = _COLLAPSE.sub("-", text).strip("-.")
    return (text[:MAX_NAME_PART] or fallback)


def _location_slug(record):
    """A short, readable description of where in the document the image sat."""
    kind = record.get("kind")
    if kind == "xlsx":
        parts = [record.get("sheet") or "sheet"]
        if record.get("cell"):
            parts.append(record["cell"])
        return slugify("-".join(parts), "sheet")
    if kind == "pdf":
        return f"p{record.get('page', 0)}"
    if kind == "docx":
        placement = record.get("placement")
        if placement == "table-cell" and record.get("table"):
            return f"t{record['table']}-r{record.get('row', 0)}c{record.get('column', 0)}"
        if placement == "unplaced":
            return "unplaced"
        if record.get("paragraph"):
            return f"para{record['paragraph']}"
    return "image"


def _unique_path(directory, stem, suffix=".jpg"):
    """`stem.jpg`, or `stem-2.jpg` and so on. Never overwrites an existing file."""
    candidate = directory / f"{stem}{suffix}"
    counter = 2
    while candidate.exists():
        candidate = directory / f"{stem}-{counter}{suffix}"
        counter += 1
    return candidate


def export(result, out_dir=None):
    """Writes readable copies plus `manifest.json` for an `extract.extract_files` result.

    Returns {"success", "out_dir", "manifest", "written", "missing"} - `written` counts files
    actually created (one per distinct image), `missing` lists refs whose bytes were not in
    the store, which would mean the store was moved or partially copied.
    """
    out_dir = Path(out_dir) if out_dir else DEFAULT_OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    exported_by_ref = {}
    manifest_images = []
    missing = []
    written = 0

    for record in result.get("images", []):
        ref = record.get("ref")
        entry = dict(record)
        stored = store.path_for(ref)
        entry["stored_path"] = str(stored) if stored else ""

        if ref in exported_by_ref:
            # Same picture, second sighting. One file, two manifest entries.
            entry["exported_path"] = exported_by_ref[ref]
            entry["duplicate_of"] = exported_by_ref[ref]
            manifest_images.append(entry)
            continue

        if not stored or not stored.exists():
            missing.append(ref)
            entry["exported_path"] = ""
            manifest_images.append(entry)
            continue

        doc_stem = slugify(Path(record.get("source_file", "document")).stem, "document")
        doc_dir = out_dir / doc_stem
        doc_dir.mkdir(parents=True, exist_ok=True)

        stem = f"{doc_stem}_{_location_slug(record)}_{record.get('index', 0):02d}"
        destination = _unique_path(doc_dir, slugify(stem, "image"))
        shutil.copyfile(stored, destination)
        written += 1

        relative = destination.relative_to(out_dir).as_posix()
        exported_by_ref[ref] = relative
        entry["exported_path"] = relative
        manifest_images.append(entry)

    manifest = {
        "schema": MANIFEST_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "counts": {
            **(result.get("counts") or {}),
            "written": written,
            "missing": len(missing),
        },
        "files": result.get("files", []),
        "skipped": result.get("skipped", []),
        "warnings": result.get("warnings", []),
        "images": manifest_images,
    }

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "success": True,
        "out_dir": str(out_dir),
        "manifest": str(manifest_path),
        "written": written,
        "missing": missing,
    }
