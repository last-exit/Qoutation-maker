"""Puts an image on the operating system's clipboard.

Kept out of `main.py` so it is testable without a GUI toolkit loaded, and out of the browser
so it works the same way on every platform. The page's own `navigator.clipboard` would have
been simpler, but it only accepts PNG, needs a secure context, and fails silently in an
embedded webview — a copy button that quietly does nothing is worse than no copy button.

Each platform wants a different form of the same picture:

* **Windows** — CF_DIB, which is a BMP with its 14-byte file header removed. This is the
  format Word, Excel, PowerPoint and Paint all read.
* **macOS** — AppleScript reading a file as a picture; it needs a real path, not bytes.
* **Linux** — `xclip`, likewise from a file, advertised as `image/png`.

Every path returns (ok, error) rather than raising: a clipboard is an OS-level resource that
can be locked by another application, and a failed copy must surface as a message rather
than take the window down.
"""
import io
import os
import subprocess
import sys
import tempfile

from PIL import Image


def _to_dib(raw_bytes):
    """BMP bytes with the 14-byte file header stripped — the CF_DIB payload Windows wants."""
    image = Image.open(io.BytesIO(raw_bytes))
    if image.mode != "RGB":
        image = image.convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="BMP")
    return buffer.getvalue()[14:]


def _copy_windows(raw_bytes):
    import win32clipboard

    data = _to_dib(raw_bytes)
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
    finally:
        win32clipboard.CloseClipboard()
    return True, None


def _with_temp_file(raw_bytes, suffix, run):
    """Writes bytes somewhere the OS tool can read them, and always cleans up after."""
    handle, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(handle, "wb") as fh:
            fh.write(raw_bytes)
        return run(path)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _copy_macos(raw_bytes):
    def run(path):
        script = f'set the clipboard to (read (POSIX file "{path}") as JPEG picture)'
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        if result.returncode != 0:
            return False, (result.stderr or "").strip() or "osascript refused the image."
        return True, None

    return _with_temp_file(raw_bytes, ".jpg", run)


def _copy_linux(raw_bytes):
    def run(path):
        try:
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-t", "image/png", "-i", path],
                capture_output=True, text=True,
            )
        except FileNotFoundError:
            return False, "xclip is not installed — install it to copy images."
        if result.returncode != 0:
            return False, (result.stderr or "").strip() or "xclip refused the image."
        return True, None

    # PNG, because that is what xclip is told it is being handed.
    png = io.BytesIO()
    Image.open(io.BytesIO(raw_bytes)).convert("RGB").save(png, format="PNG")
    return _with_temp_file(png.getvalue(), ".png", run)


def copy_text(text):
    """Copies plain text (used for file paths). Returns (ok, error)."""
    if not text:
        return False, "Nothing to copy."
    try:
        if sys.platform == "win32":
            import win32clipboard

            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
            finally:
                win32clipboard.CloseClipboard()
            return True, None

        command = ["pbcopy"] if sys.platform == "darwin" else ["xclip", "-selection", "clipboard"]
        try:
            subprocess.run(command, input=text, text=True, check=True)
        except FileNotFoundError:
            return False, f"{command[0]} is not installed."
        return True, None
    except Exception as exc:
        return False, str(exc)


def copy_image(raw_bytes):
    """Copies image bytes to the clipboard. Returns (ok, error)."""
    if not raw_bytes:
        return False, "That image is missing from the store."
    try:
        if sys.platform == "win32":
            return _copy_windows(raw_bytes)
        if sys.platform == "darwin":
            return _copy_macos(raw_bytes)
        return _copy_linux(raw_bytes)
    except Exception as exc:
        return False, str(exc)
