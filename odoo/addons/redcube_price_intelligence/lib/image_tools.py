# -*- coding: utf-8 -*-
"""Image extraction backend for the ported parser.

`parsing.py` is carried over from the desktop build essentially verbatim, so it still calls
`store_embedded_image` / `store_raw_bytes` and expects a short string back. Here those return
a content hash into `imaging`'s run cache instead of writing a file, which keeps the parser
unchanged and lets the Odoo layer decide where bytes actually live.
"""
import io

from . import imaging


def store_embedded_image(img):
    """Pulls raw bytes out of an openpyxl drawing and normalizes them. Returns a hash or ""."""
    try:
        raw_data = None
        if hasattr(img, 'ref') and img.ref:
            if hasattr(img.ref, 'read'):
                try:
                    img.ref.seek(0)
                    raw_data = img.ref.read()
                except Exception:
                    pass
            elif hasattr(img.ref, 'save'):
                buf = io.BytesIO()
                img.ref.save(buf, format="PNG")
                raw_data = buf.getvalue()
        if raw_data is None and hasattr(img, '_data') and img._data:
            try:
                raw_data = img._data()
            except Exception:
                pass
        if raw_data:
            return imaging.store(raw_data)
    except Exception:
        # A drawing that cannot be read means this row has no photo, not that the document
        # failed. The desktop build printed here; inside Odoo that goes nowhere useful.
        pass
    return ""


def store_raw_bytes(raw_bytes):
    """Normalizes bytes taken straight from a document part (docx relationship, pdf xref)."""
    return imaging.store(raw_bytes)
