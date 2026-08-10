# Graph Report - Qoutation-maker  (2026-08-11)

## Corpus Check
- 57 files · ~75,234 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1311 nodes · 2257 edges · 70 communities (46 shown, 24 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 51 edges (avg confidence: 0.7)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `86350a08`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- parsing.py
- doc_generator.py
- api
- app.js
- QuotationApi
- history_db.py
- esc
- Red Cube Smart Quotation Engine (index.html)
- 2026-07-31T08-08-49Z__index-html.md
- image_store.py
- catalog_db.py
- compute_totals
- ._get_model
- create
- Invoices UI — Design Spec
- test_end_to_end.py
- test_doc_generation.py
- parse_files
- .save_correction
- generate_excel_dynamic
- test_history_db.py
- test_image_store.py
- test_indexing.py
- CLAUDE.md
- run.sh
- test_catalog_db.py
- test_crossfill.py
- app.py
- test_corrections.py
- syncFolder
- .index_files
- design_parser.py
- ._live_image_refs
- export_onnx.py
- test_invoices_db.py
- test_jobs_db.py
- jobs_db.py
- test_design_parser.py
- Design System: Red Cube Smart Quotation Engine
- test_js_api_contract.py
- invoices_db.py
- compute_item_boq
- test_rate_card.py
- _insert_excel_logo
- Product
- extract_labelled_dimensions
- _apply_labelled_dimensions
- renderHistoryTable
- classify_item_type
- Red Cube Smart Quotation Engine
- .create_job
- .generate_invoice_document
- .merge_designs_to_proposal
- compute_valid_until
- .get_storage_report
- .export_diagnostics
- .add_rate_card_item
- .compute_design_estimate
- .create_invoice_from_quotation
- .get_estimator_options
- .get_install_health
- .get_review_queue
- .get_vat_summary
- .list_corrections
- .merge_clients
- .open_source_file
- .parse_design_files
- .pick_design_files
- .restore_backup
- .run_backup

## God Nodes (most connected - your core abstractions)
1. `QuotationApi` - 87 edges
2. `api()` - 49 edges
3. `showToast()` - 34 edges
4. `esc()` - 31 edges
5. `icon()` - 30 edges
6. `Red Cube Smart Quotation Engine (index.html)` - 28 edges
7. `make()` - 25 edges
8. `compute_item_boq()` - 22 edges
9. `generate_word_dynamic()` - 22 edges
10. `create()` - 21 edges

## Surprising Connections (you probably didn't know these)
- `Red Cube Logo image asset (red_cube_logo.png)` --semantically_similar_to--> `CSS-drawn Red Cube Icon (brandlock cube3d)`  [INFERRED] [semantically similar]
  assets/red_cube_logo.png → index.html
- `requests` --conceptually_related_to--> `runImageSearch()`  [INFERRED]
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

## Communities (70 total, 24 thin omitted)

### Community 0 - "parsing.py"
Cohesion: 0.05
Nodes (61): fetch_image_from_url(), fetch_image_suggestions(), import_local_file(), Image helpers: embedded-image extraction, best-effort online image search,…, Uniform shape for the JS API: a ref for storage, a URL for rendering., Extracts image data from an openpyxl drawing and stores it. Returns a ref or ""., Stores bytes pulled straight out of a document part (docx/pdf). Returns a ref…, Downloads an arbitrary image URL and stores it. Best-effort. (+53 more)

### Community 1 - "doc_generator.py"
Cohesion: 0.14
Nodes (21): _add_page_number(), _build_footer(), generate_word_dynamic(), item_image(), _load_terms_config(), _no_borders(), Dynamic Excel/Word quotation generation. Rows are generated to exactly match…, The image field of a line item, preferring the ref and falling back to legacy… (+13 more)

### Community 2 - "api"
Cohesion: 0.11
Nodes (38): addJobCost(), api(), applyBulkVenue(), applyCompanyBranding(), bootBackend(), changeJobStatus(), checkDbStatus(), deleteCatalogItem() (+30 more)

### Community 3 - "app.js"
Cohesion: 0.05
Nodes (56): adjustRate(), applyCatalogFilter(), catalogCache, closeCatalogItemModal(), closeClientLedgerModal(), closeModal(), closeSettingsModal(), closeSuccessModal() (+48 more)

### Community 5 - "history_db.py"
Cohesion: 0.07
Nodes (45): _add_client_column(), _add_column(), _add_lifecycle_columns(), _add_quote_number_column(), all_image_refs(), allocate_quote_number(), _backfill_clients(), _connect() (+37 more)

### Community 6 - "esc"
Cohesion: 0.13
Nodes (35): bannerError(), esc(), estAddCutout(), estMissingMaterialForm(), estRemoveCutout(), estSetCutout(), formatAge(), groupByFile() (+27 more)

### Community 7 - "Red Cube Smart Quotation Engine (index.html)"
Cohesion: 0.13
Nodes (25): addCustomDraftRow(), addMatchedItemToDraft(), applyImageToItem(), applyLibraryMatch(), cloneHistoryItem(), closeImagePicker(), deleteDraftItem(), goToNewQuotation() (+17 more)

### Community 8 - "2026-07-31T08-08-49Z__index-html.md"
Cohesion: 0.14
Nodes (13): Design Health Score — 23/40 (Acceptable), Design Specificity Verdict, False Positives (discarded), Minor Observations, [P0] "Generate Quotation" has no guard rail before a client-facing document, [P0] The Annual Markup is a no-op for 76% of the catalogue — while claiming otherwise, [P0] The application is not operable by keyboard, [P1] Closed modals stay in the tab order, exposing a destructive action (+5 more)

### Community 9 - "image_store.py"
Cohesion: 0.08
Nodes (44): collect_orphans(), _ensure_dir(), exists(), ingest(), is_data_uri(), is_ref(), _normalize(), path_for() (+36 more)

### Community 10 - "catalog_db.py"
Cohesion: 0.07
Nodes (41): add_catalog_item(), _backfill_normalized(), _connect(), count_items(), _dedupe_before_unique_index(), delete_catalog_item(), find_catalog_item_by_description(), get_catalog_items() (+33 more)

### Community 11 - "compute_totals"
Cohesion: 0.25
Nodes (15): compute_totals(), Subtotal -> discount -> VAT on discounted subtotal -> grand total. Shared by…, items(), The money math. Every number a client sees comes out of compute_totals., A flat discount larger than the order must zero the total, never go negative., A negative discount would otherwise silently inflate the price above list., test_discount_cannot_exceed_subtotal(), test_empty_draft_totals_zero() (+7 more)

### Community 12 - "._get_model"
Cohesion: 0.14
Nodes (8): _distance_to_similarity(), _elapsed_years(), Saves a photo under a description. `image_value` may be a ref or a data URI —…, Age of a historical quote in *fractional* years, for compounding the annual…, Converts ChromaDB's squared-L2 distance into a real cosine similarity…, Lazy loads the embedding model to save initial window boot time., Embeddings for every catalog title, cached until the catalog changes. Keyed on…, Enriches draft line items with the cost_price behind each one, for margin…

### Community 13 - "create"
Cohesion: 0.07
Nodes (55): _build_staging(), create(), _decrypt_to(), default_destination(), _derive_key(), ensure_passphrase(), find_cloud_folders(), generate_passphrase() (+47 more)

### Community 14 - "Invoices UI — Design Spec"
Cohesion: 0.18
Nodes (10): 1. Nav & tab changes, 2. Raising an invoice, 3. Invoices list view, 4. Invoice detail modal, 5. Reports, 6. Error handling, 7. Testing, Invoices UI — Design Spec (+2 more)

### Community 15 - "test_end_to_end.py"
Cohesion: 0.07
Nodes (24): api(), archive_with_photo(), fixture, Full pipeline against the real sample quote files: parse -> index -> search ->…, Re-syncing the same archive must not accumulate duplicate image files., A ref has to resolve all the way to bytes inside the generated file., The exact-string lookup this replaces never matched a real multi-line quote…, The two bugs that made the review queue untrustworthy, checked together: the… (+16 more)

### Community 16 - "test_doc_generation.py"
Cohesion: 0.13
Nodes (13): End-to-end generation of the client-facing quotation documents.…, python-docx defaults to Letter, which is the wrong paper for a UAE business and…, The PM can save a draft before adding lines; that must not raise., One install serves one company; if this ever comes back empty the masthead and…, A dropped row is worse than a wrong total: it is invisible on the client's copy…, test_an_empty_quotation_still_produces_a_document(), test_company_branding_is_loaded_from_config(), test_every_line_item_reaches_the_excel_sheet() (+5 more)

### Community 17 - "parse_files"
Cohesion: 0.14
Nodes (17): ocr_status(), parse_files(), _parse_pdf(), _parse_raster(), Reports which OCR backend is available, if any. Neither easyocr nor pytesseract…, OCR at native resolution — deliberately no downsampling, since dimension text…, One entry per page of a (possibly 25-page) drawing deck., A single-page entry for a PNG/JPG drawing, OCR'd when a backend is available. (+9 more)

### Community 18 - ".save_correction"
Cohesion: 0.33
Nodes (3): Applies a PM correction to a single indexed item: updates it live in ChromaDB…, Applies one venue to every indexed item from a given source file. Venue is a…, Lighter-weight than save_correction: clears the review flag on an item the PM…

### Community 19 - "generate_excel_dynamic"
Cohesion: 0.17
Nodes (13): _apply_print_setup(), _detect_template_columns(), generate_excel_dynamic(), load_image_bytes(), _prepare_thumbnail(), Resolves a line item's image field to raw bytes. Accepts a content-addressed…, Normalizes an arbitrary product photo into a clean, undistorted thumbnail.…, Row height in points, clearing whichever is taller: the photo or the text… (+5 more)

### Community 20 - "test_history_db.py"
Cohesion: 0.09
Nodes (24): build_mailto_link(), build_whatsapp_link(), _item_summary_text(), Builds share links for WhatsApp and Email. Never sends anything itself — the…, parametrize, quote(), Client identity, quote numbering and the ledger., pywebview dispatches each JS call on its own thread, so two compiles can… (+16 more)

### Community 21 - "test_image_store.py"
Cohesion: 0.11
Nodes (22): png_bytes(), A small real PNG. Built rather than committed so the suite has no binary…, The content-addressed image store — deduplication, refs, and legacy…, Quotations saved before the store existed hold inline base64 and must still…, The whole point of hashing: 352 indexed items held only 206 distinct photos., Normalizing before hashing is what makes this work — the same photo arriving as…, PNG in, JPEG out. Re-encoding photographs was 6.8x smaller on the live library., A photograph must not survive the store at anything close to its raw pixel size. (+14 more)

### Community 22 - "test_indexing.py"
Cohesion: 0.10
Nodes (18): item(), parametrize, Index identity and the embedding backend., A half-file cached in place would fail confusingly at load time instead., Ids used to be `item_{position}`, so a re-sync could land a PM's correction on…, Falling back to sentence-transformers when the model is absent would pick a…, _distance_to_similarity converts squared L2 into cosine assuming unit vectors;…, Padding is masked out of the mean pool, so batch composition must not move a… (+10 more)

### Community 25 - "test_catalog_db.py"
Cohesion: 0.12
Nodes (9): The catalog: uniqueness, and a lookup that can actually match a real quote line., Quote descriptions carry a spec block under the product name, which is why the…, A 3-character catalog name is contained in almost any description., Without this the lookup returned an arbitrary duplicate, so the cost behind a…, An existing install can already hold duplicates; the unique index cannot be…, test_legacy_duplicates_are_collapsed_by_migration(), test_same_description_upserts_instead_of_duplicating(), test_title_line_match_handles_real_quote_lines() (+1 more)

### Community 26 - "test_crossfill.py"
Cohesion: 0.25
Nodes (15): make_items(), Photo cross-fill: borrowing a picture from the nearest photographed twin.…, This is how "Delivery" ended up showing a photo lifted from a furniture…, The batched matmul must keep rows and columns aligned — a transpose slip here…, Silently borrowing against misaligned vectors would attach arbitrary photos., Accelerate's BLAS raises spurious FP-status warnings; they must not reach the…, test_borrows_from_the_nearest_photographed_item(), test_distant_items_are_left_without_a_photo() (+7 more)

### Community 27 - "app.py"
Cohesion: 0.06
Nodes (37): _bind_estimator_dropzone(), crossfill_images(), _handle_estimator_drop(), _is_generic_service(), _load_sync_config(), main(), True when a line prices a service, so borrowing a product photo for it is…, Native counterpart to the JS drop handler on #est-dropzone. The browser's File… (+29 more)

### Community 28 - "test_corrections.py"
Cohesion: 0.19
Nodes (11): parsed_item(), Corrections — specifically that they no longer freeze fields the PM never…, A pre-existing row with rate 0 is the signature of the old snapshot bug, not an…, Fixing a venue today must not un-pin a rate corrected last month., A typo'd or renamed field must not silently pin something unexpected., test_dismissal_pins_nothing_but_clears_the_flag(), test_later_correction_adds_to_pinned_fields(), test_legacy_rows_backfill_without_pinning_a_zero_rate() (+3 more)

### Community 29 - "syncFolder"
Cohesion: 0.17
Nodes (17): changeMarkup(), compileQuote(), preflightWarnings(), searchMatcher(), syncFolder(), chromadb, datefinder, google-api-python-client (+9 more)

### Community 30 - ".index_files"
Cohesion: 0.29
Nodes (4): _item_id(), Stable identity for an indexed item: a hash of what it *is*. IDs used to be…, Loads a freshly parsed index into a scratch collection, leaving the live one…, Swaps the staged index in for the live one, once it is known to be complete.…

### Community 31 - "design_parser.py"
Cohesion: 0.23
Nodes (11): _assign_dimensions(), _build_page(), _detect_cutouts(), _pick_title(), Multi-file, multi-page intake for design drawings feeding the Automated Design…, Finds openings called out on the drawing (windows, niches, TV recesses). Only…, The drawing's own name for the thing, taken as the largest non-boilerplate text., Turns a page's dimension list into length/height/depth in metres. Preference… (+3 more)

### Community 34 - "test_invoices_db.py"
Cohesion: 0.09
Nodes (33): inv(), make(), fixture, Invoices and the payment ledger against them., Derived from the ledger, so deleting a payment cannot leave a stale total…, Overdue is about money, not paperwork age., A draft is not a taxable supply. Filing on it would overstate the liability, so…, An invoice number is a tax record. Two invoices sharing one is a filing problem. (+25 more)

### Community 35 - "test_jobs_db.py"
Cohesion: 0.06
Nodes (17): jobs(), fixture, Jobs, costs and suppliers — the money side of what happens after a quote is won., Real invoices carry rounding, delivery and part-quantities that qty x unit does…, A job reference ends up on supplier paperwork and delivery notes. Two jobs…, Costs are facts about money. Tidying a supplier record must not change any…, A job with no costs would otherwise report 100% margin and inflate the whole…, Booking the same work twice would double-count both revenue and costs. (+9 more)

### Community 36 - "jobs_db.py"
Cohesion: 0.10
Nodes (33): add_job_cost(), allocate_job_number(), _connect(), cost_breakdown(), create_job(), delete_job(), delete_job_cost(), delete_supplier() (+25 more)

### Community 37 - "test_design_parser.py"
Cohesion: 0.18
Nodes (16): extract_dimensions(), Pulls every dimension-looking token out of a blob of drawing text. Returns a…, meters_for(), parametrize, Drawing text -> dimensions. This is where a wrong answer is most expensive and…, The PM has to be able to tell a measured value from an assumed one., European-style CAD exports write 2,4m for 2.4m — reading it as 24 would be a…, test_a_page_with_no_dimensions_returns_nothing_rather_than_guessing() (+8 more)

### Community 38 - "Design System: Red Cube Smart Quotation Engine"
Cohesion: 0.08
Nodes (25): Buttons, Cards (stat cards, match cards, draft items, job cards), Colors, Components, Design System: Red Cube Smart Quotation Engine, Do:, Do's and Don'ts, Don't: (+17 more)

### Community 39 - "test_js_api_contract.py"
Cohesion: 0.09
Nodes (20): api(), api_class(), called_methods(), fixture, parametrize, Contract tests between app.js and QuotationApi. These exist because a green…, Pins the fix. Shipping every line item for a 300-row list was the expensive…, Cloning a past quote back into the draft needs the lines and their photo URLs. (+12 more)

### Community 40 - "invoices_db.py"
Cohesion: 0.06
Nodes (53): backup(), connect(), integrity_check(), list_backups(), migrate(), prune_backups(), Shared SQLite plumbing: connections, versioned migrations, and backups. Each…, Reclaims free pages. Worth running after a bulk delete or a blob migration,… (+45 more)

### Community 41 - "compute_item_boq"
Cohesion: 0.06
Nodes (56): aggregate(), _arch_surfaces(), compute_item_boq(), _counter_surfaces(), dimension_message(), _line(), missing_required_dims(), net_surface_area() (+48 more)

### Community 42 - "test_rate_card.py"
Cohesion: 0.06
Nodes (47): KeyError, add_rate_card_item(), _build_column_map(), get_rate_card(), load_labor_config(), load_rate_card(), MissingRateError, _normalize_header() (+39 more)

### Community 43 - "_insert_excel_logo"
Cohesion: 0.22
Nodes (9): create_fallback_template(), _insert_excel_logo(), _load_logo_scaled(), Loads COMPANY['logo_path'] if configured and scales it to fit within a bounding…, Places the configured logo in the top-right corner of the sheet, out of the way…, Creates the branding/header block (rows 1-9) from scratch when no template file…, fixture, The app ships a fallback template generator for a fresh install; use it so the… (+1 more)

### Community 44 - "Product"
Cohesion: 0.15
Nodes (12): Accessibility & Inclusion, Brand Commitments, Capabilities and Constraints, Design Direction (standing preference), Evidence on Hand, Operating Context, Platform, Positioning (+4 more)

### Community 45 - "extract_labelled_dimensions"
Cohesion: 0.18
Nodes (11): extract_labelled_dimensions(), _infer_bare_unit(), Guesses the unit of a dimension written without one. Drawing convention in this…, Named dimensions found in the drawing text, as {field: metres}. Later mentions…, Normalizes a magnitude + unit to metres., _to_meters(), 600 DEEP" is a real way to write it and is not supported — the label has to…, `THK 18` names the MDF, not how deep the counter is. Treating it as depth would… (+3 more)

### Community 46 - "_apply_labelled_dimensions"
Cohesion: 0.29
Nodes (7): _apply_labelled_dimensions(), Fills gaps in `assigned` from named callouts, without overriding what was…, The paired callout is the stronger signal; labels only fill what is still zero., The whole point: this drawing used to stop at 'Enter Depth'., test_a_counter_stating_its_depth_now_prices_end_to_end(), test_a_labelled_depth_fills_the_gap_a_paired_callout_leaves(), test_a_measured_dimension_is_never_overwritten_by_a_label()

### Community 47 - "renderHistoryTable"
Cohesion: 0.36
Nodes (8): applyHistoryFilters(), filterHistory(), loadHistory(), paymentCellHtml(), renderHistoryTable(), setHistoryStatusFilter(), statusPillHtml(), updatePayment()

### Community 48 - "classify_item_type"
Cohesion: 0.50
Nodes (4): classify_item_type(), Maps drawing text to one of the estimator's item types. Returns (type,…, `matched` is what tells the UI the type was defaulted rather than read, so the…, test_an_unrecognised_title_falls_back_to_wall_and_reports_no_match()

### Community 49 - "Red Cube Smart Quotation Engine"
Cohesion: 0.29
Nodes (6): Knowledge graph (graphify), Optional: OCR for raster drawings (PNG/JPG dimension detection), Project structure, Red Cube Smart Quotation Engine, Running the app, Setup

### Community 54 - "compute_valid_until"
Cohesion: 0.40
Nodes (5): compute_valid_until(), Returns quote_date + validity_days as YYYY-MM-DD. Falls back to today +…, Falls back to today rather than raising mid-compile and losing the quote., test_valid_until_adds_days(), test_valid_until_tolerates_unparseable_date()

## Knowledge Gaps
- **76 isolated node(s):** `ICONS`, `draftItems`, `historyCache`, `lastMatches`, `lastLibraryMatches` (+71 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **24 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `QuotationApi` connect `QuotationApi` to `._get_model`, `.save_correction`, `app.py`, `.index_files`, `._live_image_refs`, `.create_job`, `.generate_invoice_document`, `.merge_designs_to_proposal`, `.get_storage_report`, `.export_diagnostics`, `.add_rate_card_item`, `.compute_design_estimate`, `.create_invoice_from_quotation`, `.get_estimator_options`, `.get_install_health`, `.get_review_queue`, `.get_vat_summary`, `.list_corrections`, `.merge_clients`, `.open_source_file`, `.parse_design_files`, `.pick_design_files`, `.restore_backup`, `.run_backup`?**
  _High betweenness centrality (0.118) - this node is a cross-community bridge._
- **Why does `png_bytes()` connect `test_image_store.py` to `catalog_db.py`, `test_invoices_db.py`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Why does `make()` connect `test_invoices_db.py` to `test_image_store.py`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **What connects `ICONS`, `draftItems`, `historyCache` to the rest of the system?**
  _76 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `parsing.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05069124423963134 - nodes in this community are weakly interconnected._
- **Should `doc_generator.py` be split into smaller, more focused modules?**
  _Cohesion score 0.1422924901185771 - nodes in this community are weakly interconnected._
- **Should `api` be split into smaller, more focused modules?**
  _Cohesion score 0.11379800853485064 - nodes in this community are weakly interconnected._