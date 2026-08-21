# Handover checklist — setting the app up for the PM

Written for the first install on someone else's machine. The app has run on exactly one
laptop for most of its life, and every bug found on the night before handover was of the
same kind: something that was true on the developer's machine and nowhere else. Work
through this on the target machine, not on the machine it was built on.

## 1. Run the installer — do this first

Double-click `QuotationEngine-1.0.0-Setup.exe` and click through the wizard. Windows will
warn about an unknown publisher, because the installer is not code-signed: **More info → Run
anyway**.

The app should open from the Start Menu or the Desktop icon. If it does not, the message in
`%LOCALAPPDATA%\QuotationEngine\logs\quotation_engine.log` names the cause.

This step exists because it is the one that catches real problems, and it must be done on
**his** machine, not the one that built the installer. `cryptography` was missing from
`requirements.txt` for months — the app imported it at startup, so a fresh install died
before the window appeared, while working perfectly on the developer's laptop. CI found it
the night before handover. Every handover-eve bug on this project has been that same shape.

## 2. OCR and shape detection — nothing to do

Previously this was two pages of `pip install easyocr`, a 2 GB download, and a warning that
the first parse needed internet. **The installer includes all of it**: the OCR engine, its
detector and recognizer weights, OpenCV for shape detection, and the search model. The app
reads raster drawings and runs semantic search offline, from the first launch.

Worth confirming once, from inside the app rather than a terminal: open a raster drawing
(a SketchUp export or a screenshot) and check the dimensions come back without asking you to
type them in.

If a curved wall or ring shelf comes out priced as a flat panel, shape detection is not
running — that is the symptom worth reporting, because a curved wall priced flat is
under-quoted.

## 3. Bring his real data across

A fresh install starts empty. On the **old** machine the data sits in the project folder; on
the **new** one it belongs in:

```
%LOCALAPPDATA%\QuotationEngine
```

Paste that into the Explorer address bar to open it. Copy across:

```
history.db   catalog.db   jobs.db   invoices.db   corrections.db
chroma_db\   images\      company.json
```

Copy them while the app is **closed** on both machines — SQLite writes `-wal` sidecars, and
copying mid-write can take a torn snapshot.

That folder is deliberately outside the installation directory. Uninstalling the app, or
installing a newer version over the top, leaves it untouched — including the rate card, once
he has edited it.

## 4. Set up the backup, and get the passphrase off the laptop

Run a backup from the app. The passphrase is shown **once**, on the first run only. It must
be stored somewhere that is not that laptop — a password manager, or written down and kept
elsewhere. A passphrase held only on the machine being backed up is worthless in exactly the
situation the backup exists for.

## 5. Walk one real quotation through with him

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
