# Graph Report - Qoutation-maker  (2026-08-07)

## Corpus Check
- 38 files · ~43,340 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 707 nodes · 1257 edges · 34 communities (30 shown, 4 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 42 edges (avg confidence: 0.72)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d6166bb3`
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
- loadCatalog
- app.py
- test_end_to_end.py
- renderHistoryTable
- connect
- .save_correction
- pdf_export.py
- test_history_db.py
- test_image_store.py
- test_indexing.py
- CLAUDE.md
- run.sh
- test_catalog_db.py
- test_crossfill.py
- embedder.py
- test_corrections.py
- syncFolder
- .index_files
- logging_setup.py
- ._live_image_refs
- export_onnx.py

## God Nodes (most connected - your core abstractions)
1. `QuotationApi` - 47 edges
2. `api()` - 34 edges
3. `Red Cube Smart Quotation Engine (index.html)` - 28 edges
4. `showToast()` - 21 edges
5. `icon()` - 19 edges
6. `esc()` - 19 edges
7. `generate_word_dynamic()` - 18 edges
8. `_connect()` - 18 edges
9. `connect()` - 17 edges
10. `switchTab()` - 14 edges

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

## Communities (34 total, 4 thin omitted)

### Community 0 - "parsing.py"
Cohesion: 0.05
Nodes (61): fetch_image_from_url(), fetch_image_suggestions(), import_local_file(), Image helpers: embedded-image extraction, best-effort online image search,…, Uniform shape for the JS API: a ref for storage, a URL for rendering., Extracts image data from an openpyxl drawing and stores it. Returns a ref or ""., Stores bytes pulled straight out of a document part (docx/pdf). Returns a ref…, Downloads an arbitrary image URL and stores it. Best-effort. (+53 more)

### Community 1 - "doc_generator.py"
Cohesion: 0.06
Nodes (60): _add_page_number(), _apply_print_setup(), _build_footer(), compute_totals(), compute_valid_until(), create_fallback_template(), _detect_template_columns(), generate_excel_dynamic() (+52 more)

### Community 2 - "api"
Cohesion: 0.14
Nodes (27): api(), applyBulkVenue(), applyCompanyBranding(), applyImageToItem(), applyLibraryMatch(), bootBackend(), checkDbStatus(), deleteHistoryItem() (+19 more)

### Community 3 - "app.js"
Cohesion: 0.08
Nodes (39): addCustomDraftRow(), addMatchedItemToDraft(), adjustRate(), catalogCache, cloneHistoryItem(), closeCatalogItemModal(), closeClientLedgerModal(), closeImagePicker() (+31 more)

### Community 4 - "QuotationApi"
Cohesion: 0.06
Nodes (6): QuotationApi, Opens the original quote file a flagged item came from, so a PM can see the row…, Folds one client record into another, moving their quotes across. This is the…, Every stored correction. Without a way to see these, a bad correction could…, What the app is using on disk, and how much of it is reclaimable., Returns indexed items flagged during parsing as low-confidence rate and/or…

### Community 5 - "history_db.py"
Cohesion: 0.07
Nodes (45): _add_client_column(), _add_column(), _add_lifecycle_columns(), _add_quote_number_column(), all_image_refs(), allocate_quote_number(), _backfill_clients(), _connect() (+37 more)

### Community 6 - "esc"
Cohesion: 0.16
Nodes (24): changeMarkup(), esc(), formatAge(), groupByFile(), icon(), loadHomeRecent(), loadReviewQueue(), money() (+16 more)

### Community 7 - "Red Cube Smart Quotation Engine (index.html)"
Cohesion: 0.15
Nodes (19): goToNewQuotation(), goToSync(), initTabsKeyboardNav(), openCatalogItemModal(), openImagePicker(), openModal(), openSettingsModal(), positionActiveTabPill() (+11 more)

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
Cohesion: 0.14
Nodes (23): apply_correction(), _clean_fields(), _connect(), count_corrections(), delete_correction(), get_all_corrections(), get_correction(), init_db() (+15 more)

### Community 12 - "._get_model"
Cohesion: 0.22
Nodes (4): Saves a photo under a description. `image_value` may be a ref or a data URI —…, Lazy loads the embedding model to save initial window boot time., Embeddings for every catalog title, cached until the catalog changes. Keyed on…, Enriches draft line items with the cost_price behind each one, for margin…

### Community 13 - "loadCatalog"
Cohesion: 0.50
Nodes (5): applyCatalogFilter(), deleteCatalogItem(), filterCatalog(), loadCatalog(), renderCatalogTable()

### Community 14 - "app.py"
Cohesion: 0.18
Nodes (11): crossfill_images(), _distance_to_similarity(), _elapsed_years(), _is_generic_service(), _load_sync_config(), main(), Age of a historical quote in *fractional* years, for compounding the annual…, Converts ChromaDB's squared-L2 distance into a real cosine similarity… (+3 more)

### Community 15 - "test_end_to_end.py"
Cohesion: 0.07
Nodes (24): api(), archive_with_photo(), fixture, Full pipeline against the real sample quote files: parse -> index -> search ->…, Re-syncing the same archive must not accumulate duplicate image files., A ref has to resolve all the way to bytes inside the generated file., The exact-string lookup this replaces never matched a real multi-line quote…, The two bugs that made the review queue untrustworthy, checked together: the… (+16 more)

### Community 16 - "renderHistoryTable"
Cohesion: 0.43
Nodes (7): applyHistoryFilters(), filterHistory(), loadHistory(), renderHistoryTable(), setHistoryStatusFilter(), statusPillHtml(), updatePayment()

### Community 17 - "connect"
Cohesion: 0.13
Nodes (25): backup(), connect(), integrity_check(), list_backups(), migrate(), prune_backups(), Shared SQLite plumbing: connections, versioned migrations, and backups. Each…, Reclaims free pages. Worth running after a bulk delete or a blob migration,… (+17 more)

### Community 18 - ".save_correction"
Cohesion: 0.33
Nodes (3): Applies a PM correction to a single indexed item: updates it live in ChromaDB…, Applies one venue to every indexed item from a given source file. Venue is a…, Lighter-weight than save_correction: clears the review flag on an item the PM…

### Community 19 - "pdf_export.py"
Cohesion: 0.33
Nodes (5): convert_to_pdf(), open_file(), PDF export via MS Office COM automation (win32com), with graceful offline-safe…, Converts an xlsx/docx file to PDF using the installed MS Office application via…, Opens a file with the OS default handler (e.g. default PDF viewer).

### Community 20 - "test_history_db.py"
Cohesion: 0.09
Nodes (24): build_mailto_link(), build_whatsapp_link(), _item_summary_text(), Builds share links for WhatsApp and Email. Never sends anything itself — the…, parametrize, quote(), Client identity, quote numbering and the ledger., pywebview dispatches each JS call on its own thread, so two compiles can… (+16 more)

### Community 21 - "test_image_store.py"
Cohesion: 0.11
Nodes (22): png_bytes(), A small real PNG. Built rather than committed so the suite has no binary…, The content-addressed image store — deduplication, refs, and legacy…, Quotations saved before the store existed hold inline base64 and must still…, The whole point of hashing: 352 indexed items held only 206 distinct photos., Normalizing before hashing is what makes this work — the same photo arriving as…, PNG in, JPEG out. Re-encoding photographs was 6.8x smaller on the live library., A photograph must not survive the store at anything close to its raw pixel size. (+14 more)

### Community 22 - "test_indexing.py"
Cohesion: 0.14
Nodes (12): item(), parametrize, Index identity and the embedding backend., Ids used to be `item_{position}`, so a re-sync could land a PM's correction on…, _distance_to_similarity converts squared L2 into cosine assuming unit vectors;…, Padding is masked out of the mean pool, so batch composition must not move a…, test_batching_matches_single_pass(), test_embeddings_are_unit_normalized() (+4 more)

### Community 25 - "test_catalog_db.py"
Cohesion: 0.12
Nodes (9): The catalog: uniqueness, and a lookup that can actually match a real quote line., Quote descriptions carry a spec block under the product name, which is why the…, A 3-character catalog name is contained in almost any description., Without this the lookup returned an arbitrary duplicate, so the cost behind a…, An existing install can already hold duplicates; the unique index cannot be…, test_legacy_duplicates_are_collapsed_by_migration(), test_same_description_upserts_instead_of_duplicating(), test_title_line_match_handles_real_quote_lines() (+1 more)

### Community 26 - "test_crossfill.py"
Cohesion: 0.25
Nodes (15): make_items(), Photo cross-fill: borrowing a picture from the nearest photographed twin.…, This is how "Delivery" ended up showing a photo lifted from a furniture…, The batched matmul must keep rows and columns aligned — a transpose slip here…, Silently borrowing against misaligned vectors would attach arbitrary photos., Accelerate's BLAS raises spurious FP-status warnings; they must not reach the…, test_borrows_from_the_nearest_photographed_item(), test_distant_items_are_left_without_a_photo() (+7 more)

### Community 27 - "embedder.py"
Cohesion: 0.17
Nodes (10): get_embedder(), _mean_pool(), onnx_available(), OnnxEmbedder, Sentence embeddings, with a runtime that does not require PyTorch. `sentence-…, The original backend, kept for dev checkouts that have not exported the ONNX…, Returns the process-wide embedder, loading it on first use. Lazy because…, Attention-masked mean pooling, then L2 normalization. Padding tokens must be… (+2 more)

### Community 28 - "test_corrections.py"
Cohesion: 0.19
Nodes (11): parsed_item(), Corrections — specifically that they no longer freeze fields the PM never…, A pre-existing row with rate 0 is the signature of the old snapshot bug, not an…, Fixing a venue today must not un-pin a rate corrected last month., A typo'd or renamed field must not silently pin something unexpected., test_dismissal_pins_nothing_but_clears_the_flag(), test_later_correction_adds_to_pinned_fields(), test_legacy_rows_backfill_without_pinning_a_zero_rate() (+3 more)

### Community 29 - "syncFolder"
Cohesion: 0.23
Nodes (13): compileQuote(), preflightWarnings(), syncFolder(), datefinder, google-api-python-client, google-auth-httplib2, google-auth-oauthlib, requirements.txt (Python dependency manifest) (+5 more)

### Community 30 - ".index_files"
Cohesion: 0.29
Nodes (4): _item_id(), Stable identity for an indexed item: a hash of what it *is*. IDs used to be…, Loads a freshly parsed index into a scratch collection, leaving the live one…, Swaps the staged index in for the live one, once it is known to be complete.…

### Community 31 - "logging_setup.py"
Cohesion: 0.38
Nodes (6): get_logger(), File logging for a desktop app whose console nobody ever sees. Failures used to…, Installs a rotating file handler plus console output. Safe to call more than…, Logs an exception with its traceback and returns the JS API's error envelope.…, report(), setup()

## Knowledge Gaps
- **26 isolated node(s):** `ICONS`, `draftItems`, `historyCache`, `lastMatches`, `lastLibraryMatches` (+21 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `QuotationApi` connect `QuotationApi` to `._live_image_refs`, `._get_model`, `app.py`, `.save_correction`, `.index_files`?**
  _High betweenness centrality (0.098) - this node is a cross-community bridge._
- **Why does `png_bytes()` connect `test_image_store.py` to `corrections_db.py`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **What connects `ICONS`, `draftItems`, `historyCache` to the rest of the system?**
  _26 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `parsing.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05069124423963134 - nodes in this community are weakly interconnected._
- **Should `doc_generator.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05837173579109063 - nodes in this community are weakly interconnected._
- **Should `api` be split into smaller, more focused modules?**
  _Cohesion score 0.1396011396011396 - nodes in this community are weakly interconnected._
- **Should `app.js` be split into smaller, more focused modules?**
  _Cohesion score 0.07897793263646923 - nodes in this community are weakly interconnected._