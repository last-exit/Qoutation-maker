---
name: Red Cube Smart Quotation Engine
description: A calm, confident SaaS system for a UAE event-production costing tool — near-black sidebar, light content ground, one red accent used deliberately.
colors:
  ink: "#18181b"
  ink-secondary: "#52525b"
  ink-muted: "#6b6b74"
  paper: "#ffffff"
  paper-app: "#f7f7f8"
  paper-recessed: "#f7f7f8"
  border: "#e6e6e9"
  border-strong: "#d5d5da"
  brand-red: "#db302f"
  brand-red-hover: "#c22726"
  brand-red-strong: "#b8241f"
  brand-black: "#141313"
  success: "#157f3c"
  danger: "#b42318"
  warning: "#b45309"
typography:
  body:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"
    fontSize: "12px"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "normal"
  total-figure:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"
    fontSize: "24px"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "-0.02em"
rounded:
  sm: "6px"
  md: "8px"
  lg: "12px"
  xl: "16px"
  pill: "999px"
spacing:
  xs: "6px"
  sm: "10px"
  md: "16px"
  lg: "22px"
  xl: "26px"
components:
  button-primary:
    backgroundColor: "{colors.brand-red}"
    textColor: "{colors.paper}"
    rounded: "{rounded.sm}"
    padding: "9px 15px"
  button-primary-hover:
    backgroundColor: "{colors.brand-red-hover}"
  button-ghost:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink-secondary}"
    rounded: "{rounded.sm}"
    padding: "9px 15px"
  sidebar-nav-item-active:
    backgroundColor: "#2a2825"
    textColor: "#ffffff"
    rounded: "{rounded.sm}"
---

# Design System: Red Cube Smart Quotation Engine

## Overview

**Creative North Star: "The Calm Ledger"**

Red Cube's app quotes real money to real clients, all day, on one maximized desktop window. It took its direction from a deliberate standing exit: rather than inventing a new visual world, it commits to the polished-SaaS register at full craft, benchmarked explicitly against **Stripe Dashboard** (dense financial data made calm and trustworthy), **Linear** (tight restraint, a real type scale, fast quiet interactions), and **Notion** (light-touch, content-first, generous whitespace). The brand's own colors — near-black (`#141313`) and red (`#db302f`), taken directly from `company.json` rather than an invented palette — carry structural roles instead of decorating the surface: black is the permanent sidebar rail, red is the one accent spent on primary actions, the active-nav mark, and anything flagged for attention.

The system replaced a previous "LEDGER" identity (a warm cream/near-square/uppercase-heavy industrial-editorial look) wholesale, per an explicit user redesign request. The old look is not a reference here; it is superseded.

**Key Characteristics:**
- A constant near-black sidebar (not theme-dependent) holding all navigation at once, rather than tabs hidden behind a switcher.
- One accent color, spent rarely and specifically: primary buttons, the active-nav witness-mark, brand mark, flags.
- A real type scale (12–36px, six weight/size steps) replacing an earlier reliance on uppercase + letter-spacing for all hierarchy.
- Moderate rounding (6–16px) and soft, low-elevation shadows — never a hard offset block shadow, never a hairline-only flat card.
- Self-hosted Inter (variable, woff2) — the app is offline-only by product constraint, so no font is ever fetched over a network.

## Colors

Two neutrals do almost all the work; red is reserved and load-bearing.

### Primary
- **Brand Red** (`#db302f`, light / `#e6524f`, dark): the single accent. Used on primary buttons, the active sidebar item's left mark, focus rings, flagged/needs-review states, and the brand mark. Never used decoratively or scattered across a screen.

### Neutral
- **Ink** (`#18181b`): primary text, on light panels.
- **Ink Secondary** (`#52525b`): secondary text, supporting copy.
- **Ink Muted** (`#6b6b74`): field labels, table headers, meta text. Verified ≥4.9:1 on both `Paper` and `Paper App`.
- **Paper** (`#ffffff`): panels, inputs, modals, tables.
- **Paper App** (`#f7f7f8`): the content ground behind panels.
- **Border** (`#e6e6e9`) / **Border Strong** (`#d5d5da`): hairline dividers and input borders.
- **Brand Black** (`#141313`): the sidebar rail only. Constant across light and dark theme — the one element that doesn't flip.

### Semantic
- **Success** (`#157f3c`), **Danger** (`#b42318`), **Warning** (`#b45309`): status pills, banners, margin figures. Danger is a distinct, deeper red from the brand accent on purpose, so a destructive action never reads as a primary one.

### Named Rules
**The One Red Rule.** Red appears in exactly these roles and no others: primary buttons, the active-nav mark, focus rings, and explicit flags (needs-review, borrowed-photo badge, discount amount). If a screen has more than a small handful of red elements at once, something is using it decoratively and should be recolored.

**The Constant Rail Rule.** The sidebar background (`#141313`) never changes with the light/dark theme toggle. Only the content pane (panels, tables, modals) switches; the rail is the brand's fixed anchor.

## Typography

**Body Font:** Inter (self-hosted variable woff2 at `assets/fonts/Inter-Variable.woff2`), falling back to the OS UI font stack.

**Character:** A workhorse grotesque, chosen deliberately for an Operate-mode desktop tool over a display face — Stripe, Linear, and Notion all reach for the same register here, and expression in this app lives in restraint and figure legibility, not in typographic personality.

### Hierarchy
- **Display** (700, 36px): reserved for the rare hero figure; not currently used at full scale, held for future high-emphasis totals.
- **Headline** (700, 24–30px): topbar page title, home hero title, Grand Total figure.
- **Title** (600, 15–20px): panel titles, modal titles, section headings.
- **Body** (400–500, 13–14px): the app's base — draft descriptions, table cells, form inputs.
- **Label** (500, 11–12px): field labels, table headers, stat labels, chips.

### Named Rules
**The Tabular Figures Rule.** Every rendered number (`.num`, table `td.num`, stat values, the Grand Total) uses `font-variant-numeric: tabular-nums`, so columns of money always align — this is money a real client will see.

## Layout

The app is a two-region shell: a fixed 232px sidebar (collapsing to a 68px icon rail under 1240px window width) and a flexible content pane. The content pane always shows a topbar (page title + global search + DB status) above the active view — unlike the previous design, this bar is visible on every tab, not just one.

The Compiler workspace is a two-panel CSS grid (`--ws-left` / `--ws-right`, draggable splitter, persisted per-session in `localStorage`), with a second internal splitter trading height between the draft list and the pricing footer. Both splitters are keyboard-operable (arrow keys, Home to reset) and clamp to sane minimums at any window size. Container queries (not viewport media queries) drive the client-fields' 4-up → 2-up collapse, since the splitter can narrow a panel independent of the window.

Density target: the app runs maximized, full-screen, most of a working day — the layout spends that width on seeing more context at once (a persistent sidebar with live counts, an always-visible topbar) rather than hiding destinations behind navigation.

## Elevation & Depth

Soft, low-opacity, multi-layer shadows — never a hard offset block shadow, never a colored glow standing in for elevation. Elevation is used sparingly: resting cards use only `shadow-xs`; hover states step up one level; modals and toasts use `shadow-lg`.

### Shadow Vocabulary
- **xs** (`0 1px 2px rgba(20,19,19,.04)`): resting cards, stat cards, buttons.
- **sm** (`0 1px 3px rgba(20,19,19,.07), 0 1px 2px rgba(20,19,19,.04)`): hover state on cards/inputs.
- **md** (`0 6px 16px -4px rgba(20,19,19,.10), 0 2px 6px -2px rgba(20,19,19,.05)`): hover on home action cards.
- **lg** (`0 20px 44px -12px rgba(20,19,19,.22), 0 6px 16px -6px rgba(20,19,19,.10)`): modals, toasts.

### Named Rules
**The One-Step Rule.** A hover state moves elevation up exactly one step from its resting shadow — never from flat to `lg` in one jump.

## Shapes

Moderate rounding throughout (6/8/12/16px scale) — a deliberate departure from the previous near-square (4–7px) identity, toward the calmer geometry of the benchmarked products. Pills (999px) are reserved for status badges, chips, and filter controls — never for primary buttons or cards. Icons are inline SVG (a hand-authored 35-icon set, no icon font, no CDN), stroke-width 1.8, rounded joins.

## Components

### Buttons
- **Shape:** 6px radius, never pill.
- **Primary:** brand red fill (`#db302f`), white text, `shadow-xs` at rest.
- **Hover:** background shifts to `#c22726` (light) with `shadow-sm` — a color and elevation step, never a scale/transform bounce.
- **Ghost:** white fill, 1px border, used for secondary actions (Search, Cancel, Add Row).
- **Danger-ghost:** danger-soft background, danger text — for destructive icon actions only.

### Sidebar Navigation
- **Style:** icon (17px) + label, full-width row, 6px radius, on the constant near-black rail.
- **Default:** `sidebar-text` (`#a9a49b`) on transparent.
- **Hover:** `sidebar-hover` background, white text.
- **Active:** `sidebar-active` background, white text, plus a 3px red witness-mark on the left edge — the sole per-screen indicator of "where you are."
- **Counts:** a small red pill badge (Jobs, Review) — only visible when > 0.

### Cards (stat cards, match cards, draft items, job cards)
- **Corner:** 8px radius.
- **Background:** `Paper` (white) on `Paper App` ground.
- **Border:** 1px `border`.
- **Shadow:** `xs` at rest, `sm` on hover, with a 1–2px lift.

### Inputs / Fields
- **Style:** white fill, 1px border, 6px radius, 9×12px padding.
- **Focus:** border shifts to brand red, plus the shared `--ring` (3px red-soft glow) — the same ring token every focusable control that doesn't have a bespoke state reuses.
- **Flagged (Needs Review):** danger border + danger-soft fill, pointing at exactly the field that needs a correction.

### Modals
- **Corner:** 12px radius, `shadow-lg`.
- **Motion:** fade + 8px translate + scale(.98→1), 180ms ease-out — no spring/bounce easing anywhere in this system.
- **Focus:** every modal traps focus and restores it to the trigger on close; `visibility: hidden` (not just opacity) so a closed modal's controls are never keyboard-reachable.

### Tables
- **Header:** sticky, `Paper App` background, `Ink Muted` label-weight text.
- **Rows:** 1px bottom border, no vertical rules, `bg-hover` tint on row hover.

## Do's and Don'ts

### Do:
- **Do** spend red on exactly one thing per screen when possible — the primary action, the active nav item, or a flag — never as a wash or a decorative border.
- **Do** use `tabular-nums` on every rendered figure; a PM scanning a column of rates depends on it.
- **Do** keep the sidebar's near-black background identical in light and dark theme.
- **Do** use exponential ease-out (`cubic-bezier(.16,1,.3,1)`) for all motion; respect `prefers-reduced-motion` by disabling entrance/pop animations while keeping loading spinners.
- **Do** self-host any web font added to this app; it must run with zero network calls.

### Don't:
- **Don't** introduce a second accent color. Success/warning/danger are functional, not decorative alternatives to red.
- **Don't** use pill (999px) radius on buttons or cards — pills are reserved for status/filter chips only.
- **Don't** use spring/bounce easing (`cubic-bezier(.34,1.56,.64,1)` or similar) anywhere; it was deliberately removed from this system.
- **Don't** hide a destructive action's real state behind `opacity`/`pointer-events` alone on modals — `visibility` must gate keyboard focus too.
- **Don't** shrink field labels or table headers below 12px; the previous 8.5–11px cluster was a confirmed legibility complaint this redesign fixed.
