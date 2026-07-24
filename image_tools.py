"""Image helpers: embedded-image thumbnailing, best-effort online image search, URL/file encoding.

Every network-touching function here fails soft (returns success: False) so the core
offline workflow never breaks if there is no internet connection.
"""
import io
import re
import base64

import requests
from PIL import Image as PILImage

THUMB_SIZE = (250, 250)
_SEARCH_TIMEOUT = 4
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) QuotationEngine/1.0"}


def pil_to_base64(pil_img, fmt="PNG"):
    buffered = io.BytesIO()
    pil_img.save(buffered, format=fmt)
    img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
    mime = "image/png" if fmt.upper() == "PNG" else "image/jpeg"
    return f"data:{mime};base64,{img_str}"


def bytes_to_thumbnail_base64(raw_bytes, size=THUMB_SIZE):
    pil_img = PILImage.open(io.BytesIO(raw_bytes))
    pil_img_copy = pil_img.convert("RGB") if pil_img.mode in ("P", "CMYK") else pil_img.copy()
    pil_img_copy.thumbnail(size)
    return pil_to_base64(pil_img_copy)


def get_embedded_image_base64(img):
    """Extracts image data from an openpyxl drawing image, resizes, and encodes to base64."""
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
            return bytes_to_thumbnail_base64(raw_data)
    except Exception as e:
        print(f"Error extracting embedded image: {e}")
    return ""


def fetch_image_as_base64(url, timeout=6):
    """Downloads an arbitrary image URL, resizes, and returns a base64 data URI. Best-effort."""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=timeout)
        resp.raise_for_status()
        return {"success": True, "image_base64": bytes_to_thumbnail_base64(resp.content)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def bytes_from_local_file(file_path):
    """Reads and thumbnails a locally uploaded image file. Fully offline."""
    try:
        with open(file_path, "rb") as f:
            raw = f.read()
        return {"success": True, "image_base64": bytes_to_thumbnail_base64(raw)}
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
