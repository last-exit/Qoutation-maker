"""The content-addressed store — deduplication, refs, and the guarantees the rest relies on."""
import base64
import io

import pytest


def test_stores_and_resolves(temp_store, png_bytes):
    ref = temp_store.store_bytes(png_bytes())
    assert temp_store.is_ref(ref)
    assert temp_store.exists(ref)
    assert temp_store.read_bytes(ref) is not None


def test_identical_images_collapse_to_one_file(temp_store, png_bytes):
    """The whole point of hashing: the same photo in three documents is one file on disk."""
    raw = png_bytes()
    first = temp_store.store_bytes(raw)
    second = temp_store.store_bytes(raw)
    assert first == second
    assert temp_store.stats()["count"] == 1


def test_different_images_get_different_refs(temp_store, png_bytes):
    a = temp_store.store_bytes(png_bytes(color=(10, 10, 10)))
    b = temp_store.store_bytes(png_bytes(color=(240, 240, 240)))
    assert a != b
    assert temp_store.stats()["count"] == 2


def test_png_and_jpeg_of_same_picture_dedupe(temp_store, png_bytes):
    """Normalizing before hashing is what makes this work — the same picture arriving as PNG
    from a spreadsheet and JPEG from a PDF must not occupy two files."""
    from PIL import Image

    raw_png = png_bytes(color=(120, 90, 60), size=(80, 80))
    buf = io.BytesIO()
    Image.open(io.BytesIO(raw_png)).save(buf, format="JPEG", quality=95)

    assert temp_store.store_bytes(raw_png) == temp_store.store_bytes(buf.getvalue())


def test_stored_form_is_jpeg(temp_store, png_bytes):
    stored = temp_store.read_bytes(temp_store.store_bytes(png_bytes()))
    assert stored[:2] == b"\xff\xd8"  # JPEG SOI marker


def test_large_image_is_bounded(temp_store):
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (3000, 2000), (5, 5, 5)).save(buf, format="PNG")
    ref = temp_store.store_bytes(buf.getvalue())

    out = Image.open(io.BytesIO(temp_store.read_bytes(ref)))
    assert max(out.size) <= max(temp_store.MAX_EDGE)


def test_rgba_is_flattened_not_blackened(temp_store):
    """JPEG has no alpha channel; dropping it without flattening turns transparency black."""
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGBA", (40, 40), (255, 0, 0, 0)).save(buf, format="PNG")

    ref = temp_store.store_bytes(buf.getvalue())
    out = Image.open(io.BytesIO(temp_store.read_bytes(ref))).convert("RGB")
    assert out.getpixel((20, 20)) == pytest.approx((255, 255, 255), abs=8)


def test_ingest_accepts_ref_data_uri_and_bytes(temp_store, png_bytes):
    raw = png_bytes()
    ref = temp_store.store_bytes(raw)
    data_uri = "data:image/png;base64," + base64.b64encode(raw).decode()

    assert temp_store.ingest(ref) == ref
    assert temp_store.ingest(data_uri) == ref
    assert temp_store.ingest(raw) == ref


def test_ingest_rejects_garbage(temp_store):
    assert temp_store.ingest("not an image at all") is None
    assert temp_store.ingest("") is None
    assert temp_store.ingest(None) is None


def test_web_src_is_a_relative_sharded_path(temp_store, png_bytes):
    """The UI renders this straight into an <img src>, served by pywebview's HTTP server."""
    ref = temp_store.store_bytes(png_bytes())
    assert temp_store.web_src(ref) == f"store/{ref[:2]}/{ref}.jpg"


def test_missing_file_reads_as_none_not_an_error(temp_store):
    assert temp_store.read_bytes("0" * 64) is None


def test_no_temp_files_left_behind(temp_store, png_bytes):
    temp_store.store_bytes(png_bytes())
    assert list(temp_store.IMAGE_DIR.rglob("*.tmp")) == []
