# Graph Report - quotation-maker-app  (2026-08-01)

## Corpus Check
- 18 files · ~26,124 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 313 nodes · 594 edges · 12 communities (11 shown, 1 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 20 edges (avg confidence: 0.76)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7ebababc`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Desktop App Backend API
- Historical Quote Parsing Engine
- Excel/Word Document Generation
- Frontend-Backend API Bridge
- Frontend State & Icon System
- Core Compile & Sync Pipeline
- Quotation History Database
- History & Match Rendering
- Image Fetching & Thumbnailing
- app.js
- PM Corrections Database
- WhatsApp/Email Share Links

## God Nodes (most connected - your core abstractions)
1. `QuotationApi` - 28 edges
2. `Red Cube Smart Quotation Engine (index.html)` - 28 edges
3. `api()` - 27 edges
4. `showToast()` - 17 edges
5. `generate_word_dynamic()` - 17 edges
6. `icon()` - 16 edges
7. `esc()` - 15 edges
8. `syncFolder()` - 13 edges
9. `parse_pdf_file()` - 13 edges
10. `switchTab()` - 12 edges

## Surprising Connections (you probably didn't know these)
- `Red Cube Logo image asset (red_cube_logo.png)` --semantically_similar_to--> `CSS-drawn Red Cube Icon (brandlock cube3d)`  [INFERRED] [semantically similar]
  assets/red_cube_logo.png → index.html
- `switchTab()` --references--> `Compiler Workspace View (view-compiler)`  [INFERRED]
  app.js → index.html
- `switchTab()` --references--> `Quotation History View (view-history)`  [INFERRED]
  app.js → index.html
- `switchTab()` --references--> `Home View (view-home)`  [INFERRED]
  app.js → index.html
- `switchTab()` --references--> `Needs Review View (view-review)`  [INFERRED]
  app.js → index.html

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Quotation Document Generation (Excel/Word export)** — app_compilequote, requirements_openpyxl, requirements_python_docx [INFERRED 0.85]
- **Semantic Search / Smart Matcher subsystem** — app_searchmatcher, requirements_chromadb, requirements_sentence_transformers [INFERRED 0.85]
- **Google Drive Historical Data Sync Pipeline** — app_syncfolder, requirements_google_api_python_client, requirements_google_auth_oauthlib, requirements_google_auth_httplib2, requirements_pymupdf, requirements_datefinder [INFERRED 0.75]

## Communities (12 total, 1 thin omitted)

### Community 0 - "Desktop App Backend API"
Cohesion: 0.05
Nodes (20): crossfill_images(), _distance_to_similarity(), _elapsed_years(), _is_generic_service(), main(), QuotationApi, Converts ChromaDB's squared-L2 distance into a real cosine similarity percentage, True when a line prices a service, so borrowing a product photo for it is mislea (+12 more)

### Community 1 - "Historical Quote Parsing Engine"
Cohesion: 0.07
Nodes (48): assign_images_to_rows(), _build_item(), _cell_image_base64(), classify_columns(), clean_rate(), _collect_spec_lines(), _distinct_row_cells(), evaluate_review_flags() (+40 more)

### Community 2 - "Excel/Word Document Generation"
Cohesion: 0.08
Nodes (42): _add_page_number(), _apply_print_setup(), _build_footer(), compute_totals(), compute_valid_until(), create_fallback_template(), decode_image_payload(), _detect_template_columns() (+34 more)

### Community 3 - "Frontend-Backend API Bridge"
Cohesion: 0.15
Nodes (25): api(), applyBulkVenue(), applyCompanyBranding(), applyImageToItem(), applyLibraryMatch(), bootBackend(), checkDbStatus(), closeImagePicker() (+17 more)

### Community 5 - "Frontend State & Icon System"
Cohesion: 0.33
Nodes (5): convert_to_pdf(), open_file(), PDF export via MS Office COM automation (win32com), with graceful offline-safe f, Converts an xlsx/docx file to PDF using the installed MS Office application via, Opens a file with the OS default handler (e.g. default PDF viewer).

### Community 6 - "Core Compile & Sync Pipeline"
Cohesion: 0.12
Nodes (29): changeMarkup(), compileQuote(), esc(), groupByFile(), icon(), loadHomeDashboard(), loadHomeRecent(), loadReviewQueue() (+21 more)

### Community 7 - "Quotation History Database"
Cohesion: 0.21
Nodes (14): _connect(), delete_quotation_history(), get_quotation_by_id(), get_quotation_history(), init_db(), _migrate(), peek_next_quotation_id(), Local SQLite history of every generated quotation, for the Client & Quotation Hi (+6 more)

### Community 9 - "Image Fetching & Thumbnailing"
Cohesion: 0.23
Nodes (11): bytes_from_local_file(), bytes_to_thumbnail_base64(), fetch_image_as_base64(), fetch_image_suggestions(), get_embedded_image_base64(), pil_to_base64(), Image helpers: embedded-image thumbnailing, best-effort online image search, URL, Extracts image data from an openpyxl drawing image, resizes, and encodes to base (+3 more)

### Community 10 - "app.js"
Cohesion: 0.07
Nodes (55): addCustomDraftRow(), addMatchedItemToDraft(), adjustRate(), applyHistoryFilters(), cloneHistoryItem(), closeSettingsModal(), closeSuccessModal(), deleteDraftItem() (+47 more)

### Community 11 - "PM Corrections Database"
Cohesion: 0.33
Nodes (9): _connect(), get_all_corrections(), get_correction(), init_db(), _norm_key(), Persistent PM corrections to parsed line items.  Keyed by (file_name, original, Upserts a correction. Only non-None fields overwrite; pass all three for a full, Returns {(file_name, original_description_lower): {rate, unit, venue}} for bulk (+1 more)

### Community 13 - "WhatsApp/Email Share Links"
Cohesion: 0.14
Nodes (13): Design Health Score — 23/40 (Acceptable), Design Specificity Verdict, False Positives (discarded), Minor Observations, [P0] "Generate Quotation" has no guard rail before a client-facing document, [P0] The Annual Markup is a no-op for 76% of the catalogue — while claiming otherwise, [P0] The application is not operable by keyboard, [P1] Closed modals stay in the tab order, exposing a destructive action (+5 more)

## Knowledge Gaps
- **24 isolated node(s):** `ICONS`, `draftItems`, `historyCache`, `lastMatches`, `lastLibraryMatches` (+19 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Red Cube Smart Quotation Engine (index.html)` connect `app.js` to `Frontend-Backend API Bridge`, `Core Compile & Sync Pipeline`?**
  _High betweenness centrality (0.015) - this node is a cross-community bridge._
- **Why does `syncFolder()` connect `Core Compile & Sync Pipeline` to `app.js`, `Frontend-Backend API Bridge`?**
  _High betweenness centrality (0.012) - this node is a cross-community bridge._
- **What connects `ICONS`, `draftItems`, `historyCache` to the rest of the system?**
  _24 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Desktop App Backend API` be split into smaller, more focused modules?**
  _Cohesion score 0.05272108843537415 - nodes in this community are weakly interconnected._
- **Should `Historical Quote Parsing Engine` be split into smaller, more focused modules?**
  _Cohesion score 0.06802721088435375 - nodes in this community are weakly interconnected._
- **Should `Excel/Word Document Generation` be split into smaller, more focused modules?**
  _Cohesion score 0.07928118393234672 - nodes in this community are weakly interconnected._
- **Should `Frontend-Backend API Bridge` be split into smaller, more focused modules?**
  _Cohesion score 0.14666666666666667 - nodes in this community are weakly interconnected._