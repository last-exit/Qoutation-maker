# Graph Report - quotation-maker-app  (2026-08-11)

## Corpus Check
- 76 files · ~108,331 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1819 nodes · 3000 edges · 111 communities (72 shown, 39 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 52 edges (avg confidence: 0.7)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e99abda5`
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
- renderHistoryTable
- classify_item_type
- Red Cube Smart Quotation Engine
- Handover checklist — setting the app up for the PM
- .create_job
- .generate_invoice_document
- .merge_designs_to_proposal
- compute_valid_until
- .get_storage_report
- .export_diagnostics
- .add_rate_card_item
- .compute_design_estimate
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
- image_tools.py
- test_removing_a_payment_reopens_the_balance
- test_a_settled_invoice_is_never_overdue
- test_vat_summary_covers_sent_invoices_and_flags_drafts
- test_numbers_are_never_reused
- test_a_quotation_cannot_be_invoiced_twice
- calculators.py
- shop_config.py
- openModal
- stud_linear_meters
- renderDraft
- missing_required_dims
- loadCatalog
- _ring_surfaces
- sheets_required
- .reset_fabrication_settings
- .save_fabrication_settings
- materials.py
- image_tools.py
- export.py
- is_ref
- .search_materials
- image_tools.py
- loadCatalog
- test_removing_a_payment_reopens_the_balance
- .index_files
- TestReadStateMessaging
- aging_report
- .generate_invoice_document
- test_a_quotation_cannot_be_invoiced_twice
- .begin_design_import
- .create_invoice_from_quotation
- .design_page_counts
- .finish_design_import
- .parse_design_pages
- .test_a_page_with_no_attachable_dimensions_still_parses_as_one_item
- test_vat_summary_covers_sent_invoices_and_flags_drafts
- test_a_quotation_cannot_be_invoiced_twice
- logging_setup.py
- pdf_export.py
- aging_report
- .export_app_package

## God Nodes (most connected - your core abstractions)
1. `QuotationApi` - 96 edges
2. `api()` - 55 edges
3. `showToast()` - 40 edges
4. `esc()` - 38 edges
5. `compute_item_boq()` - 36 edges
6. `recalcEstimate()` - 35 edges
7. `icon()` - 33 edges
8. `Red Cube Smart Quotation Engine (index.html)` - 28 edges
9. `make()` - 25 edges
10. `money()` - 23 edges

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

## Communities (111 total, 39 thin omitted)

### Community 0 - "parsing.py"
Cohesion: 0.05
Nodes (61): fetch_image_from_url(), fetch_image_suggestions(), import_local_file(), Image helpers: embedded-image extraction, best-effort online image search, URL/f, Uniform shape for the JS API: a ref for storage, a URL for rendering., Extracts image data from an openpyxl drawing and stores it. Returns a ref or ""., Stores bytes pulled straight out of a document part (docx/pdf). Returns a ref or, Downloads an arbitrary image URL and stores it. Best-effort. (+53 more)

### Community 1 - "doc_generator.py"
Cohesion: 0.14
Nodes (21): _add_page_number(), _build_footer(), generate_word_dynamic(), load_image_bytes(), _load_terms_config(), _no_borders(), Dynamic Excel/Word quotation generation.  Rows are generated to exactly match, Resolves a line item's image field to raw bytes.      Accepts a content-addres (+13 more)

### Community 2 - "api"
Cohesion: 0.10
Nodes (42): addJobCost(), api(), applyBulkVenue(), applyCompanyBranding(), applyImageToItem(), applyLibraryMatch(), bootBackend(), changeJobStatus() (+34 more)

### Community 3 - "app.js"
Cohesion: 0.22
Nodes (10): editJob(), fillJobForm(), openCatalogItemModal(), openImagePicker(), openModal(), openNewJob(), openSuppliers(), runLibrarySearch() (+2 more)

### Community 5 - "history_db.py"
Cohesion: 0.07
Nodes (46): _add_client_column(), _add_column(), _add_lifecycle_columns(), _add_quote_number_column(), all_image_refs(), allocate_quote_number(), _backfill_clients(), _connect() (+38 more)

### Community 6 - "esc"
Cohesion: 0.11
Nodes (36): bannerError(), esc(), estDimSummary(), estManualNeeded(), estMaterialSearch(), estMissingMaterialForm(), exportAppPackage(), formatAge() (+28 more)

### Community 7 - "Red Cube Smart Quotation Engine (index.html)"
Cohesion: 0.10
Nodes (31): addCustomDraftRow(), addMatchedItemToDraft(), cloneHistoryItem(), closeClientLedgerModal(), closeImagePicker(), closeModal(), closeSettingsModal(), closeSuccessModal() (+23 more)

### Community 8 - "2026-07-31T08-08-49Z__index-html.md"
Cohesion: 0.14
Nodes (13): Design Health Score — 23/40 (Acceptable), Design Specificity Verdict, False Positives (discarded), Minor Observations, [P0] "Generate Quotation" has no guard rail before a client-facing document, [P0] The Annual Markup is a no-op for 76% of the catalogue — while claiming otherwise, [P0] The application is not operable by keyboard, [P1] Closed modals stay in the tab order, exposing a destructive action (+5 more)

### Community 9 - "image_store.py"
Cohesion: 0.08
Nodes (44): collect_orphans(), _ensure_dir(), exists(), ingest(), is_data_uri(), is_ref(), _normalize(), path_for() (+36 more)

### Community 10 - "catalog_db.py"
Cohesion: 0.07
Nodes (39): add_catalog_item(), _backfill_normalized(), _connect(), count_items(), _dedupe_before_unique_index(), delete_catalog_item(), find_catalog_item_by_description(), get_catalog_items() (+31 more)

### Community 11 - "compute_totals"
Cohesion: 0.25
Nodes (15): compute_totals(), Subtotal -> discount -> VAT on discounted subtotal -> grand total. Shared by, items(), The money math. Every number a client sees comes out of compute_totals., A flat discount larger than the order must zero the total, never go negative., A negative discount would otherwise silently inflate the price above list., test_discount_cannot_exceed_subtotal(), test_empty_draft_totals_zero() (+7 more)

### Community 12 - "._get_model"
Cohesion: 0.14
Nodes (8): _distance_to_similarity(), _elapsed_years(), Saves a photo under a description. `image_value` may be a ref or a data URI —, Age of a historical quote in *fractional* years, for compounding the annual mark, Converts ChromaDB's squared-L2 distance into a real cosine similarity percentage, Lazy loads the embedding model to save initial window boot time., Embeddings for every catalog title, cached until the catalog changes., Enriches draft line items with the cost_price behind each one, for margin report

### Community 13 - "create"
Cohesion: 0.07
Nodes (54): _build_staging(), create(), _decrypt_to(), default_destination(), _derive_key(), ensure_passphrase(), find_cloud_folders(), generate_passphrase() (+46 more)

### Community 14 - "Invoices UI — Design Spec"
Cohesion: 0.18
Nodes (10): 1. Nav & tab changes, 2. Raising an invoice, 3. Invoices list view, 4. Invoice detail modal, 5. Reports, 6. Error handling, 7. Testing, Invoices UI — Design Spec (+2 more)

### Community 15 - "test_end_to_end.py"
Cohesion: 0.07
Nodes (23): api(), archive_with_photo(), Full pipeline against the real sample quote files: parse -> index -> search -> c, Re-syncing the same archive must not accumulate duplicate image files., A ref has to resolve all the way to bytes inside the generated file., The exact-string lookup this replaces never matched a real multi-line quote line, The two bugs that made the review queue untrustworthy, checked together: the, A QuotationApi wired to throwaway stores. (+15 more)

### Community 16 - "test_doc_generation.py"
Cohesion: 0.13
Nodes (13): End-to-end generation of the client-facing quotation documents.  `compute_tota, python-docx defaults to Letter, which is the wrong paper for a UAE business and, The PM can save a draft before adding lines; that must not raise., One install serves one company; if this ever comes back empty the masthead and t, A dropped row is worse than a wrong total: it is invisible on the client's copy, test_an_empty_quotation_still_produces_a_document(), test_company_branding_is_loaded_from_config(), test_every_line_item_reaches_the_excel_sheet() (+5 more)

### Community 17 - "parse_files"
Cohesion: 0.18
Nodes (14): parse_page_range(), _parse_pdf(), _parse_raster(), One entry per page of a (possibly 25-page) drawing deck.      `page_start` / `pa, A single-page entry for a PNG/JPG drawing, OCR'd when a backend is available., Parses a slice of one file's pages.      Returns the same page dicts `parse_file, Classifies why OCR yielded nothing, from the status `_ocr_tokens` returned., What to tell the PM on a page that produced no dimensions. (+6 more)

### Community 18 - ".save_correction"
Cohesion: 0.33
Nodes (3): Applies a PM correction to a single indexed item: updates it live in ChromaDB an, Applies one venue to every indexed item from a given source file.          Ven, Lighter-weight than save_correction: clears the review flag on an item the PM ha

### Community 19 - "generate_excel_dynamic"
Cohesion: 0.17
Nodes (13): _apply_print_setup(), _detect_template_columns(), generate_excel_dynamic(), item_image(), _prepare_thumbnail(), The image field of a line item, preferring the ref and falling back to legacy in, Normalizes an arbitrary product photo into a clean, undistorted thumbnail., Row height in points, clearing whichever is taller: the photo or the text beside (+5 more)

### Community 20 - "test_history_db.py"
Cohesion: 0.10
Nodes (22): build_mailto_link(), build_whatsapp_link(), _item_summary_text(), Builds share links for WhatsApp and Email. Never sends anything itself — the cal, quote(), Client identity, quote numbering and the ledger., pywebview dispatches each JS call on its own thread, so two compiles can overlap, The list renders client, date, total and a line count. Omitting `items` without (+14 more)

### Community 21 - "test_image_store.py"
Cohesion: 0.11
Nodes (22): png_bytes(), A small real PNG. Built rather than committed so the suite has no binary fixture, The content-addressed image store — deduplication, refs, and legacy compatibilit, Quotations saved before the store existed hold inline base64 and must still rend, The whole point of hashing: 352 indexed items held only 206 distinct photos., Normalizing before hashing is what makes this work — the same photo arriving as, PNG in, JPEG out. Re-encoding photographs was 6.8x smaller on the live library., A photograph must not survive the store at anything close to its raw pixel size. (+14 more)

### Community 22 - "test_indexing.py"
Cohesion: 0.10
Nodes (17): item(), Index identity and the embedding backend., A half-file cached in place would fail confusingly at load time instead., Ids used to be `item_{position}`, so a re-sync could land a PM's correction on a, Falling back to sentence-transformers when the model is absent would pick a back, _distance_to_similarity converts squared L2 into cosine assuming unit vectors; t, Padding is masked out of the mean pool, so batch composition must not move a vec, A fresh clone has no models/ directory and no torch. Without the download it ins (+9 more)

### Community 25 - "test_catalog_db.py"
Cohesion: 0.12
Nodes (9): The catalog: uniqueness, and a lookup that can actually match a real quote line., Quote descriptions carry a spec block under the product name, which is why the o, A 3-character catalog name is contained in almost any description., Without this the lookup returned an arbitrary duplicate, so the cost behind a ma, An existing install can already hold duplicates; the unique index cannot be buil, test_legacy_duplicates_are_collapsed_by_migration(), test_same_description_upserts_instead_of_duplicating(), test_title_line_match_handles_real_quote_lines() (+1 more)

### Community 26 - "test_crossfill.py"
Cohesion: 0.25
Nodes (15): make_items(), Photo cross-fill: borrowing a picture from the nearest photographed twin.  Res, This is how "Delivery" ended up showing a photo lifted from a furniture quotatio, The batched matmul must keep rows and columns aligned — a transpose slip here wo, Silently borrowing against misaligned vectors would attach arbitrary photos., Accelerate's BLAS raises spurious FP-status warnings; they must not reach the lo, test_borrows_from_the_nearest_photographed_item(), test_distant_items_are_left_without_a_photo() (+7 more)

### Community 27 - "app.py"
Cohesion: 0.15
Nodes (12): download_model(), get_embedder(), _mean_pool(), onnx_available(), OnnxEmbedder, Sentence embeddings, with a runtime that does not require PyTorch.  `sentence-, The original backend, kept for dev checkouts that have not exported the ONNX mod, Fetches the ONNX model and tokenizer. Returns True once both are in place. (+4 more)

### Community 28 - "test_corrections.py"
Cohesion: 0.19
Nodes (11): parsed_item(), Corrections — specifically that they no longer freeze fields the PM never touche, A pre-existing row with rate 0 is the signature of the old snapshot bug, not an, Fixing a venue today must not un-pin a rate corrected last month., A typo'd or renamed field must not silently pin something unexpected., test_dismissal_pins_nothing_but_clears_the_flag(), test_later_correction_adds_to_pinned_fields(), test_legacy_rows_backfill_without_pinning_a_zero_rate() (+3 more)

### Community 29 - "syncFolder"
Cohesion: 0.15
Nodes (19): changeMarkup(), compileQuote(), preflightWarnings(), runImageSearch(), searchMatcher(), showSuccessModal(), syncFolder(), chromadb (+11 more)

### Community 30 - ".index_files"
Cohesion: 0.29
Nodes (4): _item_id(), Stable identity for an indexed item: a hash of what it *is*.      IDs used to, Loads a freshly parsed index into a scratch collection, leaving the live one alo, Swaps the staged index in for the live one, once it is known to be complete.

### Community 31 - "design_parser.py"
Cohesion: 0.13
Nodes (24): _assign_dimensions(), _build_page(), _detect_cutouts(), _dimension_tokens(), _elements_from_clusters(), _is_meaningful_label(), _label_for_cluster(), _legacy_element() (+16 more)

### Community 34 - "test_invoices_db.py"
Cohesion: 0.09
Nodes (31): make(), Invoices and the payment ledger against them., Derived from the ledger, so deleting a payment cannot leave a stale total behind, Overdue is about money, not paperwork age., A draft is not a taxable supply. Filing on it would overstate the liability, so, An invoice number is a tax record. Two invoices sharing one is a filing problem., Double-billing surfaces as an angry client, not as a crash., 50% on confirmation, 50% before handover — two payments against one invoice, whi (+23 more)

### Community 35 - "test_jobs_db.py"
Cohesion: 0.06
Nodes (15): Jobs, costs and suppliers — the money side of what happens after a quote is won., Real invoices carry rounding, delivery and part-quantities that qty x unit does, A job reference ends up on supplier paperwork and delivery notes. Two jobs shari, Costs are facts about money. Tidying a supplier record must not change any margi, A job with no costs would otherwise report 100% margin and inflate the whole fig, Booking the same work twice would double-count both revenue and costs., Not every job starts as a quotation — some are booked straight in., A quoted margin presented as a measured one is how a business finds out it lost (+7 more)

### Community 36 - "jobs_db.py"
Cohesion: 0.06
Nodes (57): backup(), connect(), integrity_check(), list_backups(), migrate(), prune_backups(), Shared SQLite plumbing: connections, versioned migrations, and backups.  Each, Reclaims free pages. Worth running after a bulk delete or a blob migration, both (+49 more)

### Community 37 - "test_design_parser.py"
Cohesion: 0.09
Nodes (32): _apply_labelled_dimensions(), extract_dimensions(), extract_labelled_dimensions(), _infer_bare_unit(), Normalizes a magnitude + unit to metres., Guesses the unit of a dimension written without one.      Drawing convention in, Pulls every dimension-looking token out of a blob of drawing text.      Returns, Named dimensions found in the drawing text, as {field: metres}.      Later menti (+24 more)

### Community 38 - "Design System: Red Cube Smart Quotation Engine"
Cohesion: 0.08
Nodes (25): Buttons, Cards (stat cards, match cards, draft items, job cards), Colors, Components, Design System: Red Cube Smart Quotation Engine, Do:, Do's and Don'ts, Don't: (+17 more)

### Community 39 - "test_js_api_contract.py"
Cohesion: 0.09
Nodes (16): api(), called_methods(), Contract tests between app.js and QuotationApi.  These exist because a green t, Pins the fix. Shipping every line item for a 300-row list was the expensive mist, Cloning a past quote back into the draft needs the lines and their photo URLs., The match cards render <img src="${m.image_src}">., pywebview serializes return values to JSON. A method returning a raw object surf, A renamed or removed backend method shows up as a silent no-op in the UI. (+8 more)

### Community 40 - "invoices_db.py"
Cohesion: 0.14
Nodes (23): add_payment(), allocate_invoice_number(), client_statement(), _connect(), create_invoice(), delete_invoice(), delete_payment(), _enrich() (+15 more)

### Community 41 - "compute_item_boq"
Cohesion: 0.12
Nodes (34): aggregate(), compute_item_boq(), Master summary across every item from every uploaded drawing.      Margin is a, Full deterministic BOQ for one detected item.      `spec` keys: item_type, lab, edited(), Pricing math for the design estimator.  These cover the arithmetic that decide, A drawing can declare more opening than wall. Net area must not go negative and, 25% margin means selling = factory x 1.25. Getting this backwards (treating it a (+26 more)

### Community 42 - "test_rate_card.py"
Cohesion: 0.06
Nodes (46): KeyError, add_rate_card_item(), _build_column_map(), get_rate_card(), load_labor_config(), load_rate_card(), MissingRateError, _normalize_header() (+38 more)

### Community 43 - "_insert_excel_logo"
Cohesion: 0.25
Nodes (8): create_fallback_template(), _insert_excel_logo(), _load_logo_scaled(), Loads COMPANY['logo_path'] if configured and scales it to fit within a bounding, Places the configured logo in the top-right corner of the sheet, out of the way, Creates the branding/header block (rows 1-9) from scratch when no template file, The app ships a fallback template generator for a fresh install; use it so the t, template()

### Community 44 - "Product"
Cohesion: 0.15
Nodes (12): Accessibility & Inclusion, Brand Commitments, Capabilities and Constraints, Design Direction (standing preference), Evidence on Hand, Operating Context, Platform, Positioning (+4 more)

### Community 45 - "extract_labelled_dimensions"
Cohesion: 0.05
Nodes (13): Curve geometry, checked against numbers you can work out by hand.  Every expecte, The old flat model used (2 x height) + opening. An arched head is longer., A disc is sawn flat out of board; it must not get a bent skin build-up., A curve bulging past its own centre must not read as its shallow twin., A rounded corner must not be priced as curved joinery., TestAnnulus, TestArchBandRun, TestArcLength (+5 more)

### Community 47 - "renderHistoryTable"
Cohesion: 0.17
Nodes (7): _elevation(), The original failure: eight elements on a page collapsed into a single row., A tower beside an 'Entrance Arch' label must not itself become an arch., A flat elevation carrying one dimensioned rectangle per entry in `elements`., Pages are parsed one at a time so each appears as it is read. The result must ma, TestIncrementalImport, TestPageDecomposition

### Community 48 - "classify_item_type"
Cohesion: 0.40
Nodes (5): classify_item_type(), Maps drawing text to one of the estimator's item types. Returns (type, matched_p, `matched` is what tells the UI the type was defaulted rather than read, so the P, test_an_unrecognised_title_falls_back_to_wall_and_reports_no_match(), test_item_type_is_classified_from_the_drawing_title()

### Community 49 - "Red Cube Smart Quotation Engine"
Cohesion: 0.29
Nodes (6): Knowledge graph (graphify), Optional: OCR for raster drawings (PNG/JPG dimension detection), Project structure, Red Cube Smart Quotation Engine, Running the app, Setup

### Community 50 - "Handover checklist — setting the app up for the PM"
Cohesion: 0.20
Nodes (9): 1. Install from a clean copy — do this first, 2. Enable OCR and shape detection (needed for PNG/JPG drawings), 3. Download the search model while there is internet, 4. Bring his real data across, 5. Set up the backup, and get the passphrase off the laptop, 6. Walk one real quotation through with him, Handover checklist — setting the app up for the PM, Known gaps (+1 more)

### Community 52 - ".generate_invoice_document"
Cohesion: 0.08
Nodes (23): apply_to_elements(), _bow_of_contour(), _crop(), detect(), _detect_circle(), _is_straight_edged(), _largest_contour(), Find the shape of a drawn object from the page image.  Curve detection used to r (+15 more)

### Community 54 - "compute_valid_until"
Cohesion: 0.40
Nodes (5): compute_valid_until(), Returns quote_date + validity_days as YYYY-MM-DD. Falls back to today + configur, Falls back to today rather than raising mid-compile and losing the quote., test_valid_until_adds_days(), test_valid_until_tolerates_unparseable_date()

### Community 71 - "image_tools.py"
Cohesion: 0.09
Nodes (12): flat_wall(), Pricing of curved, ring and arched elements.  The point of these tests is not th, Inventing a carcass the drawing never described would be a fabricated cost., Existing quotations must re-price to the same number after this feature., The estimator fills a blank; it never overrides the PM., Silently pricing the chord is the under-quote this feature exists to stop., A disc is sawn flat. Giving it a bent build-up swaps its carcass for skins., TestArch (+4 more)

### Community 72 - "test_removing_a_payment_reopens_the_balance"
Cohesion: 0.08
Nodes (10): config_file(), Editable fabrication settings.  These constants drive every curved price, so the, A number this project invented must never look like the workshop's own., A config file shaped like the real one, with labour rates already in it., A stray string in the config must not become part of a price., The fabrication block shares a file with the PM's labour rates., Never silently destroy a PM's labour rates, even when the file is broken., TestDescribe (+2 more)

### Community 73 - "test_a_settled_invoice_is_never_overdue"
Cohesion: 0.17
Nodes (12): _box_overlap_ratio(), _dedupe_tokens(), _dimension_like(), _ocr_tokens(), _prepare_for_ocr(), How many collected tokens look like a dimension callout., Scaled and contrast-normalised copy of a page for one OCR pass., Text tokens with their pixel boxes, unioned over several passes.      Returns (t (+4 more)

### Community 74 - "test_vat_summary_covers_sent_invoices_and_flags_drafts"
Cohesion: 0.10
Nodes (25): _boxes_related(), classify_page(), cluster(), _is_frame_segment(), measure(), _merge_parallel(), page_scale(), _point_to_segment() (+17 more)

### Community 75 - "test_numbers_are_never_reused"
Cohesion: 0.09
Nodes (21): Anti-goals, Approach C — page-type-aware hybrid, Definition of done, Ground truth already in the codebase, Hard constraints — do not violate these, Implementation status (2026-08-11), Master Prompt — Zone-Render Decomposition (Approach C), Role and objective (+13 more)

### Community 76 - "test_a_quotation_cannot_be_invoiced_twice"
Cohesion: 0.09
Nodes (33): developed_run_m(), geometry_of(), net_surface_area(), A circular or annular shelf: the ring itself, per shelf, plus its edge.      A, The spec's shape, defaulting to flat and never returning an unknown value., The curve parameters carried on a spec, normalised to floats., The length of material actually wrapped along the item.      For a flat item t, Gross clad area from the item's own geometry, minus every cutout.      Returns (+25 more)

### Community 78 - "calculators.py"
Cohesion: 0.10
Nodes (19): _apply_line_edits(), _arch_surfaces(), _counter_surfaces(), _line(), _material_choice_summary(), paint_liters(), Deterministic BOQ rules engine for the Automated Design Estimator.  Every numb, A portal arch: two legs plus a header, clad on both faces, with a soffit wrap. (+11 more)

### Community 79 - "shop_config.py"
Cohesion: 0.23
Nodes (11): options_payload(), Everything the UI needs to render the estimator, sourced from the card and the s, _coerce(), describe(), load(), Editable fabrication constants for curved and ring work.  Everything in here is, Clamps a configured value into a sane range, or returns None to use the default., Current fabrication settings as {key: value}, with problems reported.      Retur (+3 more)

### Community 80 - "openModal"
Cohesion: 0.05
Nodes (63): absorbParsedPage(), adjustRate(), applyImportAdjustments(), catalogCache, CONFIDENCE_LABELS, COST_CATEGORIES, draftItems, estAddCutout() (+55 more)

### Community 81 - "stud_linear_meters"
Cohesion: 0.08
Nodes (16): dim_fields(), key_of(), meta(), normalize(), options_payload(), The shapes a PM can pick, and how each maps onto geometry and materials.  The es, The merged shape key for a spec, accepting both new and legacy forms.      A `sh, The full shape definition for a spec. (+8 more)

### Community 82 - "renderDraft"
Cohesion: 0.18
Nodes (6): Line geometry, page classification, and splitting a sheet into elements.  The de, Cutouts are found against the sheet, not against one element.          Splitting, r"""OCR noise and a bare dimension are meaningless names; the sheet title stands, TestClustering, TestCutoutsSurviveDecomposition, TestJunkLabelsRejected

### Community 83 - "missing_required_dims"
Cohesion: 0.33
Nodes (6): dimension_message(), missing_required_dims(), The required dimension fields this spec has not supplied a positive value for., Names the specific fields still needed before an item type has any clad area., wall/arch depth is a build detail; counter/stage depth is half the object., test_depth_defaults_only_where_it_is_construction_thickness()

### Community 84 - "loadCatalog"
Cohesion: 0.13
Nodes (9): card(), _FakeCard, _FakeItem, Sheet-driven material resolution.  The estimator no longer names materials in co, A minimal stand-in so a test can control exactly which rows exist., The unit filter is what stops a Sheet query picking a stud., Determinism: two equally-suitable rows must resolve the same way every run., TestScoring (+1 more)

### Community 85 - "_ring_surfaces"
Cohesion: 0.10
Nodes (19): 10. Order of work, 1. One shape list, 2. Materials come from the sheet, 3. Quantities come from the Unit column, 4. Finishes become bundles, 5. The item card, 6. Dimension chips, 7. Reliability fixes (+11 more)

### Community 86 - "sheets_required"
Cohesion: 0.50
Nodes (4): m2 -> whole 8x4 sheets, with wastage applied before rounding up., sheets_required(), Sheets are bought whole; wastage has to be inside the ceiling, not after it., test_sheets_required_applies_wastage_before_rounding_up()

### Community 90 - "materials.py"
Cohesion: 0.14
Nodes (13): _pick(), One resolved material for a role: a PM override if given, else the sheet's best, Substrate, framing, fixings, brackets and adhesive for a shape, from the sheet., resolve_build_materials(), Query, Resolve which rate-card row fills each construction role.  The estimator used to, The best-matching rate item for `query`, or None if the sheet has nothing suitab, The substrate query for a merged shape key, defaulting to a flat wall. (+5 more)

### Community 93 - "image_tools.py"
Cohesion: 0.18
Nodes (10): 1. OCR that reports its own absence, 2. Shape detection with OpenCV, 3. Manual entry, front and centre, 4. Files, 5. Testing, 6. Order of work, A material that is not on the sheet, Decisions taken (+2 more)

### Community 96 - "export.py"
Cohesion: 0.14
Nodes (14): _normalised_label(), ocr_status(), parse_files(), A shape fingerprint used to recognise the same object drawn on another sheet., Links elements that appear on more than one sheet, and fills gaps between them., Parses every uploaded drawing into a flat list of pages.      Returns {"success", Reports which OCR backend is available, if any.      Neither easyocr nor pytesse, reconcile() (+6 more)

### Community 99 - "is_ref"
Cohesion: 0.33
Nodes (7): applyCatalogFilter(), closeCatalogItemModal(), deleteCatalogItem(), filterCatalog(), loadCatalog(), renderCatalogTable(), saveCatalogItem()

### Community 107 - "image_tools.py"
Cohesion: 0.31
Nodes (9): applyHistoryFilters(), deleteHistoryItem(), filterHistory(), loadHistory(), paymentCellHtml(), renderHistoryTable(), setHistoryStatusFilter(), statusPillHtml() (+1 more)

### Community 121 - "test_vat_summary_covers_sent_invoices_and_flags_drafts"
Cohesion: 0.10
Nodes (12): build(), collect_files(), _is_safe(), Packages the app into a zip that installs on another machine with one double-cli, Writes the package and returns (path, file_count, size_bytes)., True when a path is allowed into the package., Every file that belongs in the package, as (absolute_path, archive_name) pairs., Packaging the app for another machine.  The test that matters most here is the n (+4 more)

### Community 122 - "test_a_quotation_cannot_be_invoiced_twice"
Cohesion: 0.25
Nodes (10): _bind_estimator_dropzone(), crossfill_images(), _handle_estimator_drop(), _is_generic_service(), _load_sync_config(), main(), True when a line prices a service, so borrowing a product photo for it is mislea, Fills in photos for items that have none by borrowing from the most similar item (+2 more)

### Community 123 - "logging_setup.py"
Cohesion: 0.31
Nodes (8): collect_diagnostics(), get_logger(), File logging for a desktop app whose console nobody ever sees.  Failures used, Logs an exception with its traceback and returns the JS API's error envelope., Installs a rotating file handler plus console output. Safe to call more than onc, Bundles the logs and environment into one file the PM can send on.      The lo, report(), setup()

### Community 126 - "pdf_export.py"
Cohesion: 0.25
Nodes (7): convert_to_pdf(), open_file(), pdf_available(), PDF export via MS Office COM automation (win32com), with graceful offline-safe f, Opens a file with the OS default handler (e.g. default PDF viewer)., Converts an xlsx/docx file to PDF using the installed MS Office application via, Whether this machine can turn a document into a PDF.      Checked so the app c

### Community 127 - "aging_report"
Cohesion: 0.40
Nodes (5): aging_report(), get_invoices(), outstanding_total(), Outstanding money bucketed by how late it is — the collections worklist., One number for the dashboard: everything not yet collected.

## Knowledge Gaps
- **130 isolated node(s):** `ICONS`, `draftItems`, `historyCache`, `lastMatches`, `lastLibraryMatches` (+125 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **39 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `QuotationApi` connect `QuotationApi` to `.export_app_package`, `._get_model`, `.save_correction`, `.index_files`, `._live_image_refs`, `.create_job`, `.merge_designs_to_proposal`, `.get_storage_report`, `.export_diagnostics`, `.add_rate_card_item`, `.compute_design_estimate`, `.get_estimator_options`, `.get_install_health`, `.get_review_queue`, `.get_vat_summary`, `.list_corrections`, `.merge_clients`, `.open_source_file`, `.parse_design_files`, `.pick_design_files`, `.restore_backup`, `.run_backup`, `.reset_fabrication_settings`, `.save_fabrication_settings`, `.search_materials`, `aging_report`, `.begin_design_import`, `.create_invoice_from_quotation`, `.design_page_counts`, `.finish_design_import`, `.parse_design_pages`, `test_a_quotation_cannot_be_invoiced_twice`?**
  _High betweenness centrality (0.087) - this node is a cross-community bridge._
- **Why does `png_bytes()` connect `test_image_store.py` to `catalog_db.py`, `test_invoices_db.py`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._
- **Why does `make()` connect `test_invoices_db.py` to `test_image_store.py`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **What connects `ICONS`, `draftItems`, `historyCache` to the rest of the system?**
  _130 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `parsing.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05069124423963134 - nodes in this community are weakly interconnected._
- **Should `doc_generator.py` be split into smaller, more focused modules?**
  _Cohesion score 0.1422924901185771 - nodes in this community are weakly interconnected._
- **Should `api` be split into smaller, more focused modules?**
  _Cohesion score 0.10104529616724739 - nodes in this community are weakly interconnected._