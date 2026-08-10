import hashlib
import os
import re
import json
import webbrowser
from datetime import datetime
from pathlib import Path

import numpy as np
import chromadb
import webview
from webview.dom import DOMEventHandler

import backup
import db
import parsing
import doc_generator
import history_db
import invoices_db
import jobs_db
import image_store
import image_tools
import logging_setup
import maintenance
import pdf_export
import sharing
import corrections_db
import catalog_db
from embedder import get_embedder
import design_parser
import calculators
import rate_card

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "chroma_db"))
COLLECTION_NAME = "quotation_items"
PHOTO_COLLECTION_NAME = "photo_library"
# Where a rebuild is assembled before it replaces the live index. See index_files.
STAGING_COLLECTION_NAME = "quotation_items_staging"

log = logging_setup.setup()

# Cross-fill thresholds (cosine similarity on description embeddings). Above AUTO, two items
# are effectively the same product quoted twice, so a photo from one is safe to reuse on the
# other. Between SUGGEST and AUTO it is a likely-but-not-certain match, still attached but
# flagged more softly. Below SUGGEST we leave the item without a photo rather than guess.
CROSSFILL_AUTO = 0.82
CROSSFILL_SUGGEST = 0.70

# Cosine similarity a quote line must reach against a catalog title before its cost_price is
# borrowed for margin reporting. Set high deliberately: a wrong cost produces a confident,
# plausible-looking margin figure, which is worse than reporting no margin at all.
COST_MATCH_MIN = 0.80

# --- Sync scope --------------------------------------------------------------------
# The sync folder used to be the whole Drive, which meant every scan parsed the owner's
# personal files (class notes, assignments, WhatsApp exports) alongside the job archive.
# Measured against the live index: all 401 indexed items came from ALL THE QUOTATIONS,
# while 120 documents in sibling folders parsed to zero items.
#
# Scope is set by pointing the app at the right folder — an explicit, visible choice — and
# exclude_folders only removes directories that are definitively not document sources.
# It deliberately does NOT filter on filename keywords: that was tried before and silently
# dropped 12 real pricing files, so anything skipped here is reported back to the UI.
SYNC_CONFIG_PATH = Path(__file__).resolve().parent / "sync_config.json"

_DEFAULT_SYNC_CONFIG = {
    "default_path": "G:\\My Drive\\BOOM TREE\\ALL THE QUOTATIONS",
    "exclude_folders": [
        "Google AI Studio", "Gemini Gems", "Colab Notebooks", "Opal", "Google Earth",
        "Reports", "__pycache__", "venv", ".git", "node_modules",
    ],
}


def _resolve_default_path(path_str):
    if path_str and Path(path_str).exists():
        return path_str
    # Auto-detect macOS Google Drive paths or fallback to sample_quotes if configured path doesn't exist
    home = Path.home()
    mac_cloud = home / "Library" / "CloudStorage"
    if mac_cloud.exists():
        for d in mac_cloud.glob("GoogleDrive-*"):
            target = d / "My Drive" / "BOOM TREE" / "ALL THE QUOTATIONS"
            if target.exists():
                return str(target)
            target_gen = d / "My Drive"
            if target_gen.exists():
                return str(target_gen)
    mac_gd = home / "Google Drive" / "My Drive"
    if mac_gd.exists():
        return str(mac_gd)
    sample_dir = Path(__file__).resolve().parent / "sample_quotes"
    if sample_dir.exists():
        return str(sample_dir)
    return str(Path(__file__).resolve().parent)


def _load_sync_config():
    cfg = dict(_DEFAULT_SYNC_CONFIG)
    try:
        if SYNC_CONFIG_PATH.exists():
            with open(SYNC_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("default_path"):
                cfg = {**_DEFAULT_SYNC_CONFIG, **data}
    except Exception as e:
        print(f"Failed to load sync_config.json, using defaults: {e}")

    cfg["default_path"] = _resolve_default_path(cfg.get("default_path"))
    return cfg


SYNC_CONFIG = _load_sync_config()

# Matches this app's own output naming from compile_quotation: "{client}_Quotation_{ts}.ext".
SELF_GENERATED_RE = re.compile(r'_Quotation_\d{8}_\d{4}\.(xlsx|docx|pdf)$', re.I)


def _elapsed_years(quote_date):
    """Age of a historical quote in *fractional* years, for compounding the annual markup.

    Previously this was a whole-year subtraction (current_year - quote_year), which made the
    markup a no-op for anything quoted in the current calendar year — on the live index that
    is 304 of 401 items, so three quarters of all matches displayed an "Adjusted" rate
    identical to the original while the label still claimed a markup had been applied.

    Measuring from the real date instead means a six-month-old quote earns roughly half the
    annual uplift, and a quote from last week earns almost none — which is the intent.
    """
    if not quote_date:
        return 0.0
    text = str(quote_date).strip()[:10]
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            parsed = datetime.strptime(text[:len(datetime.now().strftime(fmt))], fmt)
            break
        except ValueError:
            continue
    else:
        return 0.0
    # Future-dated quotes (clock skew, typo'd year) must not discount the rate.
    return max(0.0, (datetime.now() - parsed).days / 365.25)


def _distance_to_similarity(distance):
    """Converts ChromaDB's squared-L2 distance into a real cosine similarity percentage.

    The collections are created without an explicit `hnsw:space`, so Chroma uses squared L2,
    and the embedding model returns unit vectors — for which  d^2 = 2 - 2*cos,  i.e.
    cos = 1 - d/2 with d already squared.

    The previous `1/(1+d)` never reached 0: a completely unrelated query still scored ~37%
    and the scale bottomed out at 33%, so every match looked plausible. Ranking was
    unaffected (both curves are monotonic in d) — only the number shown to the PM was wrong.
    """
    try:
        cos = 1.0 - (float(distance) / 2.0)
    except (TypeError, ValueError):
        return 0.0
    return round(max(0.0, min(1.0, cos)) * 100, 1)


# Line items that price labour, logistics or fees rather than a physical product.
# "storage" is deliberately absent: it describes a product feature far more often than a fee
# here ("Lego Wall with Storage"), and wrongly classing a product as a service would cost it
# its photo.
_GENERIC_SERVICE_RE = re.compile(
    r'\b(delivery|transport(ation)?|installation|install|crew|labour|labor|manpower|'
    r'dismantl\w*|removal|freight|shipping|handling|rental|hire|'
    r'supervis\w*|management fee|contingency|misc(ellaneous)?|sundr\w+|'
    r'discount|vat|charges?|fees?)\b', re.I)


def _is_generic_service(description):
    """True when a line prices a service, so borrowing a product photo for it is misleading."""
    text = str(description or "").strip()
    if not text:
        return True
    first_line = text.split("\n")[0]
    # Only treat it as a service when that is what the line is *about* — a product whose spec
    # happens to mention "installation" further down still deserves its photo.
    return bool(_GENERIC_SERVICE_RE.search(first_line))


def _item_id(item):
    """Stable identity for an indexed item: a hash of what it *is*.

    IDs used to be `item_{position in the parse output}`, so `item_42` meant nothing more
    than "the 42nd row of the last sync". The review queue hands these ids to the UI and
    corrections write back to them, so re-syncing while that tab was open could land a PM's
    edit on a completely different product. A content hash is the same for the same item
    across every rebuild, and different for a different one.
    """
    key = "\x1f".join((
        str(item.get('file_name', '')).strip().lower(),
        str(item.get('original_description', '')).strip().lower(),
        f"{float(item.get('historical_rate') or 0):.4f}",
    ))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]


def crossfill_images(items, embeddings):
    """Fills in photos for items that have none by borrowing from the most similar item that
    does — the same product often appears with a photo in one quote and text-only in another.

    Reuses the description embeddings already computed for indexing (no extra model calls).
    Borrowed photos are tagged in image_source so the UI can label them honestly rather than
    passing a photo from a different quote off as this exact line item's own.

    Returns the number of items that received a borrowed photo.
    """
    emb = np.asarray(embeddings, dtype=np.float32)
    if emb.ndim != 2 or emb.shape[0] != len(items):
        return 0

    have = [i for i, it in enumerate(items) if it.get("image_ref")]
    # A generic service line has no product to photograph, but its wording is close enough to
    # the same wording in another job for the embedding to score a confident match — which is
    # how "Delivery" ended up showing a photo lifted from a furniture quotation. Nothing here
    # can be illustrated by borrowing, so these are left without a photo on purpose.
    need = [i for i, it in enumerate(items)
            if not it.get("image_ref") and not _is_generic_service(it.get("original_description", ""))]
    if not have or not need:
        return 0

    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    unit = emb / np.clip(norms, 1e-9, None)
    have_mat = unit[have]

    filled = 0
    # Apple's Accelerate BLAS (numpy 2.x on macOS) leaves floating-point status flags set in
    # unused SIMD lanes, so every one of these matmuls raises divide-by-zero/overflow/invalid
    # warnings on otherwise clean unit vectors. Verified against a float64 einsum over the
    # live 351-item index: results agree to 3.5e-08 and pick the same argmax. Silenced here
    # rather than left to fill the log, which only teaches people to ignore warnings.
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        sims_all = have_mat @ unit[need].T

    for column, i in enumerate(need):
        sims = sims_all[:, column]
        best = int(np.argmax(sims))
        score = float(sims[best])
        if score < CROSSFILL_SUGGEST:
            continue
        source_item = items[have[best]]
        items[i]["image_ref"] = source_item["image_ref"]
        prefix = "matched" if score >= CROSSFILL_AUTO else "suggested"
        items[i]["image_source"] = f"{prefix} from {source_item.get('file_name', 'another quote')}"
        filled += 1
    return filled


class QuotationApi:
    def __init__(self):
        self.model = None
        self.client = chromadb.PersistentClient(path=DB_PATH)
        self.collection = self.client.get_or_create_collection(name=COLLECTION_NAME)
        # Separate collection from historical pricing data: a small, PM-curated bank of real
        # product photos, keyed by description via the same semantic search as item matching.
        # Grows organically as PMs save photos while quoting, instead of needing a bulk upload.
        self.photo_collection = self.client.get_or_create_collection(name=PHOTO_COLLECTION_NAME)
        self.sync_path = SYNC_CONFIG["default_path"]
        self._catalog_cache = None

    def _get_model(self):
        """Lazy loads the embedding model to save initial window boot time."""
        if self.model is None:
            self.model = get_embedder()
        return self.model

    # --- Status / analytics -------------------------------------------------

    def get_company_info(self):
        try:
            return {"success": True, "company": doc_generator.COMPANY}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_db_status(self):
        try:
            count = self.collection.count()
            return {"status": "ready", "count": count}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_analytics(self):
        try:
            count = self.collection.count()
            if count == 0:
                return {
                    "total_items": 0, "avg_price": "0.00", "min_price": "0.00",
                    "max_price": "0.00", "year_min": 2026, "year_max": 2026, "venues": 0,
                    "needs_review": 0
                }

            all_meta = self.collection.get(include=["metadatas"])
            rates, years, venues = [], [], set()
            needs_review_count = 0

            if all_meta and all_meta.get("metadatas"):
                for m in all_meta["metadatas"]:
                    r = float(m.get("historical_rate", 0.0))
                    if r > 0:
                        rates.append(r)
                    dt = m.get("quote_date", "")
                    if dt:
                        try:
                            years.append(int(dt.split("-")[0]))
                        except ValueError:
                            pass
                    venue = m.get("venue", "")
                    if venue and venue != "Venue Unspecified":
                        venues.add(venue)
                    # Evaluated live from the same helper the review queue uses, so the
                    # dashboard number can never drift from the actual worklist length.
                    flagged, _ = parsing.evaluate_review_flags(m)
                    if flagged:
                        needs_review_count += 1

            avg_price = sum(rates) / len(rates) if rates else 0.0
            return {
                "total_items": count,
                "avg_price": f"{avg_price:,.2f}",
                "min_price": f"{(min(rates) if rates else 0.0):,.2f}",
                "max_price": f"{(max(rates) if rates else 0.0):,.2f}",
                "year_min": min(years) if years else 2024,
                "year_max": max(years) if years else 2026,
                "venues": len(venues),
                "needs_review": needs_review_count,
            }
        except Exception as e:
            print(f"Error computing database analytics: {e}")
            return {
                "total_items": 0, "avg_price": "0.00", "min_price": "0.00",
                "max_price": "0.00", "year_min": 2024, "year_max": 2026, "venues": 0,
                "needs_review": 0
            }

    # --- Indexing / search ----------------------------------------------------

    def _write_staging(self, ids, embeddings, metadatas, documents, batch_size=500):
        """Loads a freshly parsed index into a scratch collection, leaving the live one alone.

        Batched because Chroma materializes the whole call in memory, and a large archive can
        run to several thousand items.
        """
        try:
            self.client.delete_collection(name=STAGING_COLLECTION_NAME)
        except Exception:
            pass  # No staging collection left over from a previous run — the normal case.

        staging = self.client.get_or_create_collection(name=STAGING_COLLECTION_NAME)
        for start in range(0, len(ids), batch_size):
            stop = start + batch_size
            staging.add(
                ids=ids[start:stop],
                embeddings=embeddings[start:stop],
                metadatas=metadatas[start:stop],
                documents=documents[start:stop],
            )
        return staging

    def _promote_staging(self, expected):
        """Swaps the staged index in for the live one, once it is known to be complete.

        The count check is the whole point: promoting is the only destructive step, and it
        only happens after the replacement has been verified to hold every item. A failure
        anywhere earlier leaves the previous index serving queries untouched.
        """
        staging = self.client.get_or_create_collection(name=STAGING_COLLECTION_NAME)
        actual = staging.count()
        if actual != expected:
            raise RuntimeError(
                f"Refusing to promote a partial index: staged {actual} of {expected} items. "
                f"The existing index has been left in place."
            )

        db.backup(history_db.DB_FILE, tag="preindex")
        try:
            self.client.delete_collection(name=COLLECTION_NAME)
        except Exception:
            pass
        # Chroma has no rename, so the staged data is copied across in one pass and the
        # scratch collection dropped. Reads go through `self.collection`, which is only
        # repointed once the new collection is fully populated.
        staged = staging.get(include=["metadatas", "documents", "embeddings"])
        fresh = self.client.get_or_create_collection(name=COLLECTION_NAME)
        ids = staged["ids"]
        for start in range(0, len(ids), 500):
            stop = start + 500
            fresh.add(
                ids=ids[start:stop],
                embeddings=[list(e) for e in staged["embeddings"][start:stop]],
                metadatas=staged["metadatas"][start:stop],
                documents=staged["documents"][start:stop],
            )
        self.collection = fresh
        try:
            self.client.delete_collection(name=STAGING_COLLECTION_NAME)
        except Exception:
            pass
        log.info("Promoted new index: %s items", actual)
        return actual

    def index_files(self, path):
        path_obj = Path(path)
        if not path_obj.exists() or not path_obj.is_dir():
            return {"success": False, "error": f"Path '{path}' does not exist or is not a directory."}

        self.sync_path = str(path_obj)
        print(f"Recursively scanning target path: {self.sync_path}")

        try:
            # Index every spreadsheet/document in the target folder rather than filtering on
            # filename keywords. The old keyword gate ("quotation", "cost sheet", ...) silently
            # skipped 12 real pricing files in the live archive — including the two largest
            # image sources ("Maple Bear Equipment List", "Q01183 Cost To Build") — so hundreds
            # of embedded product photos never reached the app. The folder is the filter.
            excluded = {name.lower() for name in SYNC_CONFIG.get("exclude_folders", [])}
            excel_files, pdf_files, word_files = [], [], []
            skipped_folders = set()
            skipped_count = 0
            self_generated = 0
            for file in path_obj.rglob("*"):
                if file.name.startswith("~$") or not file.is_file():
                    continue
                suffix = file.suffix.lower()
                if suffix not in (".xlsx", ".pdf", ".docx"):
                    continue
                # Only directory names are matched, never the file name itself.
                parents = file.relative_to(path_obj).parts[:-1]
                hit = next((p for p in parents if p.lower() in excluded), None)
                if hit:
                    skipped_folders.add(hit)
                    skipped_count += 1
                    continue
                # Quotations this app produced are output, not source pricing. Re-reading them
                # fed already-marked-up rates back into the library (the same Pirate Ship
                # appeared at 29,120 / 35,200 / 42,592 as markup compounded on each pass) and
                # scraped their header labels and totals in as products.
                if SELF_GENERATED_RE.search(file.name):
                    self_generated += 1
                    continue
                if suffix == ".xlsx":
                    excel_files.append(file)
                elif suffix == ".pdf":
                    pdf_files.append(file)
                else:
                    word_files.append(file)

            all_items = []
            for file_path in excel_files:
                all_items.extend(parsing.parse_excel_file(file_path))
            for file_path in pdf_files:
                all_items.extend(parsing.parse_pdf_file(file_path))
            for file_path in word_files:
                all_items.extend(parsing.parse_docx_file(file_path))

            seen, unique_items = set(), []
            for item in all_items:
                key = (item['original_description'].lower().strip(), item['historical_rate'])
                if key not in seen:
                    seen.add(key)
                    unique_items.append(item)

            # Re-apply prior PM corrections, but only the fields the PM actually edited.
            # Snapshotting all three fields is what used to freeze an item's price the moment
            # anyone set its venue in bulk or dismissed its review flag — after which a price
            # change in the source spreadsheet could never reach the app again.
            all_corrections = corrections_db.get_all_corrections()
            reapplied = 0
            for item in unique_items:
                key = (str(item['file_name']).strip(), item['original_description'].strip().lower())
                fix = all_corrections.get(key)
                if fix:
                    corrections_db.apply_correction(item, fix)
                    reapplied += 1

            if not unique_items:
                return {
                    "success": True, "indexed_count": 0,
                    "message": "Indexing complete: 0 unique historical items found (blank/invalid rows filtered)."
                }

            descriptions = [item['original_description'] for item in unique_items]
            model = self._get_model()
            computed_embeddings = model.encode(descriptions, show_progress_bar=False)

            # Borrow photos for items that have none from their nearest photographed twin,
            # so the same product quoted text-only in one file still shows its picture.
            crossfilled = crossfill_images(unique_items, computed_embeddings)

            ids, documents, embeddings, metadatas = [], [], [], []
            used_ids = set()
            for idx, item in enumerate(unique_items):
                item_id = _item_id(item)
                # Content-hash collisions mean two rows really are the same item; keep the
                # first and let the suffix disambiguate rather than silently dropping one.
                if item_id in used_ids:
                    item_id = f"{item_id}_{idx}"
                used_ids.add(item_id)

                ids.append(item_id)
                documents.append(item['original_description'])
                embeddings.append(computed_embeddings[idx].tolist())
                metadatas.append({
                    'original_description': item['original_description'],
                    'historical_rate': float(item['historical_rate']),
                    'unit': str(item['unit']),
                    'quote_date': str(item['quote_date']),
                    'venue': str(item.get('venue', 'Venue Unspecified')),
                    'file_name': str(item['file_name']),
                    # A 64-character hash into the image store, never image bytes. Chroma keeps
                    # a B-tree index over metadata string values, so a blob here costs three
                    # copies on disk and is loaded into memory by every unprojected read.
                    'image_ref': str(item.get('image_ref') or ''),
                    'image_source': str(item.get('image_source', '')),
                    'rate_confidence': str(item.get('rate_confidence', 'medium')),
                    'venue_confidence': str(item.get('venue_confidence', 'medium')),
                    'needs_review': bool(item.get('needs_review', False)),
                    'flag_reason': str(item.get('flag_reason', '')),
                })

            # Build into staging, verify, then swap. The previous order deleted the live
            # collection *before* loading the model and computing embeddings, so any failure
            # in between — an OOM on a large archive, a missing model, the window being closed
            # — left the business with an empty price library and no backup.
            self._write_staging(ids, embeddings, metadatas, documents)
            self._promote_staging(expected=len(ids))

            own = sum(1 for it in unique_items if it.get('image_ref') and not str(it.get('image_source', '')).startswith(('matched', 'suggested')))
            message = (f"Indexing complete: {len(unique_items)} items indexed "
                       f"({own} with their own photo, {crossfilled} matched from other quotes).")
            # Anything not scanned is stated outright. Silently skipping files is exactly how
            # the old filename filter lost 12 pricing documents without anyone noticing.
            if skipped_count:
                message += (f" Skipped {skipped_count} file(s) in excluded folder(s): "
                            f"{', '.join(sorted(skipped_folders))} — edit sync_config.json to change this.")
            if self_generated:
                message += (f" Ignored {self_generated} quotation(s) this app generated itself, "
                            f"so their marked-up prices don't re-enter the price library.")
            return {
                "success": True,
                "indexed_count": len(unique_items),
                "skipped_count": skipped_count,
                "skipped_folders": sorted(skipped_folders),
                "message": message,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def search_items(self, query, markup_rate=0.04):
        try:
            count = self.collection.count()
            if count == 0:
                return {"success": True, "matches": []}

            model = self._get_model()
            query_embedding = model.encode(query).tolist()
            results = self.collection.query(query_embeddings=[query_embedding], n_results=5)

            matches = []
            if results and results['ids'] and results['ids'][0]:
                ids = results['ids'][0]
                distances = results['distances'][0]
                metadatas = results['metadatas'][0]
                current_year = datetime.now().year
                markup_rate_val = float(markup_rate)

                for idx in range(len(ids)):
                    metadata = metadatas[idx]
                    distance = distances[idx]
                    similarity_pct = _distance_to_similarity(distance)

                    rate = float(metadata.get('historical_rate', 0.0))
                    quote_date = metadata.get('quote_date', '')

                    elapsed_years = _elapsed_years(quote_date)
                    adjusted_rate = rate * ((1.0 + markup_rate_val) ** elapsed_years)

                    matches.append({
                        'id': ids[idx],
                        'description': metadata.get('original_description', ''),
                        'original_rate': round(rate, 2),
                        'adjusted_rate': round(adjusted_rate, 2),
                        'unit': metadata.get('unit', 'Pcs'),
                        'quote_date': quote_date,
                        'venue': metadata.get('venue', 'Venue Unspecified'),
                        'elapsed_years': elapsed_years,
                        'similarity': similarity_pct,
                        'file_name': metadata.get('file_name', ''),
                        # The ref identifies the photo; the src is what the <img> tag loads.
                        # Sending base64 here meant every keystroke in the search box pushed
                        # roughly 800 KB of image data across the pywebview bridge.
                        'image_ref': metadata.get('image_ref', ''),
                        'image_src': image_store.web_src(metadata.get('image_ref', '')),
                        'image_source': metadata.get('image_source', ''),
                    })

            return {"success": True, "matches": matches}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # --- Review queue (low-confidence extractions) -----------------------------

    def get_review_queue(self, limit=300):
        """Returns indexed items flagged during parsing as low-confidence rate and/or venue,
        so a PM can spot-check and correct them instead of bad data silently sitting in the index."""
        try:
            count = self.collection.count()
            if count == 0:
                return {"success": True, "items": []}

            all_data = self.collection.get(include=["metadatas"])
            flagged = []
            if all_data and all_data.get("metadatas"):
                for item_id, m in zip(all_data["ids"], all_data["metadatas"]):
                    needs_review, reasons = parsing.evaluate_review_flags(m)
                    if not needs_review:
                        continue
                    flagged.append({
                        'id': item_id,
                        'description': m.get('original_description', ''),
                        'rate': m.get('historical_rate', 0.0),
                        'unit': m.get('unit', 'Pcs'),
                        'venue': m.get('venue', 'Venue Unspecified'),
                        'quote_date': m.get('quote_date', ''),
                        'file_name': m.get('file_name', ''),
                        'rate_confidence': m.get('rate_confidence', 'low'),
                        'venue_confidence': m.get('venue_confidence', 'low'),
                        'flag_reason': '; '.join(reasons),
                        'reasons': reasons,
                    })

            # Worst data gaps first: a missing price blocks quoting outright, an unverified
            # venue is only a labelling problem.
            def severity(entry):
                r = entry['reasons']
                if any('missing unit rate' in x for x in r):
                    return 0
                if any('missing description' in x for x in r):
                    return 1
                if any('reconcile' in x for x in r):
                    return 2
                return 3

            flagged.sort(key=severity)
            return {"success": True, "items": flagged[:limit]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def save_correction(self, item_id, rate=None, unit=None, venue=None):
        """Applies a PM correction to a single indexed item: updates it live in ChromaDB and
        persists it in corrections.db so the fix survives the next folder re-sync."""
        try:
            existing = self.collection.get(ids=[item_id], include=["metadatas"])
            if not existing or not existing.get("metadatas") or not existing["metadatas"]:
                return {"success": False, "error": "Item not found in index."}

            meta = dict(existing["metadatas"][0])
            # Only the fields the PM actually filled in are recorded as corrections. The rest
            # keep re-parsing from source on every sync, which is what lets a price update in
            # the original spreadsheet still reach the app.
            edited = []
            if rate is not None and str(rate).strip() != "":
                meta["historical_rate"] = float(rate)
                meta["rate_confidence"] = "high"
                edited.append("rate")
            if unit:
                meta["unit"] = str(unit)
                edited.append("unit")
            if venue:
                meta["venue"] = str(venue)
                meta["venue_confidence"] = "high"
                edited.append("venue")

            meta["needs_review"] = False
            meta["flag_reason"] = (
                "corrected by PM: " + ", ".join(edited) if edited else "reviewed by PM - left as-is"
            )

            self.collection.update(ids=[item_id], metadatas=[meta])

            corrections_db.save_correction(
                file_name=meta.get("file_name", ""),
                original_description=meta.get("original_description", ""),
                rate=meta.get("historical_rate"),
                unit=meta.get("unit"),
                venue=meta.get("venue"),
                corrected_fields=edited,
            )

            return {"success": True, "corrected_fields": edited}
        except Exception as e:
            return logging_setup.report("Saving the correction", e)

    def bulk_set_venue_for_file(self, file_name, venue):
        """Applies one venue to every indexed item from a given source file.

        Venue is a property of the job/file, not of individual line items, so correcting it
        item-by-item would mean re-typing the same value dozens of times for one document.
        """
        try:
            venue = (venue or "").strip()
            if not venue:
                return {"success": False, "error": "Venue cannot be empty."}

            all_data = self.collection.get(include=["metadatas"])
            if not all_data or not all_data.get("metadatas"):
                return {"success": False, "error": "Index is empty."}

            ids_to_update, metas_to_update = [], []
            for item_id, m in zip(all_data["ids"], all_data["metadatas"]):
                if str(m.get("file_name", "")) != str(file_name):
                    continue
                meta = dict(m)
                meta["venue"] = venue
                meta["venue_confidence"] = "high"
                meta["needs_review"] = False
                meta["flag_reason"] = "corrected by PM"
                ids_to_update.append(item_id)
                metas_to_update.append(meta)

            if not ids_to_update:
                return {"success": False, "error": "No indexed items found for that file."}

            self.collection.update(ids=ids_to_update, metadatas=metas_to_update)

            for meta in metas_to_update:
                # Venue only. This call used to persist the rate alongside it, which pinned
                # the price of every line in the file to whatever had been parsed that day —
                # a venue correction silently froze the whole document's pricing.
                corrections_db.save_correction(
                    file_name=meta.get("file_name", ""),
                    original_description=meta.get("original_description", ""),
                    venue=venue,
                    corrected_fields=["venue"],
                )

            return {"success": True, "updated": len(ids_to_update)}
        except Exception as e:
            return logging_setup.report("Setting the venue for this file", e)

    def dismiss_review_item(self, item_id):
        """Lighter-weight than save_correction: clears the review flag on an item the PM has
        looked at and is fine leaving as-is, without forcing them to re-type every field.
        Still persisted so the item doesn't get re-flagged on the next re-sync."""
        try:
            existing = self.collection.get(ids=[item_id], include=["metadatas"])
            if not existing or not existing.get("metadatas") or not existing["metadatas"]:
                return {"success": False, "error": "Item not found in index."}

            meta = dict(existing["metadatas"][0])
            meta["needs_review"] = False
            meta["flag_reason"] = "dismissed by PM - left as-is"
            self.collection.update(ids=[item_id], metadatas=[meta])

            # An empty field list is the point: this records "a human looked and left it
            # alone", so the item stops being re-flagged without any of its parsed values
            # being pinned. Previously a dismissal snapshotted all three fields, which froze
            # the item's rate — including freezing a rate of 0 on genuinely broken rows.
            corrections_db.save_correction(
                file_name=meta.get("file_name", ""),
                original_description=meta.get("original_description", ""),
                rate=meta.get("historical_rate"),
                unit=meta.get("unit"),
                venue=meta.get("venue"),
                corrected_fields=[],
            )
            return {"success": True}
        except Exception as e:
            return logging_setup.report("Dismissing this review item", e)

    # --- Quotation generation -------------------------------------------------

    def compile_quotation(self, payload):
        try:
            items = payload.get("items", [])
            if not items:
                return {"success": False, "error": "No items in draft."}

            client_name = (payload.get("client_name") or "Client").strip()
            safe_client = re.sub(r'[\\/*?:"<>|]', "", client_name) or "Client"
            client_phone = payload.get("client_phone", "")
            venue = payload.get("venue", "")
            discount_type = payload.get("discount_type")
            discount_value = payload.get("discount_value", 0)
            formats = payload.get("formats") or ["xlsx"]
            quote_date = datetime.now().strftime("%Y-%m-%d")
            validity_days = payload.get("validity_days")
            valid_until = doc_generator.compute_valid_until(quote_date, validity_days)

            # Allocated from a counter that only moves forward, so the reference printed on
            # the document is owned by this quote before any file is written. The old scheme
            # read MAX(id)+1, which meant deleting the most recent quote made the next one
            # reuse its number — two different documents both labelled Q-7 in a client's
            # inbox. A gap in the sequence is invisible to clients; a collision is not.
            quote_ref = history_db.allocate_quote_number()

            meta = {
                "client_name": client_name, "venue": venue, "quote_date": quote_date,
                "discount_type": discount_type, "discount_value": discount_value,
                "valid_until": valid_until, "quote_ref": quote_ref,
            }

            sync_path_obj = Path(self.sync_path)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            base_filename = f"{safe_client}_Quotation_{timestamp}"

            def resolve_output_path(ext):
                try:
                    out_path = sync_path_obj / f"{base_filename}.{ext}"
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    # Binary mode: this only proves the folder is writable and never writes
                    # a byte, so it has no business picking a text encoding to do it.
                    with open(str(out_path), "wb"):
                        pass
                    os.remove(str(out_path))
                    return out_path
                except Exception:
                    return Path(f"{base_filename}.{ext}")

            xlsx_path, docx_path, totals = None, None, None
            # Reset before generating so the count reflects only this compile.
            doc_generator.IMAGE_FAILURES.clear()

            if "xlsx" in formats:
                company_name = doc_generator.COMPANY.get("name", "Company")
                template_path = sync_path_obj / f"{company_name.title()} - Quotation Format.xlsx"
                if not template_path.exists():
                    template_path = Path("template.xlsx")
                    if not template_path.exists():
                        doc_generator.create_fallback_template(str(template_path))
                xlsx_path = resolve_output_path("xlsx")
                totals = doc_generator.generate_excel_dynamic(items, meta, template_path, xlsx_path)

            if "docx" in formats:
                docx_path = resolve_output_path("docx")
                totals = doc_generator.generate_word_dynamic(items, meta, docx_path)

            if totals is None:
                totals = doc_generator.compute_totals(items, discount_type, discount_value)

            pdf_path = None
            pdf_source = xlsx_path or docx_path
            pdf_result = {"success": False}
            if pdf_source:
                pdf_result = pdf_export.convert_to_pdf(str(pdf_source))
            if pdf_result.get("success"):
                pdf_path = pdf_result["pdf_path"]
                pdf_export.open_file(pdf_path)
            elif pdf_source:
                pdf_export.open_file(str(pdf_source))

            # Cost is looked up for the history record only, never handed to doc_generator —
            # it must never appear on a document the client receives.
            items_with_cost = self._attach_costs(items)

            history_id = history_db.save_quotation_history({
                "client_name": client_name, "client_phone": client_phone, "venue": venue,
                "quote_date": quote_date, "items": items_with_cost,
                "discount_type": discount_type, "discount_value": discount_value,
                "subtotal": totals["subtotal"], "vat": totals["vat"], "grand_total": totals["grand_total"],
                "xlsx_path": str(xlsx_path.resolve()) if xlsx_path else "",
                "docx_path": str(docx_path.resolve()) if docx_path else "",
                "pdf_path": pdf_path or "",
                "valid_until": valid_until,
                "quote_number": quote_ref,
            })

            log.info("Compiled %s for %s (history id %s, total %.2f)",
                     quote_ref, client_name, history_id, totals["grand_total"])
            whatsapp_link = sharing.build_whatsapp_link(client_name, quote_ref, totals["grand_total"], items, client_phone)
            mailto_link = sharing.build_mailto_link(
                client_name, quote_ref, totals["grand_total"], items,
                pdf_path or (str(xlsx_path) if xlsx_path else None)
            )

            return {
                "success": True,
                "history_id": history_id,
                "quote_ref": quote_ref,
                "image_failures": len(doc_generator.IMAGE_FAILURES),
                "xlsx_path": str(xlsx_path.resolve()) if xlsx_path else "",
                "docx_path": str(docx_path.resolve()) if docx_path else "",
                "pdf_path": pdf_path or "",
                "pdf_available": bool(pdf_path),
                "pdf_error": "" if pdf_result.get("success") else pdf_result.get("error", ""),
                "totals": totals,
                "whatsapp_link": whatsapp_link,
                "mailto_link": mailto_link,
                "valid_until": valid_until,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # --- Catalog cost matching ----------------------------------------------------

    def _catalog_embeddings(self):
        """Embeddings for every catalog title, cached until the catalog changes.

        Keyed on the row ids and their update timestamps, so editing an item's description
        invalidates the cache without needing an explicit signal from the UI.
        """
        items = catalog_db.get_catalog_items()
        if not items:
            self._catalog_cache = None
            return None

        signature = tuple((it["id"], it.get("updated_at")) for it in items)
        if self._catalog_cache and self._catalog_cache["signature"] == signature:
            return self._catalog_cache

        titles = [catalog_db.title_line(it["description"]) or it["description"] for it in items]
        vectors = np.asarray(self._get_model().encode(titles), dtype=np.float32)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        self._catalog_cache = {
            "signature": signature,
            "items": items,
            "unit": vectors / np.clip(norms, 1e-9, None),
        }
        return self._catalog_cache

    def _attach_costs(self, items):
        """Enriches draft line items with the cost_price behind each one, for margin reporting.

        Cost lookup used to be an exact string equality test against the catalog description.
        Quote lines are multi-line free text, so it essentially never matched and every quote
        recorded cost_price: None — margin reporting had no data at all. Deterministic
        matching (exact, title line, containment) runs first; anything still unmatched falls
        back to a semantic match against catalog titles, which is what handles the wording
        drift between a catalog entry and how it gets written on a quote.
        """
        enriched_items = []
        unresolved = []

        for idx, it in enumerate(items):
            enriched = dict(it)
            match = catalog_db.find_catalog_item_by_description(it.get("description", ""))
            if match:
                enriched["cost_price"] = match["cost_price"]
                enriched["cost_source"] = match["match"]
            else:
                enriched["cost_price"] = None
                enriched["cost_source"] = ""
                unresolved.append(idx)
            enriched_items.append(enriched)

        if unresolved:
            try:
                cache = self._catalog_embeddings()
            except Exception as e:
                log.warning("Semantic cost matching unavailable: %s", e)
                cache = None

            if cache:
                queries = [
                    catalog_db.title_line(enriched_items[i].get("description", ""))
                    or enriched_items[i].get("description", "")
                    for i in unresolved
                ]
                vectors = np.asarray(self._get_model().encode(queries), dtype=np.float32)
                if vectors.ndim == 1:
                    vectors = vectors[None, :]
                norms = np.linalg.norm(vectors, axis=1, keepdims=True)
                unit = vectors / np.clip(norms, 1e-9, None)

                # See crossfill_images for why the FP warnings are silenced.
                with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
                    all_sims = cache["unit"] @ unit.T

                for slot, item_idx in enumerate(unresolved):
                    sims = all_sims[:, slot]
                    best = int(np.argmax(sims))
                    if float(sims[best]) >= COST_MATCH_MIN:
                        row = cache["items"][best]
                        enriched_items[item_idx]["cost_price"] = row["cost_price"]
                        enriched_items[item_idx]["cost_source"] = f"semantic {float(sims[best]):.0%}"

        return enriched_items

    # --- Images ------------------------------------------------------------------

    def fetch_image_suggestions(self, query):
        return image_tools.fetch_image_suggestions(query)

    def fetch_image_from_url(self, url):
        return image_tools.fetch_image_from_url(url)

    def upload_image_dialog(self):
        try:
            window = webview.windows[0]
            result = window.create_file_dialog(
                webview.OPEN_DIALOG, file_types=('Image Files (*.jpg;*.jpeg;*.png;*.gif;*.bmp)',)
            )
            if not result:
                return {"success": False, "error": "No file selected."}
            return image_tools.import_local_file(result[0])
        except Exception as e:
            return logging_setup.report("Importing that image", e)

    # --- Photo library -----------------------------------------------------------
    # A small, growing bank of real product photos separate from historical pricing data.
    # Instead of requiring a bulk photo-shoot project up front, any image a PM sets on a
    # draft item can be saved here with one click; future items with a similar description
    # then surface it automatically via the same semantic matching used for price search.

    def save_photo_to_library(self, description, image_value):
        """Saves a photo under a description. `image_value` may be a ref or a data URI —
        the frontend passes whichever it holds and `ingest` normalizes both to a ref."""
        try:
            description = (description or "").strip()
            if not description or not image_value:
                return {"success": False, "error": "Need both a description and an image to save."}

            image_ref = image_store.ingest(image_value)
            if not image_ref:
                return {"success": False, "error": "That image could not be read."}

            model = self._get_model()
            embedding = np.asarray(model.encode(description), dtype=np.float32).tolist()
            # The photo's own hash is its id, so saving the same picture twice updates one
            # entry rather than filling the library with duplicates.
            photo_id = f"photo_{image_ref[:32]}"

            self.photo_collection.upsert(
                ids=[photo_id],
                embeddings=[embedding],
                documents=[description],
                metadatas=[{
                    "description": description,
                    "image_ref": image_ref,
                    "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }],
            )
            return {"success": True, "id": photo_id, "image_ref": image_ref,
                    "image_src": image_store.web_src(image_ref)}
        except Exception as e:
            return logging_setup.report("Saving that photo to the library", e)

    def search_photo_library(self, query, n_results=6):
        try:
            count = self.photo_collection.count()
            if count == 0 or not (query or "").strip():
                return {"success": True, "matches": []}

            model = self._get_model()
            query_embedding = model.encode(query).tolist()
            results = self.photo_collection.query(
                query_embeddings=[query_embedding], n_results=min(n_results, count)
            )

            matches = []
            if results and results.get("ids") and results["ids"][0]:
                for idx, photo_id in enumerate(results["ids"][0]):
                    metadata = results["metadatas"][0][idx]
                    distance = results["distances"][0][idx]
                    ref = metadata.get("image_ref", "") or metadata.get("image_base64", "")
                    matches.append({
                        "id": photo_id,
                        "description": metadata.get("description", ""),
                        "image_ref": ref if image_store.is_ref(ref) else "",
                        "image_src": image_store.web_src(ref),
                        "similarity": _distance_to_similarity(distance),
                    })
            return {"success": True, "matches": matches}
        except Exception as e:
            return logging_setup.report("Searching the photo library", e)

    def delete_photo_from_library(self, photo_id):
        try:
            self.photo_collection.delete(ids=[photo_id])
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_photo_library_count(self):
        try:
            return {"success": True, "count": self.photo_collection.count()}
        except Exception as e:
            return {"success": False, "error": str(e), "count": 0}

    # --- Automated Design Estimator ----------------------------------------------
    # Drawings in, priced BOQ out. The split is deliberate: design_parser only reports
    # what a drawing says, calculators owns every number, and this class is a thin
    # transport layer between them and the UI. Nothing here does arithmetic on a price.

    def get_estimator_options(self):
        """Dropdown options, rate-card constants and OCR availability for the estimator tab."""
        try:
            card = rate_card.get_rate_card()
            payload = calculators.options_payload(card)
            payload["ocr"] = design_parser.ocr_status()
            payload["rate_card"] = {
                "source": card.source_path.name,
                "item_count": len(card.items),
                "categories": card.categories(),
            }
            return {"success": True, "options": payload}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def pick_design_files(self):
        """Native multi-select dialog for drawing files.

        pywebview's drag-and-drop cannot hand back a filesystem path on Windows, so the
        drop zone in the UI routes here — the PM still gets one click to a multi-select.
        """
        try:
            window = webview.windows[0]
            result = window.create_file_dialog(
                webview.OPEN_DIALOG,
                allow_multiple=True,
                file_types=(
                    'Drawings (*.pdf;*.png;*.jpg;*.jpeg;*.bmp;*.webp)',
                    'PDF Drawings (*.pdf)',
                    'Images (*.png;*.jpg;*.jpeg;*.bmp;*.webp)',
                ),
            )
            if not result:
                return {"success": False, "error": "No files selected."}
            return {"success": True, "paths": list(result)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def parse_design_files(self, paths):
        """Parses selected drawings into per-page detected specs plus preview images."""
        try:
            if not paths:
                return {"success": False, "error": "No files to parse."}
            return design_parser.parse_files(list(paths))
        except Exception as e:
            return {"success": False, "error": str(e)}

    def compute_design_estimate(self, payload):
        """Recomputes every page's BOQ and the cumulative master summary.

        Called on load and again on every manual override, so the numbers on screen are
        always the result of the current dimensions rather than a cached first pass.
        """
        try:
            specs = (payload or {}).get("specs") or []
            if not specs:
                return {"success": False, "error": "No items to cost."}

            card = rate_card.get_rate_card()
            margin_pct = (payload or {}).get("margin_pct")

            items, errors = [], []
            for index, spec in enumerate(specs):
                label = spec.get("label") or f"Item {index + 1}"
                try:
                    boq = calculators.compute_item_boq(spec, card)
                    boq["spec_index"] = index
                    items.append(boq)
                except rate_card.MissingRateError as exc:
                    # A missing code is a data problem the PM can fix from the UI right here —
                    # naming the item and the code beats failing the whole batch with a bare
                    # KeyError, and lets the frontend offer a one-click "add this material".
                    errors.append({
                        "index": index, "label": label,
                        "code": getattr(exc, "code", None), "message": str(exc),
                    })
                except Exception as exc:
                    errors.append({"index": index, "label": label, "code": None, "message": str(exc)})

            if not items:
                joined = "; ".join(e["message"] for e in errors)
                return {"success": False, "error": joined or "Nothing could be costed."}

            summary = calculators.aggregate(items, margin_pct, card)
            return {"success": True, "items": items, "summary": summary, "errors": errors}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def add_rate_card_item(self, payload):
        """Adds a new material row to the master rate card CSV from the estimator UI.

        Called when a BOQ line references a code the card doesn't have — the PM names,
        categorizes and prices it here instead of leaving the item permanently unpriced
        or hand-editing the CSV outside the app.
        """
        try:
            payload = payload or {}
            card = rate_card.add_rate_card_item(
                code=payload.get("code"),
                description=payload.get("description"),
                unit=payload.get("unit") or "Unit",
                avg_cost=payload.get("avg_cost"),
                category=payload.get("category") or "Uncategorized",
                usage=payload.get("usage") or "",
            )
            options = calculators.options_payload(card)
            options["ocr"] = design_parser.ocr_status()
            options["rate_card"] = {
                "source": card.source_path.name,
                "item_count": len(card.items),
                "categories": card.categories(),
            }
            return {"success": True, "options": options}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def merge_designs_to_proposal(self, payload):
        """Turns the estimate into quotation line items, and optionally a factory BOQ sheet.

        Client lines are handed back for the Compiler draft rather than compiled here, so
        the existing quotation path — pricing, discount, VAT, Word/Excel, PDF, history —
        stays the single way a document gets made. The factory sheet is a separate
        artefact at factory cost, which must never reach the client.
        """
        try:
            specs = (payload or {}).get("specs") or []
            if not specs:
                return {"success": False, "error": "No items to merge."}

            card = rate_card.get_rate_card()
            margin_pct = (payload or {}).get("margin_pct")

            items, blocked = [], []
            for index, spec in enumerate(specs):
                label = spec.get("label") or f"Item {index + 1}"
                try:
                    boq = calculators.compute_item_boq(spec, card)
                except rate_card.MissingRateError as exc:
                    blocked.append(f"{label}: {exc}")
                    continue
                if boq["needs_dimensions"]:
                    blocked.append(f"{label}: {boq['dimension_message']}")
                    continue
                items.append(boq)

            if blocked:
                # A zero-cost line on the client quotation reads as a free item, which is
                # the one failure mode worse than making the PM go back and fix it first.
                return {"success": False, "error": "Fix before merging — " + "; ".join(blocked)}
            if not items:
                return {"success": False, "error": "No priced items to merge."}

            summary = calculators.aggregate(items, margin_pct, card)

            client_rows = calculators.to_quotation_items(items, summary, mode="client")

            factory_path = ""
            if (payload or {}).get("include_factory_sheet"):
                factory_rows = calculators.to_quotation_items(items, summary, mode="factory")
                factory_path = self._write_factory_boq(factory_rows, summary, payload)

            return {
                "success": True,
                "client_items": client_rows,
                "summary": summary,
                "factory_sheet": factory_path,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _write_factory_boq(self, factory_rows, summary, payload):
        """Writes the production take-off to its own workbook, reusing the Excel generator."""
        client_name = ((payload or {}).get("client_name") or "Client").strip()
        safe_client = re.sub(r'[\\/*?:"<>|]', "", client_name) or "Client"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")

        sync_path_obj = Path(self.sync_path)
        try:
            sync_path_obj.mkdir(parents=True, exist_ok=True)
            out_path = sync_path_obj / f"{safe_client}_FactoryBOQ_{timestamp}.xlsx"
        except Exception:
            out_path = Path(f"{safe_client}_FactoryBOQ_{timestamp}.xlsx")

        template_path = Path("template.xlsx")
        if not template_path.exists():
            doc_generator.create_fallback_template(str(template_path))

        meta = {
            "client_name": f"{client_name} - FACTORY PRODUCTION BOQ",
            "venue": (payload or {}).get("venue", ""),
            "quote_date": datetime.now().strftime("%Y-%m-%d"),
            "discount_type": None,
            "discount_value": 0,
            "valid_until": "",
            "quote_ref": f"BOQ-{timestamp}",
        }
        doc_generator.generate_excel_dynamic(factory_rows, meta, template_path, out_path)
        return str(out_path.resolve())

    # --- Sharing ----------------------------------------------------------------

    def open_external_link(self, url):
        try:
            webbrowser.open(url)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_path(self, path):
        return pdf_export.open_file(path)

    def open_source_file(self, file_name):
        """Opens the original quote file a flagged item came from, so a PM can see the row
        in context before deciding what the rate should be.

        The index only stores the basename (parsing records `path_obj.name`), so the file is
        located by searching the sync folder rather than trusted from the caller — and the
        resolved hit is checked to be inside that folder, so a crafted name cannot walk out
        of it and open something arbitrary.
        """
        try:
            name = (file_name or "").strip()
            if not name:
                return {"success": False, "error": "No file recorded for this item."}

            root = Path(self.sync_path).resolve()
            if not root.exists():
                return {"success": False, "error": f"Sync folder not found: {root}"}

            match = next((p for p in root.rglob(Path(name).name) if p.is_file()), None)
            if match is None:
                return {"success": False, "error": f'"{name}" is no longer in {root}.'}

            resolved = match.resolve()
            if root not in resolved.parents:
                return {"success": False, "error": "Refusing to open a file outside the sync folder."}

            return pdf_export.open_file(str(resolved))
        except Exception as e:
            return {"success": False, "error": str(e)}

    # --- History -----------------------------------------------------------------

    def get_history(self, limit=200):
        try:
            return {"success": True, "items": history_db.get_quotation_history(limit)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_history_item(self, history_id):
        try:
            item = history_db.get_quotation_by_id(history_id)
            if not item:
                return {"success": False, "error": "Quotation not found."}
            # Attach a renderable URL per line so reopening a quote shows its photos. Records
            # written before the image store hold an inline data URI, which web_src passes
            # through unchanged — so old quotes still render without a migration.
            for line in item.get("items", []):
                if isinstance(line, dict):
                    line["image_src"] = image_store.web_src(
                        line.get("image_ref") or line.get("image_base64") or ""
                    )
            return {"success": True, "item": item}
        except Exception as e:
            return logging_setup.report("Loading that quotation", e)

    def delete_history_item(self, history_id):
        try:
            history_db.delete_quotation_history(history_id)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def update_quotation_status(self, history_id, status):
        try:
            history_db.update_quotation_status(history_id, status)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def update_payment(self, history_id, payment_status, amount_paid):
        try:
            history_db.update_payment(history_id, payment_status, amount_paid)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_client_ledger(self, client_name, client_phone=None, client_id=None):
        try:
            return {"success": True,
                    "ledger": history_db.get_client_ledger(client_name, client_phone, client_id)}
        except Exception as e:
            return logging_setup.report("Loading the client ledger", e)

    # --- Clients -------------------------------------------------------------------

    def get_clients(self):
        try:
            return {"success": True, "clients": history_db.get_clients()}
        except Exception as e:
            return logging_setup.report("Loading clients", e)

    def update_client(self, client_id, name=None, phone=None, email=None, notes=None):
        try:
            history_db.update_client(client_id, name=name, phone=phone, email=email, notes=notes)
            return {"success": True}
        except Exception as e:
            return logging_setup.report("Updating the client", e)

    def merge_clients(self, source_id, target_id):
        """Folds one client record into another, moving their quotes across. This is the
        repair path for the same company having been typed two different ways."""
        try:
            moved = history_db.merge_clients(source_id, target_id)
            return {"success": True, "quotes_moved": moved}
        except Exception as e:
            return logging_setup.report("Merging those clients", e)

    def find_duplicate_clients(self):
        try:
            return {"success": True, "groups": history_db.find_duplicate_clients()}
        except Exception as e:
            return logging_setup.report("Looking for duplicate clients", e)

    # --- Corrections management ------------------------------------------------------

    def list_corrections(self, limit=500):
        """Every stored correction. Without a way to see these, a bad correction could only be
        undone by hand-editing SQLite — and it would keep re-applying on every sync."""
        try:
            return {"success": True, "items": corrections_db.list_corrections(limit)}
        except Exception as e:
            return logging_setup.report("Loading corrections", e)

    def delete_correction(self, file_name, original_description):
        try:
            removed = corrections_db.delete_correction(file_name, original_description)
            return {"success": True, "removed": removed}
        except Exception as e:
            return logging_setup.report("Deleting the correction", e)

    # --- Maintenance -----------------------------------------------------------------

    def get_storage_report(self):
        """What the app is using on disk, and how much of it is reclaimable."""
        try:
            chroma_bytes = maintenance.CHROMA_SQLITE.stat().st_size if maintenance.CHROMA_SQLITE.exists() else 0
            return {
                "success": True,
                "report": {
                    "images": image_store.stats(),
                    "chroma_bytes": chroma_bytes,
                    "databases": {
                        Path(p).name: (Path(p).stat().st_size if Path(p).exists() else 0)
                        for p in maintenance.DATABASES
                    },
                    "backups": len(db.list_backups()),
                },
            }
        except Exception as e:
            return logging_setup.report("Reading the storage report", e)

    def _live_image_refs(self):
        """Every image ref still cited by the index, the photo library, or a saved quotation."""
        refs = set(history_db.all_image_refs())
        for collection in (self.collection, self.photo_collection):
            try:
                data = collection.get(include=["metadatas"])
            except Exception:
                continue
            for meta in (data.get("metadatas") or []):
                ref = (meta or {}).get("image_ref")
                if ref:
                    refs.add(ref)
        return refs

    def run_maintenance(self, remove_orphans=False):
        """Backs up, purges Chroma's write log, vacuums, and optionally sweeps orphan photos."""
        try:
            summary = maintenance.run_all(
                live_refs=self._live_image_refs(), remove_orphans=bool(remove_orphans)
            )
            return {"success": True, "summary": summary}
        except Exception as e:
            return logging_setup.report("Running maintenance", e)

    def get_margin_summary(self, period_days=30):
        try:
            return {"success": True, "summary": history_db.get_margin_summary(period_days)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # --- Install health -----------------------------------------------------------

    def get_install_health(self):
        """What is missing on this machine, checked up front rather than mid-quotation.

        Each entry names the consequence and the fix, because "LibreOffice not found" on its
        own tells a PM nothing about why their client did not get a PDF.
        """
        try:
            import embedder

            checks = []
            if not pdf_export.pdf_available():
                checks.append({
                    "id": "pdf", "severity": "warning",
                    "title": "PDFs cannot be generated on this Mac",
                    "detail": "Quotations and invoices will open as Word documents instead.",
                    "fix": "Install LibreOffice: brew install --cask libreoffice",
                })
            if not embedder.onnx_available():
                checks.append({
                    "id": "model", "severity": "info",
                    "title": "Search model not downloaded yet",
                    "detail": "About 90 MB, fetched automatically the first time you search.",
                    "fix": "Run a search once while online.",
                })
            state = backup.status()
            if state["stale"]:
                checks.append({
                    "id": "backup", "severity": "warning",
                    "title": "No recent backup",
                    "detail": f"Last backup: {state['newest']['created'] if state['newest'] else 'never'}.",
                    "fix": "Run a backup from Settings.",
                })
            return {"success": True, "checks": checks, "healthy": not checks}
        except Exception as e:
            return logging_setup.report("Checking install health", e)

    # --- Support ------------------------------------------------------------------

    def export_diagnostics(self):
        """Writes a support bundle to the Desktop and opens it.

        This app runs on one laptop with no telemetry, by design — which also means a crash
        here is invisible to anyone who could fix it. Rather than send data off the machine,
        give the user one file they can choose to pass on.
        """
        try:
            result = logging_setup.collect_diagnostics()
            if result.get("success"):
                pdf_export.open_file(result["path"])
            return result
        except Exception as e:
            return logging_setup.report("Exporting diagnostics", e)

    # --- Backup ------------------------------------------------------------------
    # Everything the business remembers lives in a few files on one laptop. Local snapshots
    # die with the disk they are on, so this puts an encrypted copy in a synced folder.

    def get_backup_status(self):
        try:
            return {"success": True, "status": backup.status()}
        except Exception as e:
            return logging_setup.report("Reading backup status", e)

    def run_backup(self):
        """Writes a backup and verifies it by restoring into a temp directory.

        `passphrase` comes back non-null only the first time. The UI must show it and tell
        the user to save it elsewhere — a passphrase held only on this machine is worthless
        in the situation the backup exists for.
        """
        try:
            result = backup.create()
            if not result["verified"]:
                return {"success": False,
                        "error": "Backup was written but could not be read back. "
                                 "Do not rely on it. See logs for details.",
                        "result": result}
            return {"success": True, "result": result}
        except Exception as e:
            return logging_setup.report("Running the backup", e)

    def list_backups(self):
        try:
            return {"success": True, "backups": backup.list_backups()}
        except Exception as e:
            return logging_setup.report("Listing backups", e)

    def set_backup_destination(self, destination):
        try:
            return {"success": True, "config": backup.save_config(destination=destination)}
        except Exception as e:
            return logging_setup.report("Saving the backup destination", e)

    def restore_backup(self, archive_path):
        """Replaces live data with a backup. Takes a safety copy of what it overwrites first."""
        try:
            outcome = backup.restore(archive_path)
            log.warning("Data restored from %s", archive_path)
            return {"success": True, "outcome": outcome,
                    "message": "Restored. Close and reopen the app so it reloads the data."}
        except Exception as e:
            return logging_setup.report("Restoring that backup", e)

    # --- Invoices -----------------------------------------------------------------
    # Marking a quotation "Paid" with one amount could not express the company's own terms
    # (50% on confirmation, 50% before handover), say what is outstanding across all clients,
    # or produce a VAT figure. An invoice is its own record with a payment ledger against it.

    def get_invoices(self, status=None, limit=300):
        try:
            return {"success": True, "invoices": invoices_db.get_invoices(status, limit)}
        except Exception as e:
            return logging_setup.report("Loading invoices", e)

    def get_invoice(self, invoice_id):
        try:
            invoice = invoices_db.get_invoice(invoice_id)
            if not invoice:
                return {"success": False, "error": "Invoice not found."}
            return {"success": True, "invoice": invoice}
        except Exception as e:
            return logging_setup.report("Loading that invoice", e)

    def create_invoice_from_quotation(self, history_id, payment_terms_days=30):
        """Raises an invoice for a quotation, copying its lines and totals.

        Figures are copied rather than recomputed: the invoice must say what the client
        agreed to, not what the same items would price at today.
        """
        try:
            quote = history_db.get_quotation_by_id(history_id)
            if not quote:
                return {"success": False, "error": "Quotation not found."}

            existing = invoices_db.get_invoice_for_quotation(history_id)
            if existing:
                return {"success": False,
                        "error": f"Already invoiced as {existing['invoice_number']}.",
                        "invoice_id": existing["id"]}

            job = jobs_db.get_job_for_quotation(history_id)
            invoice_id = invoices_db.create_invoice(
                client_name=quote.get("client_name", ""),
                items=quote.get("items") or [],
                subtotal=quote.get("subtotal", 0),
                vat=quote.get("vat", 0),
                grand_total=quote.get("grand_total", 0),
                quotation_id=history_id,
                job_id=job["id"] if job else None,
                client_phone=quote.get("client_phone", ""),
                venue=quote.get("venue", ""),
                payment_terms_days=payment_terms_days,
            )
            log.info("Raised invoice for quotation %s", history_id)
            return {"success": True, "invoice_id": invoice_id}
        except ValueError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            return logging_setup.report("Raising the invoice", e)

    def update_invoice(self, invoice_id, **fields):
        try:
            invoices_db.update_invoice(invoice_id, **fields)
            return {"success": True}
        except Exception as e:
            return logging_setup.report("Updating the invoice", e)

    def delete_invoice(self, invoice_id):
        try:
            invoices_db.delete_invoice(invoice_id)
            return {"success": True}
        except Exception as e:
            return logging_setup.report("Deleting the invoice", e)

    def add_invoice_payment(self, invoice_id, amount, paid_date=None,
                            method="Bank Transfer", reference="", notes=""):
        try:
            payment_id = invoices_db.add_payment(
                invoice_id, amount, paid_date=paid_date, method=method,
                reference=reference, notes=notes,
            )
            return {"success": True, "payment_id": payment_id}
        except ValueError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            return logging_setup.report("Recording the payment", e)

    def delete_invoice_payment(self, payment_id):
        try:
            invoices_db.delete_payment(payment_id)
            return {"success": True}
        except Exception as e:
            return logging_setup.report("Removing the payment", e)

    def generate_invoice_document(self, invoice_id, formats=None):
        """Writes the invoice as a document the client can be sent."""
        try:
            invoice = invoices_db.get_invoice(invoice_id)
            if not invoice:
                return {"success": False, "error": "Invoice not found."}

            safe_client = re.sub(r'[\\/*?:"<>|]', "", invoice["client_name"]) or "Client"
            base = f"{safe_client}_Invoice_{invoice['invoice_number']}"
            out_dir = Path(self.sync_path)
            out_dir.mkdir(parents=True, exist_ok=True)

            meta = {
                "doc_kind": "INVOICE",
                "client_name": invoice["client_name"],
                "venue": invoice.get("venue", ""),
                "quote_date": invoice["issue_date"],
                "quote_ref": invoice["invoice_number"],
                "due_date": invoice.get("due_date", ""),
                "amount_paid": invoice["amount_paid"],
                "balance_due": invoice["balance"],
            }

            docx_path = out_dir / f"{base}.docx"
            doc_generator.generate_word_dynamic(invoice["items"], meta, docx_path)

            pdf_result = pdf_export.convert_to_pdf(str(docx_path))
            pdf_path = pdf_result.get("pdf_path") if pdf_result.get("success") else None
            invoices_db.update_invoice(
                invoice_id, docx_path=str(docx_path), pdf_path=pdf_path or "",
            )
            pdf_export.open_file(pdf_path or str(docx_path))
            return {"success": True, "docx_path": str(docx_path), "pdf_path": pdf_path or ""}
        except Exception as e:
            return logging_setup.report("Generating the invoice document", e)

    def get_client_statement(self, client_name):
        try:
            return {"success": True, "statement": invoices_db.client_statement(client_name)}
        except Exception as e:
            return logging_setup.report("Building the client statement", e)

    def get_aging_report(self):
        try:
            return {"success": True, "aging": invoices_db.aging_report()}
        except Exception as e:
            return logging_setup.report("Building the aging report", e)

    def get_vat_summary(self, start_date, end_date):
        """Output VAT for a period — the sales side of a UAE FTA VAT return."""
        try:
            return {"success": True,
                    "summary": invoices_db.vat_summary(start_date, end_date)}
        except Exception as e:
            return logging_setup.report("Building the VAT summary", e)

    # --- Jobs --------------------------------------------------------------------
    # What happens after a quote is won. Until this existed the app could say a quote was Won
    # and how much had been paid, but nothing about what the work cost — so every margin it
    # reported was a quoted estimate, not a measured one.

    def get_jobs(self, status=None, limit=300):
        try:
            return {"success": True, "jobs": jobs_db.get_jobs(status=status, limit=limit)}
        except Exception as e:
            return logging_setup.report("Loading jobs", e)

    def get_job(self, job_id):
        try:
            job = jobs_db.get_job(job_id)
            if not job:
                return {"success": False, "error": "Job not found."}
            return {"success": True, "job": job}
        except Exception as e:
            return logging_setup.report("Loading that job", e)

    def create_job_from_quotation(self, history_id):
        """Turns a won quotation into a job.

        The quoted total is copied onto the job rather than read live, so later edits to the
        quotation cannot silently move the number the job's margin is measured against.
        """
        try:
            quote = history_db.get_quotation_by_id(history_id)
            if not quote:
                return {"success": False, "error": "Quotation not found."}

            existing = jobs_db.get_job_for_quotation(history_id)
            if existing:
                return {"success": True, "job_id": existing["id"], "existing": True}

            items = quote.get("items") or []
            title = (items[0].get("description", "").splitlines()[0][:80]
                     if items and isinstance(items[0], dict) else "")
            job_id = jobs_db.create_job(
                quotation_id=history_id,
                client_name=quote.get("client_name", ""),
                venue=quote.get("venue", ""),
                title=title or f"Job for {quote.get('client_name', 'client')}",
                quoted_total=quote.get("grand_total", 0),
            )
            log.info("Opened job for quotation %s (%s)", history_id, quote.get("quote_number"))
            return {"success": True, "job_id": job_id, "existing": False}
        except Exception as e:
            return logging_setup.report("Opening a job for this quotation", e)

    def create_job(self, job):
        """Opens a job directly, for work that never went through a quotation."""
        try:
            title = (job.get("title") or "").strip()
            if not title:
                return {"success": False, "error": "Give the job a name."}
            job_id = jobs_db.create_job(
                client_name=job.get("client_name", ""), venue=job.get("venue", ""),
                title=title, quoted_total=job.get("quoted_total", 0),
                start_date=job.get("start_date"), end_date=job.get("end_date"),
                site_contact=job.get("site_contact", ""), notes=job.get("notes", ""),
            )
            return {"success": True, "job_id": job_id}
        except Exception as e:
            return logging_setup.report("Creating the job", e)

    def update_job(self, job_id, fields):
        # pywebview's JS bridge marshals a JS object as a single positional dict, not
        # keyword arguments — a **fields signature here would reject every call from app.js.
        try:
            jobs_db.update_job(job_id, **fields)
            return {"success": True}
        except Exception as e:
            return logging_setup.report("Updating the job", e)

    def delete_job(self, job_id):
        try:
            jobs_db.delete_job(job_id)
            return {"success": True}
        except Exception as e:
            return logging_setup.report("Deleting the job", e)

    # --- Job costs ---------------------------------------------------------------

    def add_job_cost(self, job_id, description, category="Material", supplier_name=None,
                     quantity=1, unit_cost=0, amount=None, cost_date=None, invoice_ref=""):
        try:
            cost_id = jobs_db.add_job_cost(
                job_id, description, category=category, supplier_name=supplier_name,
                quantity=quantity, unit_cost=unit_cost, amount=amount,
                cost_date=cost_date, invoice_ref=invoice_ref,
            )
            return {"success": True, "cost_id": cost_id}
        except Exception as e:
            return logging_setup.report("Adding that cost", e)

    def update_job_cost(self, cost_id, fields):
        # Same bridge constraint as update_job above: the JS caller sends one dict argument.
        try:
            jobs_db.update_job_cost(cost_id, **fields)
            return {"success": True}
        except Exception as e:
            return logging_setup.report("Updating the cost", e)

    def delete_job_cost(self, cost_id):
        try:
            jobs_db.delete_job_cost(cost_id)
            return {"success": True}
        except Exception as e:
            return logging_setup.report("Deleting the cost", e)

    def get_cost_categories(self):
        return {"success": True, "categories": jobs_db.COST_CATEGORIES,
                "statuses": jobs_db.JOB_STATUSES}

    # --- Suppliers ---------------------------------------------------------------

    def get_suppliers(self):
        try:
            return {"success": True, "suppliers": jobs_db.get_suppliers()}
        except Exception as e:
            return logging_setup.report("Loading suppliers", e)

    def save_supplier(self, supplier):
        try:
            supplier_id = jobs_db.save_supplier(
                supplier_id=supplier.get("id"), name=supplier.get("name"),
                phone=supplier.get("phone"), email=supplier.get("email"),
                notes=supplier.get("notes"),
            )
            return {"success": True, "id": supplier_id}
        except Exception as e:
            return logging_setup.report("Saving the supplier", e)

    def delete_supplier(self, supplier_id):
        try:
            jobs_db.delete_supplier(supplier_id)
            return {"success": True}
        except Exception as e:
            return logging_setup.report("Deleting the supplier", e)

    # --- Job reporting -----------------------------------------------------------

    def get_job_margin_report(self, period_days=90):
        try:
            return {"success": True, "report": jobs_db.margin_report(period_days)}
        except Exception as e:
            return logging_setup.report("Building the margin report", e)

    def get_upcoming_jobs(self, days=30):
        try:
            return {"success": True, "jobs": jobs_db.upcoming_jobs(days)}
        except Exception as e:
            return logging_setup.report("Loading the schedule", e)

    # --- Item Catalog --------------------------------------------------------------

    def get_catalog_items(self):
        try:
            return {"success": True, "items": catalog_db.get_catalog_items()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def save_catalog_item(self, item):
        try:
            description = (item.get("description") or "").strip()
            if not description:
                return {"success": False, "error": "Description is required."}
            item_id = item.get("id")
            if item_id:
                catalog_db.update_catalog_item(
                    item_id, description=description, unit=item.get("unit"),
                    rate=item.get("rate"), cost_price=item.get("cost_price"),
                    category=item.get("category"),
                )
                return {"success": True, "id": item_id}
            new_id = catalog_db.add_catalog_item(
                description, unit=item.get("unit") or "Pcs", rate=item.get("rate") or 0,
                cost_price=item.get("cost_price"), category=item.get("category"),
            )
            return {"success": True, "id": new_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_catalog_item(self, item_id):
        try:
            catalog_db.delete_catalog_item(item_id)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}


def _handle_estimator_drop(window, event):
    """Native counterpart to the JS drop handler on #est-dropzone.

    The browser's File API never exposes a real filesystem path for a dropped file — only
    pywebview's own DOM event bridge can, and only for elements it has a registered 'drop'
    listener on (see _bind_estimator_dropzone). Without this, dropping a file onto the
    estimator does nothing: app.js's ondrop only stops the browser from navigating away.
    """
    files = ((event or {}).get("dataTransfer") or {}).get("files") or []
    paths = [f["pywebviewFullPath"] for f in files if f.get("pywebviewFullPath")]
    if not paths:
        window.evaluate_js(
            "showToast('Could not read the dropped file path — use Upload Drawings instead.', 'error')"
        )
        return
    window.evaluate_js(f"ingestDesignPaths({json.dumps(paths)})")


def _bind_estimator_dropzone(window):
    element = window.dom.get_element("#est-dropzone")
    if element:
        element.events.drop += DOMEventHandler(
            lambda event: _handle_estimator_drop(window, event), prevent_default=True
        )


def main():
    api = QuotationApi()
    company_name = doc_generator.COMPANY.get("name", "Company")
    window = webview.create_window(
        f'{company_name.title()} Smart Quotation Engine',
        'index.html',
        js_api=api,
        width=1440,
        height=900,
        resizable=True,
        background_color='#0a0a0b'
    )
    window.events.loaded += lambda: _bind_estimator_dropzone(window)
    # Devtools are opt-in via QE_DEBUG=1 rather than always on: a shipped build should not
    # hand end users an inspector over the app's own data.
    debug = os.environ.get("QE_DEBUG", "").lower() in ("1", "true", "yes")
    # http_server serves this directory over localhost, which is what lets the page load
    # product photos with a plain relative <img src="images/..."> instead of receiving
    # megabytes of base64 through the JS bridge.
    webview.start(debug=debug, http_server=True)


if __name__ == '__main__':
    main()
