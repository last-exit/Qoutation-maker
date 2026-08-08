# Graph Report - quotation-maker-app  (2026-08-08)

## Corpus Check
- 23 files · ~37,005 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 458 nodes · 844 edges · 29 communities (19 shown, 10 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 25 edges (avg confidence: 0.72)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c4b4f15e`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Desktop App Backend API
- Historical Quote Parsing Engine
- Excel/Word Document Generation
- Frontend-Backend API Bridge
- rate_card.py
- Frontend State & Icon System
- Core Compile & Sync Pipeline
- Quotation History Database
- History & Match Rendering
- Image Fetching & Thumbnailing
- app.js
- PM Corrections Database
- calculators.py
- WhatsApp/Email Share Links
- ._get_model
- app.py
- .save_correction
- .merge_designs_to_proposal
- .open_source_file
- .parse_design_files
- esc
- api
- renderDraft
- renderHistoryTable
- Red Cube Smart Quotation Engine
- .compute_design_estimate
- .get_estimator_options
- .get_review_queue
- .pick_design_files

## God Nodes (most connected - your core abstractions)
1. `QuotationApi` - 35 edges
2. `api()` - 32 edges
3. `Red Cube Smart Quotation Engine (index.html)` - 28 edges
4. `icon()` - 23 edges
5. `esc()` - 23 edges
6. `showToast()` - 22 edges
7. `recalcEstimate()` - 17 edges
8. `generate_word_dynamic()` - 17 edges
9. `switchTab()` - 14 edges
10. `syncFolder()` - 13 edges

## Surprising Connections (you probably didn't know these)
- `Red Cube Logo image asset (red_cube_logo.png)` --semantically_similar_to--> `CSS-drawn Red Cube Icon (brandlock cube3d)`  [INFERRED] [semantically similar]
  assets/red_cube_logo.png → index.html
- `Pillow` --conceptually_related_to--> `uploadImageForItem()`  [INFERRED]
  requirements.txt → app.js
- `switchTab()` --references--> `Compiler Workspace View (view-compiler)`  [INFERRED]
  app.js → index.html
- `switchTab()` --references--> `Quotation History View (view-history)`  [INFERRED]
  app.js → index.html
- `switchTab()` --references--> `Home View (view-home)`  [INFERRED]
  app.js → index.html

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Quotation Document Generation (Excel/Word export)** — app_compilequote, requirements_openpyxl, requirements_python_docx [INFERRED 0.85]
- **Semantic Search / Smart Matcher subsystem** — app_searchmatcher, requirements_chromadb, requirements_sentence_transformers [INFERRED 0.85]
- **Google Drive Historical Data Sync Pipeline** — app_syncfolder, requirements_google_api_python_client, requirements_google_auth_oauthlib, requirements_google_auth_httplib2, requirements_pymupdf, requirements_datefinder [INFERRED 0.75]

## Communities (29 total, 10 thin omitted)

### Community 1 - "Historical Quote Parsing Engine"
Cohesion: 0.07
Nodes (48): assign_images_to_rows(), _build_item(), _cell_image_base64(), classify_columns(), clean_rate(), _collect_spec_lines(), _distinct_row_cells(), evaluate_review_flags() (+40 more)

### Community 2 - "Excel/Word Document Generation"
Cohesion: 0.08
Nodes (42): _add_page_number(), _apply_print_setup(), _build_footer(), compute_totals(), compute_valid_until(), create_fallback_template(), decode_image_payload(), _detect_template_columns() (+34 more)

### Community 3 - "Frontend-Backend API Bridge"
Cohesion: 0.15
Nodes (19): closeSettingsModal(), closeSuccessModal(), goToNewQuotation(), goToSync(), onDiscountValueChange(), openSettingsModal(), positionActiveTabPill(), setDiscountType() (+11 more)

### Community 4 - "rate_card.py"
Cohesion: 0.08
Nodes (26): KeyError, add_rate_card_item(), _build_column_map(), get_rate_card(), load_labor_config(), load_rate_card(), MissingRateError, _normalize_header() (+18 more)

### Community 5 - "Frontend State & Icon System"
Cohesion: 0.29
Nodes (8): changeMarkup(), formatAge(), isBorrowedPhoto(), renderMatches(), searchMatcher(), upliftHtml(), chromadb, sentence-transformers

### Community 6 - "Core Compile & Sync Pipeline"
Cohesion: 0.21
Nodes (14): compileQuote(), preflightWarnings(), showSuccessModal(), syncFolder(), datefinder, google-api-python-client, google-auth-httplib2, google-auth-oauthlib (+6 more)

### Community 7 - "Quotation History Database"
Cohesion: 0.08
Nodes (28): crossfill_images(), _is_generic_service(), main(), True when a line prices a service, so borrowing a product photo for it is mislea, Fills in photos for items that have none by borrowing from the most similar item, _connect(), delete_quotation_history(), get_quotation_by_id() (+20 more)

### Community 9 - "Image Fetching & Thumbnailing"
Cohesion: 0.07
Nodes (40): _assign_dimensions(), _build_page(), classify_item_type(), _detect_cutouts(), extract_dimensions(), _infer_bare_unit(), ocr_status(), parse_files() (+32 more)

### Community 10 - "app.js"
Cohesion: 0.09
Nodes (26): CONFIDENCE_LABELS, draftItems, estimatorPages, estimatorResults, estimatorSpecs, estSet(), groupByFile(), historyCache (+18 more)

### Community 11 - "PM Corrections Database"
Cohesion: 0.33
Nodes (9): _connect(), get_all_corrections(), get_correction(), init_db(), _norm_key(), Persistent PM corrections to parsed line items.  Keyed by (file_name, original, Upserts a correction. Only non-None fields overwrite; pass all three for a full, Returns {(file_name, original_description_lower): {rate, unit, venue}} for bulk (+1 more)

### Community 12 - "calculators.py"
Cohesion: 0.08
Nodes (29): aggregate(), _arch_surfaces(), compute_item_boq(), _counter_surfaces(), dimension_message(), _line(), net_surface_area(), options_payload() (+21 more)

### Community 13 - "WhatsApp/Email Share Links"
Cohesion: 0.14
Nodes (13): Design Health Score — 23/40 (Acceptable), Design Specificity Verdict, False Positives (discarded), Minor Observations, [P0] "Generate Quotation" has no guard rail before a client-facing document, [P0] The Annual Markup is a no-op for 76% of the catalogue — while claiming otherwise, [P0] The application is not operable by keyboard, [P1] Closed modals stay in the tab order, exposing a destructive action (+5 more)

### Community 14 - "._get_model"
Cohesion: 0.25
Nodes (5): _distance_to_similarity(), _elapsed_years(), Converts ChromaDB's squared-L2 distance into a real cosine similarity percentage, Lazy loads sentence-transformers model to save initial window boot time., Age of a historical quote in *fractional* years, for compounding the annual mark

### Community 16 - ".save_correction"
Cohesion: 0.33
Nodes (3): Applies a PM correction to a single indexed item: updates it live in ChromaDB an, Applies one venue to every indexed item from a given source file.          Ven, Lighter-weight than save_correction: clears the review flag on an item the PM ha

### Community 21 - "esc"
Cohesion: 0.16
Nodes (24): esc(), estAddCutout(), estAddMaterial(), estMissingMaterialForm(), estRemoveCutout(), estSetCutout(), estSetLaborRate(), estSetRate() (+16 more)

### Community 22 - "api"
Cohesion: 0.14
Nodes (27): api(), applyBulkVenue(), applyCompanyBranding(), applyImageToItem(), applyLibraryMatch(), bootBackend(), checkDbStatus(), closeImagePicker() (+19 more)

### Community 24 - "renderDraft"
Cohesion: 0.36
Nodes (8): addCustomDraftRow(), addMatchedItemToDraft(), adjustRate(), cloneHistoryItem(), deleteDraftItem(), mergeDesignsToProposal(), renderDraft(), uid()

### Community 25 - "renderHistoryTable"
Cohesion: 0.38
Nodes (7): applyHistoryFilters(), deleteHistoryItem(), filterHistory(), loadHistory(), renderHistoryTable(), setHistoryStatusFilter(), statusPillHtml()

### Community 26 - "Red Cube Smart Quotation Engine"
Cohesion: 0.29
Nodes (6): Knowledge graph (graphify), Optional: OCR for raster drawings (PNG/JPG dimension detection), Project structure, Red Cube Smart Quotation Engine, Running the app, Setup

## Knowledge Gaps
- **32 isolated node(s):** `ICONS`, `draftItems`, `historyCache`, `lastMatches`, `lastLibraryMatches` (+27 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `QuotationApi` connect `Desktop App Backend API` to `Quotation History Database`, `._get_model`, `app.py`, `.save_correction`, `.merge_designs_to_proposal`, `.open_source_file`, `.parse_design_files`, `.compute_design_estimate`, `.get_estimator_options`, `.get_review_queue`, `.pick_design_files`?**
  _High betweenness centrality (0.116) - this node is a cross-community bridge._
- **What connects `ICONS`, `draftItems`, `historyCache` to the rest of the system?**
  _32 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Desktop App Backend API` be split into smaller, more focused modules?**
  _Cohesion score 0.11764705882352941 - nodes in this community are weakly interconnected._
- **Should `Historical Quote Parsing Engine` be split into smaller, more focused modules?**
  _Cohesion score 0.06802721088435375 - nodes in this community are weakly interconnected._
- **Should `Excel/Word Document Generation` be split into smaller, more focused modules?**
  _Cohesion score 0.07928118393234672 - nodes in this community are weakly interconnected._
- **Should `rate_card.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08232118758434548 - nodes in this community are weakly interconnected._
- **Should `Quotation History Database` be split into smaller, more focused modules?**
  _Cohesion score 0.0784313725490196 - nodes in this community are weakly interconnected._