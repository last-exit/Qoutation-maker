"""Content-addressed store for product photos.

Photos used to be carried around as `data:image/png;base64,...` strings living directly in
ChromaDB metadata and in `history.db`'s items_json. That cost far more than it looked like:

  * Chroma keeps a B-tree index on `(key, string_value)` for metadata filtering, so every
    blob was stored a second time in the index, and a third time in `embeddings_queue`
    (its write log, which is never purged). 352 items came to 176 MB.
  * The same photo appearing in several quotes was stored once per occurrence — 352 rows
    held only 206 distinct images.
  * PNG is the wrong codec for photographs. Re-encoding the live library at JPEG q85 was
    6.8x smaller with no visible difference at the size these print.

Here a photo is written once to `images/<ab>/<sha256>.jpg` and referred to everywhere by its
hash. Identical bytes collapse to one file automatically, the databases carry 64 characters
instead of ~165 KB, and the UI loads pictures over normal <img> requests rather than pushing
megabytes of base64 across the pywebview bridge on every keystroke.
"""
import base64
import hashlib
import io
import os
import re

from PIL import Image as PILImage

import paths

ROOT = paths.data_root()
IMAGE_DIR = paths.data_path("images")

# Stored resolution. These are not just UI thumbnails — the same bytes are embedded into the
# generated Word/Excel quotation, where 250px rendered at print size looked visibly soft.
# 900px keeps ~300 DPI at a 3.4cm print width with room to spare.
MAX_EDGE = (900, 900)
JPEG_QUALITY = 85

_REF_RE = re.compile(r"^[0-9a-f]{64}$")
_DATA_URI_RE = re.compile(r"^data:image/[a-zA-Z.+-]+;base64,", re.IGNORECASE)


def _ensure_dir():
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)


def is_ref(value):
    """True for a stored image reference (a bare sha256 hex digest)."""
    return bool(value) and isinstance(value, str) and bool(_REF_RE.match(value.strip()))


def is_data_uri(value):
    return bool(value) and isinstance(value, str) and bool(_DATA_URI_RE.match(value.strip()))


def _normalize(raw_bytes):
    """Decodes arbitrary image bytes and re-encodes to a bounded-size RGB JPEG.

    Normalizing before hashing is what makes the store deduplicate properly: the same photo
    exported as PNG from one spreadsheet and as JPEG from another lands on identical bytes,
    so it occupies one file instead of two.
    """
    pil_img = PILImage.open(io.BytesIO(raw_bytes))
    if pil_img.mode == "RGBA":
        # Flatten transparency onto white rather than letting the alpha channel drop to
        # black when JPEG discards it.
        flattened = PILImage.new("RGB", pil_img.size, (255, 255, 255))
        flattened.paste(pil_img, mask=pil_img.split()[-1])
        pil_img = flattened
    elif pil_img.mode != "RGB":
        pil_img = pil_img.convert("RGB")

    # LANCZOS over the default filter: these end up printed, and the default leaves visible
    # aliasing on product photos with fine detail (truss, mesh, lettering).
    pil_img.thumbnail(MAX_EDGE, PILImage.LANCZOS)

    stream = io.BytesIO()
    pil_img.save(stream, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return stream.getvalue()


def path_for(ref):
    """Filesystem location of a ref. Sharded on the first two hex characters so the
    directory stays browsable once the library runs to thousands of photos."""
    if not is_ref(ref):
        return None
    ref = ref.strip()
    return IMAGE_DIR / ref[:2] / f"{ref}.jpg"


def exists(ref):
    p = path_for(ref)
    return bool(p and p.exists())


def store_bytes(raw_bytes):
    """Normalizes, hashes and writes. Returns the ref, or None if the bytes aren't an image."""
    if not raw_bytes:
        return None
    try:
        normalized = _normalize(raw_bytes)
    except Exception:
        return None

    ref = hashlib.sha256(normalized).hexdigest()
    dest = path_for(ref)
    if dest.exists():
        return ref

    _ensure_dir()
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Write to a temp name and rename so a crash mid-write can never leave a truncated file
    # sitting at a hash that claims to describe complete content.
    tmp = dest.with_suffix(".jpg.tmp")
    with open(tmp, "wb") as fh:
        fh.write(normalized)
    os.replace(tmp, dest)
    return ref


def store_data_uri(value):
    """Accepts `data:image/...;base64,xxx` or a bare base64 payload."""
    if not value or not isinstance(value, str):
        return None
    payload = value.split(",", 1)[1] if "," in value else value
    try:
        raw = base64.b64decode(payload)
    except Exception:
        return None
    return store_bytes(raw)


def ingest(value):
    """Normalizes any image field to a ref.

    Tolerates all three shapes that exist in the wild: an already-stored ref (returned
    untouched), a legacy data URI from before this module existed, and raw bytes.
    """
    if not value:
        return None
    if isinstance(value, (bytes, bytearray)):
        return store_bytes(bytes(value))
    if is_ref(value):
        return value.strip()
    return store_data_uri(value)


def read_bytes(ref):
    """Raw JPEG bytes for a ref, or None if the file is missing.

    Callers must handle None: the store is a directory of loose files, and a photo can go
    missing if the folder is restored from a partial backup.
    """
    p = path_for(ref)
    if not p or not p.exists():
        return None
    try:
        with open(p, "rb") as fh:
            return fh.read()
    except OSError:
        return None


def resolve_bytes(value):
    """Bytes for either a ref or a legacy inline data URI, so document generation keeps
    working against history records written before the migration."""
    if not value:
        return None
    if is_ref(value):
        return read_bytes(value)
    payload = value.split(",", 1)[1] if "," in value else value
    try:
        return base64.b64decode(payload)
    except Exception:
        return None


def web_src(ref):
    """Relative URL for an <img> tag. The app is served by pywebview's built-in HTTP server
    rooted at this directory, so a relative path resolves without embedding any bytes in the
    page or moving them across the JS bridge."""
    if not is_ref(ref):
        # A legacy data URI is already a usable src; anything else renders as nothing.
        return ref if is_data_uri(ref) else ""
    ref = ref.strip()
    return f"images/{ref[:2]}/{ref}.jpg"


def to_data_uri(ref):
    """Inline form, for the few places that genuinely need bytes in the page (clipboard
    export, the mailto attachment path). Avoid in list rendering."""
    raw = read_bytes(ref)
    if raw is None:
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii")


def stats():
    if not IMAGE_DIR.exists():
        return {"count": 0, "bytes": 0}
    count = 0
    total = 0
    for p in IMAGE_DIR.rglob("*.jpg"):
        count += 1
        total += p.stat().st_size
    return {"count": count, "bytes": total}


def collect_orphans(live_refs):
    """Stored images no live record points at. Returned rather than deleted so the caller
    decides — an empty `live_refs` means "nothing referenced anything", which is far more
    likely to be a bug in the caller than a genuine instruction to wipe the library."""
    if not IMAGE_DIR.exists():
        return []
    live = {r.strip() for r in live_refs if is_ref(r)}
    orphans = []
    for p in IMAGE_DIR.rglob("*.jpg"):
        if p.stem not in live:
            orphans.append(p)
    return orphans
