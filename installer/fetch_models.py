"""Downloads every model the app needs, ahead of time, into the build tree.

The installed app must work with no internet. Three separate things in this stack disagree
with that by default, and each one downloads at the moment it is first actually used - which
in practice means the first time someone parses a real drawing, in front of a client:

  * easyocr fetches its detector (~83 MB) and recognizer (~15 MB) on the first `Reader(...)`.
  * embedder.py needs `models/all-MiniLM-L6-v2/model.onnx` (~91 MB), which is gitignored and
    so absent from a fresh clone.
  * chromadb's own default embedding function downloads a *second* copy of MiniLM to
    `~/.cache/chroma`. The app does not use it - `embedder.py` supplies vectors directly -
    but a stray call to a default-constructed collection would trigger it.

Run this on the build machine before PyInstaller. It is safe to re-run: anything already
present with a matching checksum is left alone.

    python installer/fetch_models.py
"""

import hashlib
import io
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EASYOCR_DIR = ROOT / "models" / "easyocr"
ONNX_DIR = ROOT / "models" / "all-MiniLM-L6-v2"


def _md5(path):
    digest = hashlib.md5()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download_and_unzip(url, filename, md5sum, destination):
    """Fetch a zipped model and drop the weight file flat into `destination`.

    easyocr expects the `.pth` sitting directly in its model directory, not nested inside
    the zip's folder structure, so the member is extracted by name rather than with
    `extractall`.
    """
    target = destination / filename
    if target.exists():
        if md5sum and _md5(target) == md5sum:
            print(f"  {filename} already present and verified")
            return
        print(f"  {filename} present but checksum differs - refetching")
        target.unlink()

    destination.mkdir(parents=True, exist_ok=True)
    print(f"  downloading {filename} from {url}")
    with urllib.request.urlopen(url) as response:
        payload = response.read()

    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        member = next((n for n in archive.namelist() if n.endswith(filename)), None)
        if member is None:
            raise RuntimeError(f"{filename} not found inside {url}")
        with archive.open(member) as source, open(target, "wb") as sink:
            shutil.copyfileobj(source, sink)

    if md5sum and _md5(target) != md5sum:
        raise RuntimeError(f"{filename} downloaded but the checksum does not match")
    print(f"  {filename} ready ({target.stat().st_size / 1_000_000:.0f} MB)")


def fetch_easyocr():
    """The English detector and recognizer.

    URLs and checksums are read from easyocr's own config rather than copied here, so they
    cannot drift out of step with the pinned version.
    """
    print("easyocr models:")
    try:
        import easyocr.config as config
    except ImportError:
        print("  easyocr is not installed - install requirements.txt first", file=sys.stderr)
        raise

    detector = config.detection_models["craft"]
    recognizer = config.recognition_models["gen2"]["english_g2"]

    for spec in (detector, recognizer):
        _download_and_unzip(spec["url"], spec["filename"], spec.get("md5sum"), EASYOCR_DIR)


def check_onnx():
    """The MiniLM ONNX export the search index runs on.

    This one is not downloadable - it is produced by `tools/export_onnx.py` from the
    sentence-transformers weights. It is gitignored, so a fresh clone of the repo on the
    build machine will not have it, and a bundle built without it ships an app whose search
    silently falls back to a dependency that is not installed.
    """
    print("search model:")
    model = ONNX_DIR / "model.onnx"
    tokenizer = ONNX_DIR / "tokenizer.json"
    if model.exists() and tokenizer.exists():
        print(f"  model.onnx present ({model.stat().st_size / 1_000_000:.0f} MB)")
        return True

    print(f"  MISSING: {model}", file=sys.stderr)
    print("  Produce it with:  python tools/export_onnx.py", file=sys.stderr)
    print("  or copy models/all-MiniLM-L6-v2/ from a machine that already has it.",
          file=sys.stderr)
    return False


if __name__ == "__main__":
    fetch_easyocr()
    ok = check_onnx()
    if not ok:
        print("\nThe search model is missing. Fix that before building.", file=sys.stderr)
        sys.exit(1)
    print("\nAll models present.")
