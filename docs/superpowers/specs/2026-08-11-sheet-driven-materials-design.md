# Sheet-Driven Materials and a Simplified Estimator

**Date:** 2026-08-11
**Status:** Awaiting review — not implemented

## Why

The estimator works on synthetic vector drawings and falls apart on the real Mirdif deck.
Three failures were observed directly:

* **Page 4** reports *"1 dimension found but none could be tied to a line on the drawing"*,
  falls back to the whole-page reading, and produces one item at 1.25 × 0.50 m for an
  entire zone. Its label is `50.0cm` — a dimension used as a name.
* **Page 2** produces an item labelled `—=s\`, which is OCR noise, plus two rows with no
  dimensions at all.
* **Page 4 is badged ELEVATION** although it is plainly a 3D perspective view.

Alongside that, the item card carries twelve controls (Type, Shape, Qty, Length, Height,
Depth, Clad faces, Finish, Substrate, Framing, LED, Cutouts), and the material catalogue is
duplicated: `master_rate_card.csv.csv` holds 59 materials, while `calculators.py` hardcodes
its own `SUBSTRATES`, `FRAMING` and `FINISH_SYSTEMS` lists naming specific codes.

This design does three things: makes the rate card the only source of materials, reduces
the card to shape plus dimensions, and stops the parser emitting rows built from noise.

## What this is not

Not a rewrite of the decomposition work. `page_geometry.py`, `curves.py` and the element
model stay. This changes what a shape *means*, where materials come from, and what the PM
sees.

---

## 1. One shape list

`item_type` (wall / counter / stage / arch) and `shape` (flat / curved / ring / arch) merge
into a single `shape`. The two lists overlapped — "arch" appeared in both, and Type=Feature
Wall with Shape=Arched head was a selectable combination that meant nothing.

| Shape key | Label | Geometry | Curved |
|---|---|---|---|
| `wall_flat` | Flat wall | clad face(s) + end returns | no |
| `wall_curved` | Curved wall | as above, on arc length | yes |
| `counter_flat` | Counter | fascia + worktop + ends | no |
| `counter_curved` | Curved counter | as above, on arc length | yes |
| `arch` | Arch | legs + arc head + soffit | head only |
| `ring` | Ring shelf | annular area per shelf | n/a |
| `stage` | Stage | deck + perimeter fascia | no |

Each shape declares which dimension fields it shows, so a ring never offers Length and a
flat wall never offers Curve rise. Curved shapes require a rise; without one they refuse to
price rather than quietly quoting the chord. That rule already exists and is kept.

Each shape also carries the carpentry hours per m² that `ITEM_TYPES` holds today (wall
0.45, counter 0.85, stage 0.55, arch 0.95). Curved variants inherit their flat twin's rate
and apply the existing `curve_labour_factor` on top, so no new labour figures are invented.

**Migration.** Existing specs carry `item_type` and `shape` separately. A loader maps the
old pair to the new key (`wall`+`curved` → `wall_curved`, and so on). Saved quotations must
re-price to the same number.

---

## 2. Materials come from the sheet

### The rule

`calculators.py` stops naming materials. A shape declares the **roles** it needs, and each
role is filled by searching the rate card. Adding a material to the CSV makes it available
with no code change; removing one is reported rather than silently substituted.

Roles:

| Role | Needed by | Fills |
|---|---|---|
| `substrate` | every shape | the carcass board |
| `framing` | walls, counters, arches, stages | the stud skeleton |
| `fixings` | anything framed | screws |
| `brackets` | anything framed | joint reinforcement |
| `adhesive` | anything with clad area | wood glue |
| `finish_*` | every shape | the finish bundle (§4) |

### How a role is filled

Each role carries a query: a required `Category`, a set of `prefer` keywords, and a set of
`avoid` keywords, matched case-insensitively against the row's **Category** and **Typical
Usage** text. Every candidate row scores one point per `prefer` keyword present, minus one
per `avoid` keyword. Highest score wins.

**Ties break deterministically**: highest score, then lowest `Avg. Cost`, then `Item Code`
ascending. This matters — the module docstring in `calculators.py` promises the same
drawing always costs the same, and an unstable tiebreak would quietly break that.

These queries are verified against the current sheet:

| Shape | Role | Category | Prefer | Resolves to |
|---|---|---|---|---|
| `wall_flat` | substrate | Wood & Boards | structural, walls | `WD-MDF-18` |
| `wall_curved` | substrate | Wood & Boards | curved, flexible, cladding | `WD-MDF-06` |
| `counter_*` | substrate | Wood & Boards | counters, structural | `WD-MDF-18` |
| `stage` | substrate | Wood & Boards | stages, sub-floors | `WD-PLY-18M` |
| `ring` | substrate | Wood & Boards | shelving, lightweight | `WD-MDF-12` |
| walls/counters/arch | framing | Wood & Boards | wall, skeletons | `WD-FRM-2X2` |
| `stage` | framing | Wood & Boards | stage, supports, load-bearing | `WD-FRM-2X4` |
| all framed | fixings | Hardware | assembly, framing | `HW-SCR-BLK` |
| all framed | brackets | Hardware | reinforcing, joints | `HW-LBR-05` |
| all clad | adhesive | Paints & Chems | carpentry joints, laminating | `AD-WD-05L` |

**Where these live.** `shapes.py` says *which* roles a shape needs. `materials.py` says
*how* each role is filled. The table above is the join of the two, shown together for
review; it is not a single structure in the code. Both are rules, not a catalogue — they
say "a curved wall wants a flexible board", never "a curved wall uses WD-MDF-06".

### When nothing matches

The item does not price. It reports which role is unfilled and what the sheet would need to
say, in the same style as the existing missing-dimension message. It never falls back to an
arbitrary row: a wrong material that looks plausible is the failure mode this project
exists to prevent.

### Showing the choice

Every resolved material appears on the item card with its reason:

> Substrate: **MDF 6mm** — sheet says *"Curved walls, flexible cladding skins"*

and can be overridden per item. Overrides are already supported by `rate_overrides`; this
adds a material-code override alongside them. This recovers the auditability of a hardcoded
list without keeping one.

### Caching

Resolution runs once per rate-card load and is cached on the `RateCard` object. Changing
the CSV and reloading re-resolves. Resolution never runs per item.

---

## 3. Quantities come from the Unit column

The `Unit` column decides the *shape of the formula*; a size constant supplies the rest.

| Unit | Formula | Size constant needed |
|---|---|---|
| Sheet | `area × (1 + wastage) / SHEET_AREA_M2`, ceil | none |
| Sqm | `area × (1 + wastage)` | none |
| Piece | `linear_m × (1 + wastage) / piece_length`, ceil | piece length (4.0 m) |
| Length | `linear_m / stock_length`, ceil | stock length |
| Roll | `metres / roll_length`, ceil | roll length (5.0 m) |
| Can, Drum, Liter | `area × coats / coverage / unit_size`, ceil | coverage, coats, unit size |
| Unit, Pair, Box | count from the rule that requested it | items per box |

**Be explicit about the limit:** the sheet does not carry coverage figures. Only
`PT-EML-18L` mentions one ("covers ~80 sqm"); `PT-PRM-05L` and `PT-PU-01L` state what they
are for but not how far they go. Every size constant in the table above — coverage, coats,
piece length, stock length, roll length and items per box — therefore lives in
`estimator_config.json` beside the fabrication constants, editable in the same settings
panel, and marked unconfirmed until the workshop supplies real figures. This is
the one place where "everything comes from the sheet" is not achievable today. Adding a
`Coverage (sqm per unit)` column to the CSV would close it, and the loader should read that
column when present and fall back to config when absent.

---

## 4. Finishes become bundles

A finish is a method, not a material: "primer, two coats, then PU, two coats, thinned"
cannot be read off a row. So `FINISH_SYSTEMS` is replaced by finish *bundles* that list
roles and coats, with the products resolved from the sheet exactly as §2 describes.

```
paint_pu:      primer (2 coats) + topcoat (2 coats) + thinner
laminate_hpl:  laminate sheet + contact adhesive
vinyl_print:   printed vinyl (sqm)
veneer_oak:    veneer (sqm) + contact adhesive
none:          nothing
```

Role queries, verified against the sheet: primer → *"MDF surface preparation"*
(`PT-PRM-05L`); topcoat → *"flawless spray finish"* (`PT-PU-01L`); thinner → *"thinning PU
paint"* (`PT-THN-05L`); laminate → Finishes & Decor + *"countertops, durable"*
(`FN-HPL-SOL`); contact adhesive → *"bonding laminates"* (`AD-GLU-15L`); printed vinyl →
*"branding wraps"* (`FN-VNL-PRT`); veneer → *"wooden finish over MDF"* (`WD-VEN-OAK`).

Bundle definitions (which roles, how many coats) live in config, not code, so a new finish
can be added without a release. Finish selection moves to Advanced; `paint_pu` stays the
default.

---

## 5. The item card

Default view, in order: **Label · Shape · Qty**, then the shape's dimension fields, then
**Cutouts & openings**, then a one-line materials result and the cost.

Behind an **Advanced** disclosure: Finish system, Substrate override, Framing override, LED
strip, and per-line rate overrides.

That takes the default card from twelve controls to five or six depending on shape. Nothing
becomes unreachable — Advanced is one click, and the auto-chosen materials are visible
without opening it.

The collapsed row summary is unchanged: include checkbox, label, shape chip, dimension
summary, confidence, cost.

---

## 6. Dimension chips

Every dimension the parser read from a sheet is listed beside the drawing as a chip
(`125.0 cm`, `240.0 cm`, `50.0 cm`), whether or not it could be attached to an object.

Interaction: click a chip to arm it; the item's dimension inputs highlight; click one and
it fills, converted to metres. A hint bar reads *"Assigning 125.0 cm — click a field"* and
Esc cancels. A chip that has been used is greyed but stays available.

Auto-fill still happens where the geometry is confident. Chips are what turn today's dead
end — a page whose numbers were read correctly but could not be tied to anything — into two
clicks, without the estimator inventing an assignment.

Chips come from the existing `dimensions_found` on each page, so no new extraction work.

---

## 7. Reliability fixes

These are small and independently testable, and without them the simplified card still
shows nonsense.

**Junk labels.** A label is rejected unless it contains at least three consecutive letters
and is not a pure dimension. `—=s\` and `50.0cm` both fail. Rejected labels fall back to the
sheet title, then to `Item 1`, `Item 2`. Applies to `_label_for_cluster` and to the legacy
whole-page element.

**Empty rows.** An element is only emitted when it has at least one attached dimension.
Rows reading "no dimensions yet" with nothing behind them are not produced at all; the page
reports how many shapes it could not measure, as it already does for unattached callouts.

**Page-kind misclassification.** `classify_page` currently counts every axis-aligned run,
including the image border and the page frame, so a 3D render scores as flat. Fix: ignore
segments within 2% of any page edge, and ignore any segment spanning ≥95% of the page's
width or height. Require at least eight *interior* segments before classifying at all,
otherwise return `perspective`. Page 4 of the Mirdif deck must classify as `perspective`.

**Raster scan noise.** `segments_from_image` must discard runs whose endpoints touch the
image border, and merged bands more than 4 px thick — a drawn dimension line is 1–3 px,
while a thicker band is the edge of a shaded solid.

---

## 8. Files

| File | Change |
|---|---|
| `materials.py` | **New.** Role definitions, keyword scoring, resolution, caching, reasons. |
| `calculators.py` | Delete `SUBSTRATES`, `FRAMING`, `FINISH_SYSTEMS`, `ITEM_TYPES`. Add the merged shape table. Quantities derive from `Unit`. |
| `shapes.py` | **New.** The seven shapes: geometry builder, dimension fields, material roles, old-pair migration. Keeps `calculators.py` from growing further. |
| `shop_config.py` | Add coverage, coats, piece length, roll length, box counts. |
| `rate_card.py` | Expose `Category` and `Typical Usage` for scoring; read an optional `Coverage` column. |
| `design_parser.py` | Label rejection; suppress dimensionless elements; interior-only page classification. |
| `page_geometry.py` | Border and thickness filtering in the raster scan. |
| `app.py` | Options payload carries shapes, resolved materials and reasons. |
| `app.js`, `index.html`, `style.css` | Merged shape selector, Advanced disclosure, materials result line, dimension chips. |

---

## 9. Testing

* Role resolution against the real CSV: each row in the §2 and §4 tables asserted to
  resolve to the code named there.
* Determinism: resolving twice gives identical results; two rows with equal score resolve
  by cost then code.
* Missing material: a rate card with the framing rows removed makes a wall report an
  unfilled role and refuse to price, rather than substituting.
* Unit→quantity: one test per unit kind, with hand-computable numbers.
* Migration: `{item_type: wall, shape: curved}` prices identically to `{shape: wall_curved}`.
* Regression: a flat wall's total is unchanged from today's figure.
* Labels: `—=s\`, `50.0cm` and `...` are all rejected; `Display Tower` is kept.
* Page kind: a bordered image of a perspective render classifies as `perspective`.
* Chips: a page whose callouts cannot be attached still exposes them in `dimensions_found`.

All 370 existing tests must still pass.

---

## 10. Order of work

1. Reliability fixes (§7) — small, independent, and they stop the visible nonsense.
2. `materials.py` role resolution (§2) behind the existing API, with `calculators.py` still
   passing explicit codes, so resolution can be proven before anything is deleted.
3. Unit-driven quantities (§3) and finish bundles (§4); delete the hardcoded lists.
4. Merged shapes (§1) with migration.
5. UI: Advanced disclosure, materials line, chips (§5, §6).

Stages 1 and 2 are independently shippable. Stage 4 is the breaking one and lands with its
migration test.

## Open question for the reviewer

Coverage figures (§3) are the one thing the sheet cannot supply today. The spec puts them in
config. If you would rather add a `Coverage (sqm per unit)` column to the rate card, say so
and §3 changes to read it as the primary source.
