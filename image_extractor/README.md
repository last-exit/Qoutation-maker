# Document Image Extractor

Pulls every embedded image out of Excel, Word and PDF documents, stores each one exactly
once, and writes them out with names that say where they came from.

This is a **separate project that happens to live in this repository**. It shares no code,
no database and no configuration with the quotation app in the folder above — it was carved
out of it, and the two are now independent. Nothing here imports anything from there, and
nothing there imports anything from here.

## Run it

```bash
python image_extractor/main.py
```

Or `run.bat` (Windows) / `run.sh` (macOS, Linux), which build a virtualenv in this folder on
first launch and reuse it afterwards.

Drop documents onto the window, or press **Choose Documents** (clicking the drop zone opens
the same dialog). Thumbnails appear as they are found; **Export Images** writes them out.

Dropped files are read *in the page* and sent across as bytes, rather than relying on
pywebview attaching a filesystem path to the drop event — that path is not always there, and
when it is missing a drop does nothing at all with no error to explain why.

## Viewing and copying

Click any result to **open** it in a panel over the window — big enough to read a drawing,
capped at 82% of the window so the grid stays visible behind it. Arrow keys step through the
run, `Esc` closes it, and clicking the backdrop does too.

**Copy** — on the card or in the viewer — puts the picture on the system clipboard at full
stored resolution, ready to paste straight into Word, Excel, PowerPoint, Paint or a chat
window. **Copy All Paths** puts the file paths of every image from the run on the clipboard
instead, which is what a folder window or an email attachment box wants.

The copy is done in Python rather than through the page's `navigator.clipboard`, which only
accepts PNG, needs a secure context, and fails silently inside an embedded webview. On
Windows the image goes on as `CF_DIB`; macOS uses AppleScript and Linux uses `xclip`. If the
clipboard is locked by another application, you get a message rather than a dead button.

## What it reads

| Format | Where the images hide | What gets recorded |
|---|---|---|
| `.xlsx` `.xlsm` | drawings anchored to a cell, on every worksheet | sheet name, anchor cell (`Costs!C7`) |
| `.docx` | pictures in table cells and body paragraphs, plus headers/footers/floating shapes | table + row + column, or paragraph number, or `unplaced` |
| `.pdf` | embedded images per page | page number and bounding box |

Every image in the document is taken. There is no filtering by column heading, no guessing
about which picture "belongs" to a priced row — that judgement lived in the quotation app and
stayed there.

## What comes out

Two forms, both written on every export:

* **`store/<ab>/<sha256>.jpg`** — the content-addressed store. Each image is normalized
  (transparency flattened onto white, bounded to 900px, JPEG q85) and named by the hash of
  the result. The same picture appearing in five documents is one file on disk.
* **`out/<document>/<document>_<where>_<nn>.jpg`** — readable copies, one folder per source
  document, plus **`out/manifest.json`** carrying the full record for every image: its ref,
  both paths, the source document, and exactly where inside it the image sat.

Normalizing *before* hashing is what makes deduplication work: the same photo exported as
PNG from a spreadsheet and as JPEG from a PDF lands on identical bytes.

## What it deliberately does not do

No pricing, no rate cards, no line-item parsing, no venue or date inference, no semantic
search or embeddings, no databases, no document generation. If you want any of that, it is
one folder up and still works exactly as it did.

One thing was left behind on purpose: the quotation app's `assign_images_to_rows`, which
awards a PDF image to the table row it visually overlaps. That needs extracted priced rows to
define the row bands, and there are none here. Its input is kept instead — every PDF record
carries `bbox`, `y0` and `y1`, so nothing positional is lost.

## Tests

```bash
python -m pytest image_extractor/tests -q
```

Every fixture document (`.xlsx`, `.docx`, `.pdf`) is built at runtime rather than committed,
so there are no binary fixtures and each test knows its documents down to the pixel.

The suite is not wired into the repository's CI workflow, which runs the quotation app's
`tests/` only.
