# Master Prompt — Zone-Render Decomposition (Approach C)

> Hand this whole document to a fresh session. It is self-contained.

---

## Implementation status (2026-08-11)

Built: `curves.py`, `page_geometry.py`, `shop_config.py`; changes to `design_parser.py`,
`calculators.py`, `app.py`, `app.js`, `index.html`, `style.css`. Suite went from 302 to
370 passing tests.

| Stage | State | Note |
|---|---|---|
| 0 OCR recall | Done | Multi-pass (native + 3x upscaled, contrast-normalised), boxes preserved, passes unioned by overlap |
| 1 Page classification | Done | `page_kind` from axis-aligned linework share; unclassifiable pages default to `perspective` |
| 2 Measured spans | Done | Witness-line attachment, local `px_per_m`, unattached callouts reported not guessed |
| 3 Flat-page pipeline | **Partial** | `page_scale` median solve done. Curves come from the PDF's own vector arcs (`curves_from_pdf_page`), which is exact where available. **Raster circle/ellipse detection is not implemented** — a ring on a flat bitmap is not auto-detected; the PM sets Shape → Ring, which is fully supported |
| 4 Perspective pipeline | Done | Measurement-first clustering only; no fabricated elements |
| 5 Data model | Done | `elements[]` per page, `detected` retained for back-compat |
| 6 Curved pricing | Done | Arc length, annular area, arched head, flexible-skin substrate, tighter formers, labour factor — all in `basis` strings |
| 7 Reconciliation | Done | Cross-fill from flat pages, de-duplication switched off (not deleted) |
| 8 UI | Done | Collapsed element rows, hover-to-highlight on the drawing, shape-aware fields, editable fabrication settings |
| 9 Corrections feedback | **Not done** | `corrections_db` is keyed on `(file_name, original_description)` and stores rate/unit/venue — a schema for quotation lines, not drawing elements. Bolting shape/dimension corrections onto it would risk existing behaviour; it needs its own table |

**Still `NEEDS PM CONFIRMATION`** (shown as *unconfirmed* in Workspace Settings →
Curved & Ring Fabrication, and used until changed):

- `curved_skin_layers` = 2
- `curved_stud_spacing_m` = 0.40 m
- `curve_labour_factor` = 1.45
- `ring_wastage_factor` = 0.35

`curved_substrate_code` (WD-MDF-06) came from the rate card's own usage note, and
`ring_edge_banding_code` is deliberately blank so nothing is invented.

---

## Role and objective

You are working on the **Automated Design Estimator** inside the quotation-maker-app
(Python + PyWebView desktop app, vanilla JS frontend). Your objective is to make the
estimator read a multi-page SketchUp/Layout drawing deck and produce a **correct,
auditable BOQ for every buildable element on every page** — including curved walls,
circular/annular shelves, and arched portals.

Today the estimator produces one wrong row per page. This is the work that fixes it.

## The failure you are fixing (verified, not hypothetical)

Page 4 of `Updated Mirdif Sketchups & Designs_01-07-26.pdf` is a perspective render of a
whole retail zone. It carries seven dimension callouts — 110.0, 125.0, 240.0, 230.0,
105.0, 85.0 and 50.0 cm — and contains roughly eight buildable elements: a curved bar
counter, two tall circular-shelf display towers, oval ring shelves, mesh grid panels, an
arched portal, curved back walls, and curved floor plinths.

The estimator returns: **one** item, type `Feature Wall`, length `0.5 m`, height `0`,
sourced from the single token `50.0cm`. Four independent defects stack to produce this:

1. **OCR recall.** One of seven callouts was read. The page came from a PDF but shows an
   `OCR` badge — SketchUp exported it as a flat raster, so the lossless vector-text path
   in `_parse_pdf` (design_parser.py:539) never engaged. Thin grey text on a light render
   at a single OCR scale is near worst-case.
2. **One page = one item.** `_build_page` (design_parser.py:496) returns exactly one
   `detected` object per page. Even with perfect OCR you get one row where eight belong.
3. **No dimension-to-object association.** All page text is flattened into one bag, and
   `_assign_dimensions` (design_parser.py:327) takes the two largest numbers globally.
   The spatial link between a leader line and the object it measures — which is drawn
   right there on the page — is discarded.
4. **Rectilinear-only geometry.** Everything is length x height x depth with flat clad
   faces (`_wall_surfaces`, calculators.py:46). A curved wall's arc length exceeds its
   chord and costs more per m2; a ring shelf is an annulus cut from sheet stock. Neither
   is representable, so even correct dimensions would price wrong.

## Hard constraints — do not violate these

- **Fully local. No cloud vision, no LLM API calls, no network at parse time.** This is a
  firm product decision, not a preference. Do not add a Gemini/Claude/OpenAI call path,
  do not add an "optional online mode", do not suggest one.
- **Determinism is the product promise.** Read the calculators.py module docstring. The
  same drawing must always cost the same. Every computed figure carries a human-readable
  `basis` string rendered beside it in the UI. Anything you add must preserve both.
- **Never invent a number.** The existing parser deliberately refuses to guess —
  see `_reject_envelope_cutouts` (design_parser.py:462) and the THK/THICKNESS exclusion
  comment at design_parser.py:276. A missing dimension must surface as "enter this",
  never as a plausible default. Under-reporting visibly beats over-reporting silently.
- **Do not fabricate shop constants.** Where a real-world value is needed (stud centres on
  curves, skin layers, CNC labour per curved m2), expose it as named configuration with a
  `NEEDS PM CONFIRMATION` comment, and list it in your final report. Do not invent a
  number and let it read as settled fact.
- After changing code, run `graphify update .` (per CLAUDE.md).

## Ground truth already in the codebase

- `master_rate_card.csv.csv` — columns: Category, Item Code, Description / Specification,
  Unit, Price Range (AED), Avg. Cost (AED), Typical Usage.
- **`WD-MDF-06`** is described as *"Curved walls, flexible cladding skins"* (avg 30 AED/sheet).
  The shop already builds curves as thin flexible skins over a frame — not by bending 18mm.
  Your curved-substrate model must reflect this, not a fudge factor.
- `WD-MDF-18` (65 AED) is the flat structural default.
- calculators.py constants: `SHEET_AREA_M2 = 2.9768`, `WASTAGE_FACTOR = 0.10`,
  `STUD_SPACING_M = 0.60`, `STUD_PIECE_LEN_M = 4.0`.
- `corrections_db.py` exists and is the persistence layer for PM corrections.
- Tests live in `tests/`, CI is `.github/workflows/tests.yml`. `test_design_parser.py`
  and `test_calculators.py` show the expected testing idiom — behavioural test names,
  one asserted behaviour each.

---

## Approach C — page-type-aware hybrid

Different page types get different pipelines, and the deck is reconciled as a whole.

### Stage 0 — OCR recall (do this first; everything depends on it)

Highest value per hour in the project, and independently shippable.

- Raise the render scale for the OCR pass specifically (`PDF_RENDER_SCALE = 2.0` is for
  human preview; OCR wants 3-4x). Keep the preview path unchanged.
- Normalise contrast/binarise before OCR — the killer here is thin grey text on light grey.
- Second pass restricted to dimension-shaped tokens (`\d+[.,]?\d*\s*(mm|cm|m)`) with recall
  favoured over precision; union the passes and de-duplicate by position.
- Accept rotated text — vertical callouts (the `240.0 cm` on page 4) are common.
- Preserve the **pixel bounding box** of every OCR token. Stages 2-4 cannot work without it.
  This is a change to what OCR returns, not just how well it reads.

**Acceptance:** on the page-4 render, at least 6 of the 7 callouts are recovered with
correct values and units. Write this as a regression test with the image as a fixture.

### Stage 1 — page classification

Classify each page as `flat` (elevation/plan) or `perspective` before parsing it.

Signal: detect long straight line segments; dimension/witness lines on a flat orthographic
page are strongly axis-parallel and mutually parallel, while a perspective page's converge.
Compute the dispersion of dominant line angles — bimodal and tight at 0/90 degrees means flat.

Store as `page_kind` on the page dict. Report it in the UI. When classification is
uncertain, prefer `perspective` — it is the conservative pipeline.

### Stage 2 — measured spans (the core primitive, used by both pipelines)

A SketchUp dimension callout is a value **plus witness lines** bracketing exactly what it
measures. That geometry is the association signal that Stage 3 of the current parser throws away.

For each OCR dimension token:
- find the nearby dimension line and its two perpendicular witness-line terminators;
- record a **measured span**: `{ value_m, axis, p_start_px, p_end_px, bbox_px, px_per_m }`.

`px_per_m` is the local scale. On a perspective page it varies across the image — that is
expected and is precisely why solving scale locally makes foreshortening stop mattering.

**Acceptance:** on page 4, the `240.0 cm` span's endpoints bracket the left tower's full
height, and `110.0 cm` brackets its width.

### Stage 3 — flat pages: global scale + shape segmentation

Flat pages are where accuracy comes from. Exploit them.

- Solve **one page-wide scale** by least-squares over all measured spans; large residual on
  a span means it was misread — flag rather than silently average it in.
- Segment shapes: Hough circles/ellipses for ring shelves; contour extraction with arc
  fitting for curved walls and portal arcs; line clustering for flat panels.
- For each shape, derive real-world geometry from the page scale, and classify it into the
  `shape` taxonomy in Stage 5.
- Attach measured spans falling inside a shape's bbox as its authoritative dimensions;
  pixel-derived values are used only where no span exists, and are marked lower confidence.

### Stage 4 — perspective pages: measurement-first only

Do **not** run shape segmentation as the source of elements here — occlusion and shading
generate false positives, and an undimensioned shape has no recoverable scale.

- Cluster measured spans that overlap spatially; each cluster is one element candidate.
- Classify shape from the strokes inside the cluster bbox (arc vs line vs ellipse) — shape
  only, never dimensions.
- Every element on a perspective page is therefore backed by a dimension a draughtsman
  actually drew. Elements nobody dimensioned do not appear; surface a page-level note
  ("3 undimensioned shapes detected, not quoted") so the omission is visible, not silent.

### Stage 5 — data model: many elements per page

This is the breaking change. `_build_page` must return `elements: [...]` instead of a
single `detected`. Each element:

```
{
  id, label, item_type,            # existing taxonomy: wall|counter|arch|stage
  shape,                           # flat | curved | ring | arch  (NEW)
  length_m, height_m, depth_m,
  radius_m, included_angle_deg,    # curved/arch only (NEW)
  outer_r_m, inner_r_m,            # ring only (NEW)
  faces, quantity, cutouts,
  bbox_px,                         # for UI highlight-on-select (NEW)
  confidence, assumed_unit, source_text,
  provenance                       # which span/page each dimension came from (NEW)
}
```

Keep `detected` populated from the first element for one release so nothing downstream
breaks at once; migrate `app.py` (`QuotationApi`), `app.js` and `index.html` deliberately.
`tests/test_js_api_contract.py` guards the bridge — update it in the same commit.

### Stage 6 — curved geometry in calculators.py

Add surface builders alongside the existing ones. Follow their exact idiom: return named
surfaces, each with a `formula` string and `area_m2`.

Geometry:
- Arc length `= r * theta` (theta in radians). Where the drawing gives chord `c` and
  sagitta `h`, recover `r = c^2/(8h) + h/2`.
- Curved wall clad area `= arc_length * height`. Never chord * height.
- Ring/annular shelf area `= pi * (R^2 - r^2)`; nest against `SHEET_AREA_M2` with
  `WASTAGE_FACTOR` — note that ring nesting wastes more than rectangular cuts, so a
  ring-specific wastage constant is warranted (`NEEDS PM CONFIRMATION`).
- Arch band follows the arc run, not the existing straight `(2 * height) + length`
  approximation at calculators.py:115.

Substrate and framing:
- Curved elements use **WD-MDF-06 flexible skins** (two layers over the frame is the
  normal build — `NEEDS PM CONFIRMATION`), not WD-MDF-18.
- Studs on a curve sit at closer centres than the flat `STUD_SPACING_M = 0.60`
  (`CURVED_STUD_SPACING_M`, `NEEDS PM CONFIRMATION`).
- Any curve labour/CNC premium is an explicit named constant with its own line and basis
  string — never folded invisibly into a rate.

**Acceptance:** a 3 m chord curved wall costs demonstrably more than a 3 m flat wall, and
the `basis` string shows the arc-length derivation so a PM can follow it by hand.

### Stage 7 — cross-page reconciliation

This is where a mixed deck pays off, and it is what makes the feature worth building.

- Build a per-deck element registry. Match elements across pages by shape signature,
  proportion, and label similarity.
- **Cross-fill:** an element well-dimensioned on a flat elevation fills the gaps in its
  perspective-page counterpart. Record the source page in `provenance`.
- **De-duplicate:** the same tower appearing on four pages must be quoted **once**.
  Without this, multi-page decks over-quote badly — arguably worse than today's bug.
- Conflicts between pages surface to the PM with both values; never silently pick one.

### Stage 8 — UI

- Each page renders as a group of element rows against one thumbnail.
- Selecting a row highlights its `bbox_px` on the thumbnail. This is the single feature
  that makes correction fast, because the PM can see what the row refers to.
- Show `page_kind`, per-element confidence, and provenance ("height from p7 elevation").
- Add/delete/merge/split rows manually. Auto-split is a first draft, not a verdict.

### Stage 9 — corrections feedback

- A PM edit writes to `corrections_db` keyed on shape signature + element type + deck.
- Later pages in the same deck apply matching corrections before presenting.
- Corrections are always visible and reversible — show "adjusted from a previous fix".

---

## Testing

Non-negotiable, matching the existing suite's style:

- Fixture images: the page-4 perspective and at least one flat elevation. Golden-file the
  expected element list.
- Unit tests per stage — span extraction, page classification, scale solve, each curve formula.
- Geometry tests with hand-computable numbers (a quarter-circle of radius 2 has arc length
  `pi`); assert the `basis` string content, not just the total.
- A regression test asserting page 4 no longer yields a single 0.5 m Feature Wall.
- Explicit test that an undimensioned element is **omitted and reported**, never guessed.
- Deck-level test that a repeated element is quoted once.
- All existing tests must still pass. `tests/test_js_api_contract.py` must be updated in
  the same commit as the data-model change, not after.

## Anti-goals

- No cloud/LLM inference anywhere in the parse path.
- No silent defaults for missing dimensions.
- No refactoring beyond what this work requires.
- Do not tune heuristics against the page-4 fixture until it passes and nothing else does.
  If a stage cannot hit its acceptance criterion honestly, say so and stop.

## Definition of done

Page 4 yields multiple correctly-typed elements — curved counter, tower, portal, curved
walls — each either carrying dimensions traceable to a real callout or clearly marked as
needing PM input. Curved elements price using arc length and flexible-skin substrate with
auditable basis strings. A repeated element across the deck is quoted once. Every invented
constant is listed as `NEEDS PM CONFIRMATION` in the final report.

## Suggested sequencing

Stages 0-2 first — they are independently valuable and de-risk everything after. Ship Stage 0
on its own; it improves today's behaviour with no data-model change. Stages 5 and 8 land
together. Stage 7 last, since it needs several pages parsing well before it means anything.
