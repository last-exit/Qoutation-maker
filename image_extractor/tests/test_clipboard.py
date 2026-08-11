"""Copying an extracted image to the system clipboard.

The clipboard write itself is the operating system's, so what is pinned here is everything
around it: the payload conversion, and the promise that a failure comes back as a message
rather than an exception through the JS bridge.
"""
import io
import sys

import pytest

import clipboard


def test_dib_payload_has_no_bmp_file_header(png_bytes):
    """CF_DIB is a BMP *without* its 14-byte file header. Leaving the header on is the
    classic version of this bug: every paste target shows garbage or nothing."""
    data = clipboard._to_dib(png_bytes())

    assert not data.startswith(b"BM")
    # What is left starts with the DIB header size (40 for BITMAPINFOHEADER).
    assert int.from_bytes(data[:4], "little") == 40


def test_dib_round_trips_back_to_the_same_picture(png_bytes):
    from PIL import Image

    raw = png_bytes(color=(12, 200, 90), size=(50, 40))
    data = clipboard._to_dib(raw)

    # Put the file header back and the bytes must open as the original picture.
    header = b"BM" + (14 + len(data)).to_bytes(4, "little") + b"\x00" * 4 + (14 + 40).to_bytes(4, "little")
    restored = Image.open(io.BytesIO(header + data))
    assert restored.size == (50, 40)
    assert restored.convert("RGB").getpixel((25, 20)) == pytest.approx((12, 200, 90), abs=8)


def test_rgba_is_flattened_before_copying(png_bytes):
    """BMP has no alpha; handing PIL an RGBA image would fail or paste black."""
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGBA", (30, 30), (255, 0, 0, 0)).save(buf, format="PNG")

    assert clipboard._to_dib(buf.getvalue())  # does not raise


def test_empty_bytes_are_refused_with_a_message():
    ok, error = clipboard.copy_image(b"")
    assert ok is False
    assert error


def test_unreadable_bytes_come_back_as_an_error_not_an_exception():
    ok, error = clipboard.copy_image(b"this is not an image")
    assert ok is False
    assert error


def test_a_locked_clipboard_is_reported_not_raised(monkeypatch, png_bytes):
    """Another application can hold the clipboard open. That must surface as a toast."""
    def boom(_raw):
        raise OSError("clipboard is held by another application")

    target = {"win32": "_copy_windows", "darwin": "_copy_macos"}.get(sys.platform, "_copy_linux")
    monkeypatch.setattr(clipboard, target, boom)

    ok, error = clipboard.copy_image(png_bytes())
    assert ok is False
    assert "another application" in error


def test_copy_image_by_ref_reads_from_the_store(temp_store, png_bytes, monkeypatch):
    import main

    ref = temp_store.store_bytes(png_bytes())
    copied = {}
    monkeypatch.setattr(clipboard, "copy_image", lambda raw: (copied.update(bytes=raw) or (True, None)))

    assert main.ExtractorApi().copy_image(ref) == {"success": True}
    assert copied["bytes"] == temp_store.read_bytes(ref)


def test_copying_an_image_that_is_no_longer_stored(temp_store):
    import main

    result = main.ExtractorApi().copy_image("0" * 64)
    assert result["success"] is False
    assert "no longer in the store" in result["error"]


def test_copy_all_paths_dedupes_and_needs_a_run(temp_store, png_bytes, monkeypatch):
    import main

    ref = temp_store.store_bytes(png_bytes())
    api = main.ExtractorApi()

    assert api.copy_all_images()["success"] is False  # nothing extracted yet

    api.last_result = {"images": [{"ref": ref}, {"ref": ref}]}  # same picture, two sightings
    captured = {}
    monkeypatch.setattr(clipboard, "copy_text", lambda text: (captured.update(text=text) or (True, None)))

    result = api.copy_all_images()
    assert result == {"success": True, "count": 1}
    assert captured["text"] == str(temp_store.path_for(ref))
