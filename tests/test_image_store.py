"""The content-addressed image store — deduplication, refs, and legacy compatibility."""
import base64

import pytest


def test_stores_and_resolves(temp_images, png_bytes):
    ref = temp_images.store_bytes(png_bytes())
    assert temp_images.is_ref(ref)
    assert temp_images.exists(ref)
    assert temp_images.read_bytes(ref) is not None


def test_identical_images_collapse_to_one_file(temp_images, png_bytes):
    """The whole point of hashing: 352 indexed items held only 206 distinct photos."""
    raw = png_bytes()
    first = temp_images.store_bytes(raw)
    second = temp_images.store_bytes(raw)
    assert first == second
    assert temp_images.stats()["count"] == 1


def test_different_images_get_different_refs(temp_images, png_bytes):
    a = temp_images.store_bytes(png_bytes(color=(10, 10, 10)))
    b = temp_images.store_bytes(png_bytes(color=(240, 240, 240)))
    assert a != b
    assert temp_images.stats()["count"] == 2


def test_png_and_jpeg_of_same_picture_dedupe(temp_images, png_bytes):
    """Normalizing before hashing is what makes this work — the same photo arriving as PNG
    from one spreadsheet and JPEG from another must not occupy two files."""
    import io

    from PIL import Image

    raw_png = png_bytes(color=(120, 90, 60), size=(80, 80))
    buf = io.BytesIO()
    Image.open(io.BytesIO(raw_png)).save(buf, format="JPEG", quality=95)

    ref_png = temp_images.store_bytes(raw_png)
    ref_jpeg = temp_images.store_bytes(buf.getvalue())
    assert ref_png == ref_jpeg


def test_stored_form_is_jpeg(temp_images, png_bytes):
    """PNG in, JPEG out. Re-encoding photographs was 6.8x smaller on the live library."""
    stored = temp_images.read_bytes(temp_images.store_bytes(png_bytes()))
    assert stored[:2] == b"\xff\xd8"  # JPEG SOI marker


def test_photographic_content_compresses_well(temp_images):
    """A photograph must not survive the store at anything close to its raw pixel size."""
    import io
    import random

    from PIL import Image

    rng = random.Random(0)
    # Smooth, noisy, photograph-like content rather than a synthetic repeating pattern —
    # the latter is compressible in ways real product photos are not.
    img = Image.new("RGB", (900, 900))
    img.putdata([(rng.randint(90, 160), rng.randint(60, 130), rng.randint(40, 110))
                 for _ in range(900 * 900)])
    img = img.resize((900, 900), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    stored = temp_images.read_bytes(temp_images.store_bytes(buf.getvalue()))
    assert len(stored) < 900 * 900 * 3 / 4


def test_large_image_is_bounded(temp_images):
    from PIL import Image
    import io

    buf = io.BytesIO()
    Image.new("RGB", (3000, 2000), (5, 5, 5)).save(buf, format="PNG")
    ref = temp_images.store_bytes(buf.getvalue())

    out = Image.open(io.BytesIO(temp_images.read_bytes(ref)))
    assert max(out.size) <= max(temp_images.MAX_EDGE)


def test_rgba_is_flattened_not_blackened(temp_images):
    """JPEG has no alpha channel; dropping it without flattening turns transparency black."""
    from PIL import Image
    import io

    img = Image.new("RGBA", (40, 40), (255, 0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    ref = temp_images.store_bytes(buf.getvalue())
    out = Image.open(io.BytesIO(temp_images.read_bytes(ref))).convert("RGB")
    assert out.getpixel((20, 20)) == pytest.approx((255, 255, 255), abs=8)


def test_ingest_accepts_ref_data_uri_and_bytes(temp_images, png_bytes):
    raw = png_bytes()
    ref = temp_images.store_bytes(raw)
    data_uri = "data:image/png;base64," + base64.b64encode(raw).decode()

    assert temp_images.ingest(ref) == ref
    assert temp_images.ingest(data_uri) == ref
    assert temp_images.ingest(raw) == ref


def test_ingest_rejects_garbage(temp_images):
    assert temp_images.ingest("not an image at all") is None
    assert temp_images.ingest("") is None
    assert temp_images.ingest(None) is None


def test_resolve_bytes_handles_legacy_data_uri(temp_images, png_bytes):
    """Quotations saved before the store existed hold inline base64 and must still render."""
    data_uri = "data:image/png;base64," + base64.b64encode(png_bytes()).decode()
    assert temp_images.resolve_bytes(data_uri) is not None


def test_web_src_passes_legacy_data_uri_through(temp_images, png_bytes):
    data_uri = "data:image/png;base64," + base64.b64encode(png_bytes()).decode()
    assert temp_images.web_src(data_uri) == data_uri


def test_web_src_is_a_relative_sharded_path(temp_images, png_bytes):
    ref = temp_images.store_bytes(png_bytes())
    assert temp_images.web_src(ref) == f"images/{ref[:2]}/{ref}.jpg"


def test_missing_file_reads_as_none_not_an_error(temp_images):
    assert temp_images.read_bytes("0" * 64) is None


def test_orphans_are_files_nothing_references(temp_images, png_bytes):
    kept = temp_images.store_bytes(png_bytes(color=(1, 2, 3)))
    dropped = temp_images.store_bytes(png_bytes(color=(9, 9, 9)))

    orphans = temp_images.collect_orphans({kept})
    assert [p.stem for p in orphans] == [dropped]


def test_no_temp_files_left_behind(temp_images, png_bytes):
    temp_images.store_bytes(png_bytes())
    assert list(temp_images.IMAGE_DIR.rglob("*.tmp")) == []
