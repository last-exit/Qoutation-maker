"""Image helpers: embedded-image extraction, best-effort online image search, URL/file import.

Every function that produces a photo now returns a content-addressed ref from `image_store`
rather than a base64 data URI. The bytes land on disk exactly once; databases and API
responses carry a 64-character hash. See image_store's docstring for why.

Every network-touching function here fails soft (returns success: False) so the core
offline workflow never breaks if there is no internet connection.
"""
import base64
import io
import re

import requests

import image_store

_SEARCH_TIMEOUT = 4
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) QuotationEngine/1.0"}


def pil_to_base64(image, fmt="PNG"):
    """Encodes a PIL image as a data: URI.

    Used for the design estimator's page previews, which are per-parse-session and never
    need a permanent home in image_store's content-addressed disk cache — unlike catalog
    photos, a drawing thumbnail is discarded the moment the PM clears or re-uploads it.
    """
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/{fmt.lower()};base64,{encoded}"


def _result_for(ref):
    """Uniform shape for the JS API: a ref for storage, a URL for rendering."""
    if not ref:
        return {"success": False, "error": "Could not read that image."}
    return {"success": True, "image_ref": ref, "image_src": image_store.web_src(ref)}


def store_embedded_image(img):
    """Extracts image data from an openpyxl drawing and stores it. Returns a ref or ""."""
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
            return image_store.store_bytes(raw_data) or ""
    except Exception as e:
        print(f"Error extracting embedded image: {e}")
    return ""


def store_raw_bytes(raw_bytes):
    """Stores bytes pulled straight out of a document part (docx/pdf). Returns a ref or ""."""
    return image_store.store_bytes(raw_bytes) or ""


def fetch_image_from_url(url, timeout=6):
    """Downloads an arbitrary image URL and stores it. Best-effort."""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=timeout)
        resp.raise_for_status()
        return _result_for(image_store.store_bytes(resp.content))
    except Exception as e:
        return {"success": False, "error": str(e)}


def import_local_file(file_path):
    """Reads a locally uploaded image file into the store. Fully offline."""
    try:
        with open(file_path, "rb") as f:
            raw = f.read()
        return _result_for(image_store.store_bytes(raw))
    except Exception as e:
        return {"success": False, "error": str(e)}


def fetch_image_suggestions(query, max_results=6):
    """Best-effort DuckDuckGo image search using only `requests` (no extra scraping deps).

    Scrapes the `vqd` search token from the DDG HTML search page, then queries the
    image-search JSON endpoint. Any failure (offline, endpoint change, blocked) returns
    success: False so callers can degrade gracefully instead of crashing.
    """
    try:
        session = requests.Session()
        session.headers.update(_HEADERS)

        token_resp = session.get(
            "https://duckduckgo.com/",
            params={"q": query},
            timeout=_SEARCH_TIMEOUT,
        )
        token_resp.raise_for_status()
        vqd_match = re.search(r'vqd=([\d-]+)', token_resp.text)
        if not vqd_match:
            return {"success": False, "error": "Could not resolve search token (no internet or DuckDuckGo blocked)."}
        vqd = vqd_match.group(1)

        img_resp = session.get(
            "https://duckduckgo.com/i.js",
            params={"l": "us-en", "o": "json", "q": query, "vqd": vqd, "f": ",,,", "p": "1"},
            timeout=_SEARCH_TIMEOUT,
        )
        img_resp.raise_for_status()
        data = img_resp.json()

        results = []
        for entry in data.get("results", [])[:max_results]:
            thumb = entry.get("thumbnail") or entry.get("image")
            source = entry.get("image") or entry.get("url")
            if thumb and source:
                results.append({"thumbnail_url": thumb, "source_url": source, "title": entry.get("title", "")})

        if not results:
            return {"success": False, "error": "No image results found."}

        return {"success": True, "results": results}
    except Exception as e:
        return {"success": False, "error": f"Image search unavailable (likely offline): {e}"}
