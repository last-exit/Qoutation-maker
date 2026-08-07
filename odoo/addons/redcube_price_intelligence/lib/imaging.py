# -*- coding: utf-8 -*-
"""Image normalization for the indexer.

The desktop build wrote photos to a content-addressed directory and stored the hash. Inside
Odoo that job belongs to `ir.attachment`, which already deduplicates by checksum in the
filestore — so this module stops at "normalize and hash", and the indexer hands the bytes to
an `fields.Image` column.

Normalizing *before* hashing is what makes deduplication work: the same photo exported as PNG
from one spreadsheet and as JPEG from another lands on identical bytes and one stored file.
On the live archive that collapsed 352 references to 205 distinct images.

JPEG rather than PNG. These are photographs; re-encoding the live library at q85 was 6.8x
smaller with no visible difference at the size they print.
"""
import hashlib
import io

from PIL import Image as PILImage

MAX_EDGE = (900, 900)
JPEG_QUALITY = 85

# Bytes for the current indexing run, keyed by hash. Parsing walks documents and yields
# hashes; the indexer then pulls the bytes back out to write onto records. Held in memory
# rather than on disk because a full archive is a few hundred photos at ~30 KB each, and a
# temp directory would need cleaning up on every failure path.
_blobs = {}


def reset():
    """Drops the run cache. Called at the start and end of every index."""
    _blobs.clear()


def blob_count():
    return len(_blobs)


def blob_bytes():
    return sum(len(v) for v in _blobs.values())


def get_blob(image_hash):
    return _blobs.get(image_hash)


def normalize(raw_bytes):
    """Decodes arbitrary image bytes, re-encodes to a bounded RGB JPEG, returns (bytes, hash).

    Returns (None, None) for anything Pillow cannot read — a decorative shape, an unsupported
    WMF, or a corrupt embedded object. Callers treat that as "this row has no photo", which is
    the correct outcome rather than failing the whole document.
    """
    if not raw_bytes:
        return None, None
    try:
        pil_img = PILImage.open(io.BytesIO(raw_bytes))
        if pil_img.mode == "RGBA":
            # Flatten onto white rather than letting the alpha channel drop to black when
            # JPEG discards it.
            flattened = PILImage.new("RGB", pil_img.size, (255, 255, 255))
            flattened.paste(pil_img, mask=pil_img.split()[-1])
            pil_img = flattened
        elif pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")

        # LANCZOS because these end up printed, and the default filter leaves visible
        # aliasing on product photos with fine detail (truss, mesh, lettering).
        pil_img.thumbnail(MAX_EDGE, PILImage.LANCZOS)

        stream = io.BytesIO()
        pil_img.save(stream, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        data = stream.getvalue()
    except Exception:
        return None, None

    digest = hashlib.sha256(data).hexdigest()
    _blobs.setdefault(digest, data)
    return data, digest


def store(raw_bytes):
    """Normalizes and caches, returning just the hash (or "" so callers can treat it as text)."""
    _, digest = normalize(raw_bytes)
    return digest or ""
