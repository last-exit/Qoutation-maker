# OCR, Shape Detection, and Manual Entry

**Date:** 2026-08-11
**Status:** Awaiting review — not implemented

## Why

Three failures observed on the real Mirdif deck.

**No text reader is installed.** `design_parser.ocr_status()` returns `available: False`. Every
page without a vector text layer therefore yields zero dimensions. Page 2 shows "no
dimensions yet" while the drawing carries five plain callouts (435.0, 325.0, 210.0, 120.0,
300.0 cm). The app then reports *"drawing gave no usable value"*, which points the blame at
the drawing when the actual cause is a missing dependency. No dimension chips appear either,
because there is no text to make them from.

**Shapes are never detected.** Curve detection reads PDF vector arcs only. On a rasterised
deck nothing is ever classified, so every item defaults to Flat wall — including the curved
walls and ring shelves that fill these drawings. A curved wall priced flat is under-quoted,
silently.

**Manual entry is a dead end.** When detection fails the PM gets Length and Height boxes and
nothing else. There is no way to say "this is 18 mm MDF at 65 AED". Material is auto-resolved
from the sheet and rate overrides sit inside the cost table behind Advanced.

## Decisions taken

* Install **easyocr** as the reader. Accepted cost: ~2 GB of torch wheels, against a project
  that deliberately stripped torch to keep the PM install lean. `HANDOVER.md` must say so.
* easyocr depends on **opencv-python-headless**, so OpenCV arrives with it. Real shape
  detection becomes possible with no extra dependency.
* Detected shapes are **applied automatically**, and always remain changeable.
* A typed material cost **asks** whether to use once or save to the rate card.

---

## 1. OCR that reports its own absence

Adding the dependency is half the fix. The other half is that a missing reader must never
again present as a bad drawing.

`requirements.txt` gains `easyocr`, in its own clearly-commented section noting the torch
weight and that the estimator still runs without it.

Message routing, replacing today's single generic string. The parser already distinguishes
these cases internally; the UI does not surface the difference:

| Situation | Message on the item |
|---|---|
| No reader installed | "No text reader installed, so nothing could be read from this drawing. Install it with `pip install easyocr`, or type the dimensions below." |
| Reader ran, found nothing | "Nothing readable on this sheet — type the dimensions below." |
| Numbers read, none attachable | Existing dimension chips, plus "Click a number, then a field." |
| Dimensions attached, one missing | Existing "Enter Height to price this…" |

The install hint already exists on `ocr_status()["hint"]`; it is currently shown once as a
toast at load and lost. It must appear on the page that failed, where the PM is looking.

**First-run model download.** easyocr fetches its detection model on first use (~64 MB). On a
PM machine with no network that fails at parse time. The failure is already caught
(`_ocr_init_error`) — it must surface with the same actionable wording, not as "no text".

---

## 2. Shape detection with OpenCV

New module `shape_detect.py`. Takes the page image plus each element's `bbox_px`, returns a
shape suggestion per element. Pure detection: it reads pixels and returns findings, it does
not price, classify item types, or mutate specs.

**Rings.** `cv2.HoughCircles` over the element's box. A strong circle whose radius is a
sensible fraction of the box gives `ring`, with `outer_r_m` derived from the element's local
`px_per_m` where one exists. Concentric pairs give an inner radius too.

**Curved walls.** Contours within the box, approximated with `cv2.approxPolyDP`. A contour
that resists straight-line approximation but fits an ellipse arc (`cv2.fitEllipse`, low
residual) is a curve. The sagitta comes from the fitted arc's deviation from its chord —
which is exactly the dimension the pricing model needs and the PM would otherwise measure by
eye.

**Arches.** A curve whose chord is roughly horizontal and sits in the upper portion of the
box, with two near-vertical contours descending from its ends, is an arched portal.

**Confidence and application.** Each suggestion carries a confidence. Applied automatically,
per the decision above, and recorded as `shape_source`:

* `detected` — set by this module. The row shows a small "detected" chip.
* `user` — the PM changed it. **Never overwritten by re-detection**, on this parse or any
  later one. A PM correction that gets undone by a re-parse is worse than no detection.
* `default` — nothing found; Flat wall as today.

Detection runs only where it can be checked: a curve with no `px_per_m` yields the shape but
not the sagitta, so the item asks for the rise rather than inventing one. The existing rule
stands — a curved item with no rise refuses to price.

**Failure is silent and safe.** If OpenCV is absent (someone skipped easyocr), the module
returns no suggestions and everything behaves exactly as it does today.

---

## 3. Manual entry, front and centre

The rule: **an item that could not be read from the drawing puts everything needed to price
it on the card.** An item that was read keeps the tidy layout, with overrides in Advanced.

When `needs_dimensions` is true, the card shows, inline and unfolded:

* the shape's dimension fields (as now)
* **Material** — a searchable picker over the rate card, showing code, description and price
* **Cost** — pre-filled from the sheet, editable, in AED per the material's own unit
* **Unit** — shown, not editable, taken from the sheet row

`rate_card.search()` already backs the picker. The material and cost fields write to the
existing `substrate` and `rate_overrides` spec keys, so nothing new is threaded through
pricing.

### A material that is not on the sheet

The picker accepts free text. Typing a name that matches nothing offers an inline row:

> Not on the rate card. Unit `[Sheet ▾]` · Cost `[____]` AED
> ( ) Use on this quote only   ( ) Save to the rate card

Saving calls the existing `rate_card.add_rate_card_item()`, which appends to
`master_rate_card.csv` and reloads the cache — so the material is available on every future
drawing. Use-once keeps it in `rate_overrides` for this quote alone.

A generated code is required for a saved row. Derive it from the description
(`MDF Plain 18mm` → `WD-MDF-18`-style: first letters of the category, then the name), and
show it for editing before saving. Never save a code that already exists — the existing
method raises on collision, and that error must reach the PM as a clear message, not a toast.

---

## 4. Files

| File | Change |
|---|---|
| `shape_detect.py` | **New.** Hough circles, ellipse-arc fitting, arch heuristic. Returns suggestions; mutates nothing. |
| `requirements.txt` | Add `easyocr` with a comment on its torch weight. |
| `design_parser.py` | Route the three no-dimension cases to distinct messages; carry `shape_source`; call shape detection after clustering. |
| `calculators.py` | Respect `shape_source == "user"`; no pricing change. |
| `app.py` | Expose `search_materials` and `add_material` to the UI; carry OCR status per page. |
| `app.js`, `index.html`, `style.css` | Inline manual block when unpriceable; material picker; save-to-sheet row; "detected" shape chip. |
| `HANDOVER.md` | Note the easyocr install, its size, and the first-run model download. |

## 5. Testing

* `ocr_status()` unavailable produces the install message, not "no usable value".
* An easyocr init failure surfaces its own message rather than "no text".
* A synthetic image of a circle detects as `ring`; a bowed line as `curved`; a straight
  panel stays `flat` (no false positive).
* Detection with no OpenCV installed returns nothing and changes no behaviour.
* `shape_source == "user"` survives a re-parse.
* A curved detection with no scale asks for the rise instead of guessing it.
* Material picker: searching returns sheet rows; use-once leaves the CSV untouched; save
  appends exactly one row and it resolves on the next quote; a duplicate code reports clearly.
* All 408 existing tests still pass.

## 6. Order of work

1. OCR messaging (§1) — small, no new dependency, and it stops the misleading text today.
2. Manual entry (§3) — the ask that unblocks a PM on any drawing, readable or not.
3. `easyocr` in requirements + `HANDOVER.md`.
4. Shape detection (§2) — largest piece, and it depends on OpenCV arriving with easyocr.

Steps 1 and 2 are independently shippable and useful even if OCR is never installed.
