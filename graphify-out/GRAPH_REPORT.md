# Graph Report - Qoutation-maker  (2026-08-10)

## Corpus Check
- 53 files · ~70,735 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1200 nodes · 2045 edges · 68 communities (44 shown, 24 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 51 edges (avg confidence: 0.7)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `9f74d2b1`
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
- corrections_db.py
- ._get_model
- create
- Invoices UI — Design Spec
- test_end_to_end.py
- loadCatalog
- connect
- .save_correction
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
- ._live_image_refs
- export_onnx.py
- test_invoices_db.py
- test_jobs_db.py
- jobs_db.py
- design_parser.py
- Design System: Red Cube Smart Quotation Engine
- test_js_api_contract.py
- invoices_db.py
- calculators.py
- RateCard
- rate_card.py
- Product
- compute_item_boq
- openModal
- conftest.py
- Red Cube Smart Quotation Engine
- RateItem
- .create_job
- .generate_invoice_document
- .merge_designs_to_proposal
- _to_float
- .get_storage_report
- workspace
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
1. `QuotationApi` - 86 edges
2. `api()` - 48 edges
3. `showToast()` - 33 edges
4. `esc()` - 31 edges
5. `icon()` - 30 edges
6. `Red Cube Smart Quotation Engine (index.html)` - 28 edges
7. `make()` - 25 edges
8. `create()` - 21 edges
9. `money()` - 20 edges
10. `_connect()` - 20 edges

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

## Communities (68 total, 24 thin omitted)

### Community 0 - "parsing.py"
Cohesion: 0.05
Nodes (61): fetch_image_from_url(), fetch_image_suggestions(), import_local_file(), Image helpers: embedded-image extraction, best-effort online image search,…, Uniform shape for the JS API: a ref for storage, a URL for rendering., Extracts image data from an openpyxl drawing and stores it. Returns a ref or ""., Stores bytes pulled straight out of a document part (docx/pdf). Returns a ref…, Downloads an arbitrary image URL and stores it. Best-effort. (+53 more)

### Community 1 - "doc_generator.py"
Cohesion: 0.06
Nodes (60): _add_page_number(), _apply_print_setup(), _build_footer(), compute_totals(), compute_valid_until(), create_fallback_template(), _detect_template_columns(), generate_excel_dynamic() (+52 more)

### Community 2 - "api"
Cohesion: 0.14
Nodes (29): addJobCost(), api(), applyBulkVenue(), applyCompanyBranding(), bannerError(), bootBackend(), changeJobStatus(), checkDbStatus() (+21 more)

### Community 3 - "app.js"
Cohesion: 0.06
Nodes (41): adjustRate(), applyHistoryFilters(), catalogCache, CONFIDENCE_LABELS, COST_CATEGORIES, deleteHistoryItem(), draftItems, estimatorPages (+33 more)

### Community 5 - "history_db.py"
Cohesion: 0.07
Nodes (46): _add_client_column(), _add_column(), _add_lifecycle_columns(), _add_quote_number_column(), all_image_refs(), allocate_quote_number(), _backfill_clients(), _connect() (+38 more)

### Community 6 - "esc"
Cohesion: 0.10
Nodes (39): esc(), estAddCutout(), estAddMaterial(), estMissingMaterialForm(), estRemoveCutout(), estSetCutout(), estSetLaborRate(), estSetRate() (+31 more)

### Community 7 - "Red Cube Smart Quotation Engine (index.html)"
Cohesion: 0.09
Nodes (33): addCustomDraftRow(), addMatchedItemToDraft(), applyImageToItem(), applyLibraryMatch(), cloneHistoryItem(), closeClientLedgerModal(), closeImagePicker(), closeModal() (+25 more)

### Community 8 - "2026-07-31T08-08-49Z__index-html.md"
Cohesion: 0.14
Nodes (13): Design Health Score — 23/40 (Acceptable), Design Specificity Verdict, False Positives (discarded), Minor Observations, [P0] "Generate Quotation" has no guard rail before a client-facing document, [P0] The Annual Markup is a no-op for 76% of the catalogue — while claiming otherwise, [P0] The application is not operable by keyboard, [P1] Closed modals stay in the tab order, exposing a destructive action (+5 more)

### Community 9 - "image_store.py"
Cohesion: 0.08
Nodes (44): collect_orphans(), _ensure_dir(), exists(), ingest(), is_data_uri(), is_ref(), _normalize(), path_for() (+36 more)

### Community 10 - "catalog_db.py"
Cohesion: 0.16
Nodes (18): add_catalog_item(), _backfill_normalized(), _connect(), count_items(), _dedupe_before_unique_index(), delete_catalog_item(), find_catalog_item_by_description(), get_catalog_items() (+10 more)

### Community 11 - "corrections_db.py"
Cohesion: 0.20
Nodes (17): apply_correction(), _clean_fields(), _connect(), count_corrections(), delete_correction(), get_all_corrections(), get_correction(), init_db() (+9 more)

### Community 12 - "._get_model"
Cohesion: 0.14
Nodes (8): _distance_to_similarity(), _elapsed_years(), Saves a photo under a description. `image_value` may be a ref or a data URI —…, Age of a historical quote in *fractional* years, for compounding the annual…, Converts ChromaDB's squared-L2 distance into a real cosine similarity…, Lazy loads the embedding model to save initial window boot time., Embeddings for every catalog title, cached until the catalog changes. Keyed on…, Enriches draft line items with the cost_price behind each one, for margin…

### Community 13 - "create"
Cohesion: 0.08
Nodes (51): _build_staging(), create(), _decrypt_to(), default_destination(), _derive_key(), ensure_passphrase(), find_cloud_folders(), generate_passphrase() (+43 more)

### Community 14 - "Invoices UI — Design Spec"
Cohesion: 0.18
Nodes (10): 1. Nav & tab changes, 2. Raising an invoice, 3. Invoices list view, 4. Invoice detail modal, 5. Reports, 6. Error handling, 7. Testing, Invoices UI — Design Spec (+2 more)

### Community 15 - "test_end_to_end.py"
Cohesion: 0.07
Nodes (24): api(), archive_with_photo(), fixture, Full pipeline against the real sample quote files: parse -> index -> search ->…, Re-syncing the same archive must not accumulate duplicate image files., A ref has to resolve all the way to bytes inside the generated file., The exact-string lookup this replaces never matched a real multi-line quote…, The two bugs that made the review queue untrustworthy, checked together: the… (+16 more)

### Community 16 - "loadCatalog"
Cohesion: 0.33
Nodes (7): applyCatalogFilter(), closeCatalogItemModal(), deleteCatalogItem(), filterCatalog(), loadCatalog(), renderCatalogTable(), saveCatalogItem()

### Community 17 - "connect"
Cohesion: 0.14
Nodes (24): backup(), connect(), integrity_check(), list_backups(), migrate(), prune_backups(), Shared SQLite plumbing: connections, versioned migrations, and backups. Each…, Reclaims free pages. Worth running after a bulk delete or a blob migration,… (+16 more)

### Community 18 - ".save_correction"
Cohesion: 0.33
Nodes (3): Applies a PM correction to a single indexed item: updates it live in ChromaDB…, Applies one venue to every indexed item from a given source file. Venue is a…, Lighter-weight than save_correction: clears the review flag on an item the PM…

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
Nodes (35): _bind_estimator_dropzone(), crossfill_images(), _handle_estimator_drop(), _is_generic_service(), _load_sync_config(), main(), True when a line prices a service, so borrowing a product photo for it is…, Native counterpart to the JS drop handler on #est-dropzone. The browser's File… (+27 more)

### Community 28 - "test_corrections.py"
Cohesion: 0.19
Nodes (11): parsed_item(), Corrections — specifically that they no longer freeze fields the PM never…, A pre-existing row with rate 0 is the signature of the old snapshot bug, not an…, Fixing a venue today must not un-pin a rate corrected last month., A typo'd or renamed field must not silently pin something unexpected., test_dismissal_pins_nothing_but_clears_the_flag(), test_later_correction_adds_to_pinned_fields(), test_legacy_rows_backfill_without_pinning_a_zero_rate() (+3 more)

### Community 29 - "syncFolder"
Cohesion: 0.15
Nodes (19): changeMarkup(), compileQuote(), preflightWarnings(), runImageSearch(), searchMatcher(), showSuccessModal(), syncFolder(), chromadb (+11 more)

### Community 30 - ".index_files"
Cohesion: 0.29
Nodes (4): _item_id(), Stable identity for an indexed item: a hash of what it *is*. IDs used to be…, Loads a freshly parsed index into a scratch collection, leaving the live one…, Swaps the staged index in for the live one, once it is known to be complete.…

### Community 34 - "test_invoices_db.py"
Cohesion: 0.09
Nodes (33): inv(), make(), fixture, Invoices and the payment ledger against them., Derived from the ledger, so deleting a payment cannot leave a stale total…, Overdue is about money, not paperwork age., A draft is not a taxable supply. Filing on it would overstate the liability, so…, An invoice number is a tax record. Two invoices sharing one is a filing problem. (+25 more)

### Community 35 - "test_jobs_db.py"
Cohesion: 0.06
Nodes (17): jobs(), fixture, Jobs, costs and suppliers — the money side of what happens after a quote is won., Real invoices carry rounding, delivery and part-quantities that qty x unit does…, A job reference ends up on supplier paperwork and delivery notes. Two jobs…, Costs are facts about money. Tidying a supplier record must not change any…, A job with no costs would otherwise report 100% margin and inflate the whole…, Booking the same work twice would double-count both revenue and costs. (+9 more)

### Community 36 - "jobs_db.py"
Cohesion: 0.10
Nodes (33): add_job_cost(), allocate_job_number(), _connect(), cost_breakdown(), create_job(), delete_job(), delete_job_cost(), delete_supplier() (+25 more)

### Community 37 - "design_parser.py"
Cohesion: 0.10
Nodes (31): _assign_dimensions(), _build_page(), classify_item_type(), _detect_cutouts(), extract_dimensions(), _infer_bare_unit(), ocr_status(), parse_files() (+23 more)

### Community 38 - "Design System: Red Cube Smart Quotation Engine"
Cohesion: 0.08
Nodes (25): Buttons, Cards (stat cards, match cards, draft items, job cards), Colors, Components, Design System: Red Cube Smart Quotation Engine, Do:, Do's and Don'ts, Don't: (+17 more)

### Community 39 - "test_js_api_contract.py"
Cohesion: 0.09
Nodes (20): api(), api_class(), called_methods(), fixture, parametrize, Contract tests between app.js and QuotationApi. These exist because a green…, Cloning a past quote back into the draft needs the lines and their photo URLs., The match cards render <img src="${m.image_src}">. (+12 more)

### Community 40 - "invoices_db.py"
Cohesion: 0.12
Nodes (28): add_payment(), aging_report(), allocate_invoice_number(), client_statement(), _connect(), create_invoice(), delete_invoice(), delete_payment() (+20 more)

### Community 41 - "calculators.py"
Cohesion: 0.11
Nodes (17): aggregate(), _arch_surfaces(), _counter_surfaces(), _line(), options_payload(), Deterministic BOQ rules engine for the Automated Design Estimator. Every number…, A portal arch: two legs plus a header, clad on both faces, with a soffit wrap.…, Prices one material line against the rate card. qty is rounded up to whole… (+9 more)

### Community 42 - "RateCard"
Cohesion: 0.16
Nodes (8): KeyError, MissingRateError, RateCard, Indexed, read-only view over the rate card CSV plus the labor rate config., Returns the RateItem for `code`, or raises MissingRateError., Average unit cost in AED for `code`., AED/hour for a trade. A `Labor` category in the CSV takes precedence over the…, Raised when a BOQ line references an item code the card does not contain.…

### Community 43 - "rate_card.py"
Cohesion: 0.25
Nodes (13): add_rate_card_item(), _build_column_map(), get_rate_card(), load_labor_config(), load_rate_card(), _normalize_header(), _parse_range(), Loader for the master rate card CSV that prices the automated design estimator.… (+5 more)

### Community 44 - "Product"
Cohesion: 0.15
Nodes (12): Accessibility & Inclusion, Brand Commitments, Capabilities and Constraints, Design Direction (standing preference), Evidence on Hand, Operating Context, Platform, Positioning (+4 more)

### Community 45 - "compute_item_boq"
Cohesion: 0.17
Nodes (12): compute_item_boq(), dimension_message(), net_surface_area(), paint_liters(), Gross clad area from the item's own geometry, minus every cutout. Returns…, m2 -> whole 8x4 sheets, with wastage applied before rounding up., Framing skeleton: perimeter plates plus a vertical every STUD_SPACING_M.…, Litres of wet product needed to put `coats` over `area_m2`. (+4 more)

### Community 46 - "openModal"
Cohesion: 0.22
Nodes (10): editJob(), fillJobForm(), openCatalogItemModal(), openImagePicker(), openModal(), openNewJob(), openSuppliers(), runLibrarySearch() (+2 more)

### Community 48 - "conftest.py"
Cohesion: 0.43
Nodes (6): fixture, Shared fixtures. Every store keeps its path in a module-level `DB_FILE` and…, temp_catalog(), temp_corrections(), temp_history(), temp_images()

### Community 49 - "Red Cube Smart Quotation Engine"
Cohesion: 0.29
Nodes (6): Knowledge graph (graphify), Optional: OCR for raster drawings (PNG/JPG dimension detection), Project structure, Red Cube Smart Quotation Engine, Running the app, Setup

### Community 54 - "_to_float"
Cohesion: 0.50
Nodes (3): Substring match over code, description and usage — powers the material swap…, Pulls the first number out of a cell, tolerating currency text and thousands…, _to_float()

### Community 56 - "workspace"
Cohesion: 0.67
Nodes (3): fixture, A throwaway app directory with real databases in it., workspace()

## Knowledge Gaps
- **76 isolated node(s):** `ICONS`, `draftItems`, `historyCache`, `lastMatches`, `lastLibraryMatches` (+71 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **24 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `QuotationApi` connect `QuotationApi` to `._get_model`, `.save_correction`, `app.py`, `.index_files`, `._live_image_refs`, `.create_job`, `.generate_invoice_document`, `.merge_designs_to_proposal`, `.get_storage_report`, `.add_rate_card_item`, `.compute_design_estimate`, `.create_invoice_from_quotation`, `.get_estimator_options`, `.get_install_health`, `.get_review_queue`, `.get_vat_summary`, `.list_corrections`, `.merge_clients`, `.open_source_file`, `.parse_design_files`, `.pick_design_files`, `.restore_backup`, `.run_backup`?**
  _High betweenness centrality (0.137) - this node is a cross-community bridge._
- **Why does `png_bytes()` connect `test_image_store.py` to `conftest.py`, `test_invoices_db.py`?**
  _High betweenness centrality (0.060) - this node is a cross-community bridge._
- **Why does `make()` connect `test_invoices_db.py` to `test_image_store.py`?**
  _High betweenness centrality (0.027) - this node is a cross-community bridge._
- **What connects `ICONS`, `draftItems`, `historyCache` to the rest of the system?**
  _76 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `parsing.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05069124423963134 - nodes in this community are weakly interconnected._
- **Should `doc_generator.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05837173579109063 - nodes in this community are weakly interconnected._
- **Should `api` be split into smaller, more focused modules?**
  _Cohesion score 0.1354679802955665 - nodes in this community are weakly interconnected._