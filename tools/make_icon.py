"""Builds assets/app.ico from the logo, for the Windows executable and installer.

Windows picks a different size out of the .ico depending on where it draws the icon - 16px
in the title bar, 32px in the taskbar, 256px in the Add/Remove Programs list - so a
single-size icon looks either blurry or aliased somewhere. Pillow writes all of them into
one file.

    python tools/make_icon.py
"""

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "assets" / "red_cube_logo.png"
TARGET = ROOT / "assets" / "app.ico"

SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def build():
    image = Image.open(SOURCE).convert("RGBA")

    # Square it off on a transparent canvas first. Windows scales a non-square icon to fit
    # its box, which distorts the logo; padding keeps the aspect ratio.
    side = max(image.size)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(image, ((side - image.width) // 2, (side - image.height) // 2), image)

    # Pillow silently omits any requested size larger than the source, and Windows then
    # upscales the biggest one it finds - badly - for the 256px slot used by Add/Remove
    # Programs. Upscaling here with a good filter is the lesser evil, but the honest fix is
    # a larger source logo, so say so rather than shipping a soft icon quietly.
    largest = max(size[0] for size in SIZES)
    if side < largest:
        print(f"  note: {SOURCE.name} is {image.width}x{image.height}; upscaling to "
              f"{largest}px. A source logo of at least {largest}px would look sharper.")
        canvas = canvas.resize((largest, largest), Image.LANCZOS)

    canvas.save(TARGET, format="ICO", sizes=SIZES)
    return TARGET


if __name__ == "__main__":
    path = build()
    print(f"Wrote {path} ({path.stat().st_size / 1000:.1f} KB)")
