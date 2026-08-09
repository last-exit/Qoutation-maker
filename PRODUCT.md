# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Ameer, the PM at Red Cube — a UAE-based event production/fabrication company (AED currency; venues like Kite Beach; work in structures, backdrops, AV, staging). A solo power user who runs the app maximized, full-screen, for most of the working day: building client quotations under time pressure, then tracking job costs and payments once a quote converts.

## Product Purpose

Turns years of historical quotation line-items into a searchable, semantically-matched price index, so building a new quotation means finding comparable past work rather than pricing from scratch. Ages historical rates by an annual markup so old prices aren't quoted stale. Compiles Excel/Word quotation documents and tracks the full lifecycle from draft → sent → won/lost → invoiced/paid, plus post-win job costing against suppliers to see real margin.

## Positioning

Not a generic quoting/CRM tool. The mechanism is semantic search over the company's own historical quotes (not a static price list), combined with time-decay-adjusted pricing (a rate quoted 18 months ago earns a compounding annual markup automatically), and margin tracking that ties every quoted line back to a catalog cost. Vocabulary is native to Middle East event production (Lump Sum, Sqm, AED, VAT 5%, venues, "Needs Review" items flagged from re-synced historical files).

## Operating Context

Runs as an offline Windows desktop app (pywebview shell) with zero network dependency by design — fonts, icons, and assets are bundled/inline, never CDN-fetched. Used maximized, full-screen, most of the day.

Workflow: sync/index historical quote files from a Drive folder → search for comparable line items while drafting a new quote → adjust rates/quantities → generate Excel and/or Word output → share via WhatsApp/email → track status (Sent/Won/Lost) and payment → once won, log actual job costs against suppliers to see real margin vs. quoted.

## Capabilities and Constraints

- Six core areas: Home (dashboard), Compiler (search + draft quote builder), Catalog (priced item list with cost/margin), Jobs (post-win cost tracking vs. suppliers), Needs Review (flagged historical data needing correction), Invoices/History (quotation lifecycle + payment tracking).
- Must remain fully offline-capable: no CDN fonts, icon fonts, or scripts. Any web font used in the redesign must be self-hosted (woff2 bundled locally).
- Company identity is data-driven from `company.json` (name, logo, pm_name) so the app isn't hardcoded to one company's copy, though the current live deployment is Red Cube.
- **Out of scope for this redesign:** the generated Word/Excel quotation documents (`doc_generator.py`). They keep their current template/branding untouched — confirmed with the user.
- Backend is Python (`pywebview`, exposed as `window.pywebview.api`); frontend is vanilla JS calling `api().<method>()` — no framework. The redesign stays dependency-free/vanilla to match, and preserves every existing `api()` call contract (backed by `tests/test_js_api_contract.py`).

## Brand Commitments

- Product name: **Red Cube**.
- The user's own words on palette: "There needs to be the company colors which is a tiny bit of red and black and white, but otherwise go crazy." Read as: red, black, and white must remain a legible, identifiable brand thread — not the majority of the surface — and the rest of the palette/material world is genuinely open for this redesign.
- Existing 3D-cube logo mark (`assets/red_cube_logo.png`, a 2×2 grid of squares with one rendered as a 3D red cube among flat white squares on black — a modular/building-block motif) is available brand equity, not a mandate to reuse as-is.
- `company.json`'s `accent_hex` (`#DB302F`) governs the generated documents only (out of scope here) and already differs from the app's current CSS accent (`#c8102e`) — the app UI and the client-facing documents are already decoupled today, confirmed with the user.

## Evidence on Hand

- `assets/red_cube_logo.png` — the only brand image asset.
- `company.json` — name, tagline, doc-branding colors, pm_name (drives document branding + the app's greeting/title text, not its palette).
- No other photography, illustration, or brand reference material exists. Any imagery this redesign needs must be authored (icons, patterns) rather than assumed to exist.

## Product Principles

1. The core loop — search a historical rate, adjust it, generate — is the product. The new layout must make that loop faster, not just prettier.
2. Full-screen desktop density is an asset to use, not a constraint to design around: favor seeing more real context at once over hiding it behind tab switches (confirmed pain point: "too much tab-switching").
3. Every number on screen is money a real client will see. Legibility of figures always wins over decorative restraint (confirmed pain point: "information is too dense/small").
4. Offline-first is non-negotiable: no CDN fonts, scripts, or icons; everything ships bundled.
5. Red, black, and white stay as a legible brand thread through an otherwise bold, new material world.

## Design Direction (standing preference)

The user took the standing exit in the 2026-08-10 redesign round: a polished modern-SaaS execution rather than a structural visual-world reinvention, benchmarked against **Stripe Dashboard** (dense financial data made calm and trustworthy, confident big-number treatment), **Linear** (tight minimal restraint, sharp real type scale, fast/quiet interactions), and **Notion** (light-touch, content-first, generous whitespace). This is a durable brand/craft commitment — later surfaces in this app should be held to this same bar rather than re-opening the direction question, unless the user explicitly asks to revisit it.

Brand color mandate (user's words): "a tiny bit of red and black and white, but otherwise go crazy" — resolved as: `company.json`'s actual brand colors (`#141313` near-black, `#DB302F` red) carry structural roles (dark sidebar, single confident accent) rather than sitting in a hidden data file, white/light neutral surfaces do the rest, and red is reserved for brand mark, primary emphasis, and flagged/attention states — never scattered decoratively.

## Accessibility & Inclusion

No new requirement beyond what the codebase already established: WCAG-conscious contrast, visible keyboard focus, focus-trapped modals, `prefers-reduced-motion` support, and full keyboard operability of the primary workflow. The rebuild must preserve all of this, not just its look.
