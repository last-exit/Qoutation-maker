# Handover checklist — setting the app up for the PM

Written for the first install on someone else's machine. The app has run on exactly one
laptop for most of its life, and every bug found on the night before handover was of the
same kind: something that was true on the developer's machine and nowhere else. Work
through this on the target machine, not on the machine it was built on.

## 1. Install from a clean copy — do this first

```bat
git clone https://github.com/last-exit/Qoutation-maker.git
cd Qoutation-maker
run.bat
```

The window should open. If it does not, the message in `logs/quotation_engine.log` names
the cause.

This step exists because it is the one that catches real problems. `cryptography` was
missing from `requirements.txt` for months — the app imported it at startup, so a fresh
install died before the window appeared, while working perfectly on the developer's laptop.
CI found it the night before handover. Nothing here substitutes for running it where it
will actually be used.

## 2. Enable OCR and shape detection (needed for PNG/JPG drawings)

Vector PDFs read exactly and need nothing. Raster drawings — SketchUp exports, screenshots,
photos of a printout — need OCR to read the dimension text. Most real client decks are
raster, so in practice this step matters.

**Install easyocr.** It reads the callouts, and it brings OpenCV with it, which is what
recognises curved walls and ring shelves. Without OpenCV every item comes out as a flat
panel, and a curved wall priced flat is under-quoted.

```bat
venv\Scripts\python.exe -m pip install easyocr
```

Be ready for the size: this pulls roughly **2 GB** of torch wheels. On a slow connection it
is a long install. Torch was deliberately removed from this project earlier to keep the
install lean — easyocr brings it back, and that is the accepted trade for reading raster
drawings and detecting shapes.

**First parse needs internet.** easyocr downloads its detection model (~64 MB) the first
time it runs. Do one parse while still on a good connection so the PM does not hit it later.
If it fails, the app now says the reader could not start and why, rather than reporting the
drawing as blank.

Confirm:

```bat
venv\Scripts\python.exe -c "import design_parser; print(design_parser.ocr_status())"
venv\Scripts\python.exe -c "import shape_detect; print('shapes:', shape_detect.AVAILABLE)"
```

Expect `{'available': True, 'backend': 'easyocr'}` and `shapes: True`.

**Lighter alternative.** `pip install pytesseract` plus
`winget install --id UB-Mannheim.TesseractOCR -e` is far smaller and reads dimensions fine,
but gives **no shape detection** — everything stays flat. If you use it, close the terminal
and open a new one afterwards, because the Tesseract installer only adds itself to PATH for
processes started later.

Without any reader nothing is priced wrongly — items missing dimensions are held back rather
than quoted — but every raster drawing needs its numbers typed in by hand. The app now says
exactly that, with the install command, on the page that failed.

## 3. Download the search model while there is internet

The first semantic search or catalog index downloads about 90 MB from HuggingFace. It is
lazy, so the app starts and quotes offline perfectly well without it — but the download
fires the first time search is used, and that must not be at a client site.

Open the app once on a good connection and run one search, or index the Drive folder. After
that the app is fully offline. If it is ever attempted offline, the app now says so plainly
instead of showing an errno.

## 4. Bring his real data across

The databases are gitignored, so a fresh clone starts empty. Copy from the old machine:

```
history.db   catalog.db   jobs.db   invoices.db   corrections.db
chroma_db/   images/      company.json
```

Copy them while the app is **closed** on both machines — SQLite writes `-wal` sidecars, and
copying mid-write can take a torn snapshot.

## 5. Set up the backup, and get the passphrase off the laptop

Run a backup from the app. The passphrase is shown **once**, on the first run only. It must
be stored somewhere that is not that laptop — a password manager, or written down and kept
elsewhere. A passphrase held only on the machine being backed up is worthless in exactly the
situation the backup exists for.

## 6. Walk one real quotation through with him

Drawing → estimate → quotation → Excel/Word → invoice. Fifteen minutes, on his machine, with
his data. This catches the things a checklist cannot predict.

---

## Things to tell him

**Some items will refuse to price, on purpose.** If a drawing does not give a counter its
depth, or a stage its depth, or a wall its height, the item shows *"Enter Depth to price this
Kiosk Counter"* instead of a number. This is deliberate. Previously such an item was priced
using an assumed depth and produced a confident, plausible, understated figure — a counter
missing its depth quoted at AED 1,092.91 with no warning. An understated quote gets honoured;
a visible prompt gets fixed. Typing the number in takes seconds.

**Dimensions written on their own line are now read.** "DEPTH 600 mm" on the sheet is picked
up automatically. The form `600 DEEP` — number first — is not yet supported and still needs
typing.

**If something goes wrong: Settings → Save Diagnostics File.** It writes the recent activity
log to the Desktop and opens it. It contains no client data. Sending that file is far more
useful than a description of what happened.

## Known gaps

- `600 DEEP` (trailing label) is not parsed; `DEPTH 600` is.
- OCR quality on photographs of printed drawings is much worse than on digital exports.
  Prefer PDF exports wherever the designer can produce them.
- The rate card is `master_rate_card.csv.csv` — the double extension is real, not a typo to
  be helpfully corrected. Renaming it without updating `rate_card.py` will break pricing.
