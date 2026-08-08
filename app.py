import os
import re
import json
import webbrowser
from datetime import datetime
from pathlib import Path

import numpy as np
import chromadb
from sentence_transformers import SentenceTransformer
import webview

import parsing
import doc_generator
import history_db
import image_tools
import pdf_export
import sharing
import corrections_db
import design_parser
import calculators
import rate_card

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "chroma_db"))
COLLECTION_NAME = "quotation_items"
PHOTO_COLLECTION_NAME = "photo_library"

# Cross-fill thresholds (cosine similarity on description embeddings). Above AUTO, two items
# are effectively the same product quoted twice, so a photo from one is safe to reuse on the
# other. Between SUGGEST and AUTO it is a likely-but-not-certain match, still attached but
# flagged more softly. Below SUGGEST we leave the item without a photo rather than guess.
CROSSFILL_AUTO = 0.82
CROSSFILL_SUGGEST = 0.70

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


def _load_sync_config():
    try:
        if SYNC_CONFIG_PATH.exists():
            with open(SYNC_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("default_path"):
                return {**_DEFAULT_SYNC_CONFIG, **data}
    except Exception as e:
        print(f"Failed to load sync_config.json, using defaults: {e}")

    try:
        with open(SYNC_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(_DEFAULT_SYNC_CONFIG, f, indent=2)
    except Exception as e:
        print(f"Could not write sync_config.json: {e}")

    return _DEFAULT_SYNC_CONFIG


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

    have = [i for i, it in enumerate(items) if it.get("image_base64")]
    # A generic service line has no product to photograph, but its wording is close enough to
    # the same wording in another job for the embedding to score a confident match — which is
    # how "Delivery" ended up showing a photo lifted from a furniture quotation. Nothing here
    # can be illustrated by borrowing, so these are left without a photo on purpose.
    need = [i for i, it in enumerate(items)
            if not it.get("image_base64") and not _is_generic_service(it.get("original_description", ""))]
    if not have or not need:
        return 0

    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    unit = emb / np.clip(norms, 1e-9, None)
    have_mat = unit[have]

    filled = 0
    for i in need:
        sims = have_mat @ unit[i]
        best = int(np.argmax(sims))
        score = float(sims[best])
        if score < CROSSFILL_SUGGEST:
            continue
        source_item = items[have[best]]
        items[i]["image_base64"] = source_item["image_base64"]
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

    def _get_model(self):
        """Lazy loads sentence-transformers model to save initial window boot time."""
        if self.model is None:
            print("Loading sentence-transformers model (all-MiniLM-L6-v2)...")
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
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

            try:
                self.client.delete_collection(name=COLLECTION_NAME)
            except Exception:
                pass
            self.collection = self.client.get_or_create_collection(name=COLLECTION_NAME)

            seen, unique_items = set(), []
            for item in all_items:
                key = (item['original_description'].lower().strip(), item['historical_rate'])
                if key not in seen:
                    seen.add(key)
                    unique_items.append(item)

            # Re-apply any prior PM corrections from the Needs Review queue, so a fix made once
            # survives future re-syncs of the same source files instead of getting overwritten.
            all_corrections = corrections_db.get_all_corrections()
            for item in unique_items:
                key = (str(item['file_name']).strip(), item['original_description'].strip().lower())
                fix = all_corrections.get(key)
                if fix:
                    if fix.get("rate") is not None:
                        item['historical_rate'] = float(fix["rate"])
                    if fix.get("unit"):
                        item['unit'] = fix["unit"]
                    if fix.get("venue"):
                        item['venue'] = fix["venue"]
                    item['rate_confidence'] = "high"
                    item['venue_confidence'] = "high"
                    item['needs_review'] = False
                    item['flag_reason'] = "corrected by PM"

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
            for idx, item in enumerate(unique_items):
                ids.append(f"item_{idx}")
                documents.append(item['original_description'])
                embeddings.append(computed_embeddings[idx].tolist())
                metadatas.append({
                    'original_description': item['original_description'],
                    'historical_rate': float(item['historical_rate']),
                    'unit': str(item['unit']),
                    'quote_date': str(item['quote_date']),
                    'venue': str(item.get('venue', 'Venue Unspecified')),
                    'file_name': str(item['file_name']),
                    'image_base64': str(item['image_base64']),
                    'image_source': str(item.get('image_source', '')),
                    'rate_confidence': str(item.get('rate_confidence', 'medium')),
                    'venue_confidence': str(item.get('venue_confidence', 'medium')),
                    'needs_review': bool(item.get('needs_review', False)),
                    'flag_reason': str(item.get('flag_reason', '')),
                })

            self.collection.add(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=documents)

            own = sum(1 for it in unique_items if it.get('image_base64') and not str(it.get('image_source', '')).startswith(('matched', 'suggested')))
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
                        'image_base64': metadata.get('image_base64', ''),
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
            if rate is not None and str(rate).strip() != "":
                meta["historical_rate"] = float(rate)
            if unit:
                meta["unit"] = str(unit)
            if venue:
                meta["venue"] = str(venue)
            meta["rate_confidence"] = "high"
            meta["venue_confidence"] = "high"
            meta["needs_review"] = False
            meta["flag_reason"] = "corrected by PM"

            self.collection.update(ids=[item_id], metadatas=[meta])

            corrections_db.save_correction(
                file_name=meta.get("file_name", ""),
                original_description=meta.get("original_description", ""),
                rate=meta.get("historical_rate"),
                unit=meta.get("unit"),
                venue=meta.get("venue"),
            )

            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

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
                corrections_db.save_correction(
                    file_name=meta.get("file_name", ""),
                    original_description=meta.get("original_description", ""),
                    rate=meta.get("historical_rate"),
                    unit=meta.get("unit"),
                    venue=venue,
                )

            return {"success": True, "updated": len(ids_to_update)}
        except Exception as e:
            return {"success": False, "error": str(e)}

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

            corrections_db.save_correction(
                file_name=meta.get("file_name", ""),
                original_description=meta.get("original_description", ""),
                rate=meta.get("historical_rate"),
                unit=meta.get("unit"),
                venue=meta.get("venue"),
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

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

            # Reserved up front so the printed reference on the document matches the history
            # record, which can only be written after the files exist.
            reserved_id = history_db.peek_next_quotation_id()
            quote_ref = f"Q-{reserved_id}"

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
                    with open(str(out_path), "w") as f:
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

            history_id = history_db.save_quotation_history({
                "client_name": client_name, "client_phone": client_phone, "venue": venue,
                "quote_date": quote_date, "items": items,
                "discount_type": discount_type, "discount_value": discount_value,
                "subtotal": totals["subtotal"], "vat": totals["vat"], "grand_total": totals["grand_total"],
                "xlsx_path": str(xlsx_path.resolve()) if xlsx_path else "",
                "docx_path": str(docx_path.resolve()) if docx_path else "",
                "pdf_path": pdf_path or "",
                "valid_until": valid_until,
            })

            quote_ref = f"Q-{history_id}"
            if history_id != reserved_id:
                print(f"Quote ref drift: document printed {reserved_id}, history row is {history_id}.")
            whatsapp_link = sharing.build_whatsapp_link(client_name, quote_ref, totals["grand_total"], items, client_phone)
            mailto_link = sharing.build_mailto_link(
                client_name, quote_ref, totals["grand_total"], items,
                pdf_path or (str(xlsx_path) if xlsx_path else None)
            )

            return {
                "success": True,
                "history_id": history_id,
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

    # --- Images ------------------------------------------------------------------

    def fetch_image_suggestions(self, query):
        return image_tools.fetch_image_suggestions(query)

    def fetch_image_from_url(self, url):
        return image_tools.fetch_image_as_base64(url)

    def upload_image_dialog(self):
        try:
            window = webview.windows[0]
            result = window.create_file_dialog(
                webview.OPEN_DIALOG, file_types=('Image Files (*.jpg;*.jpeg;*.png;*.gif;*.bmp)',)
            )
            if not result:
                return {"success": False, "error": "No file selected."}
            return image_tools.bytes_from_local_file(result[0])
        except Exception as e:
            return {"success": False, "error": str(e)}

    # --- Photo library -----------------------------------------------------------
    # A small, growing bank of real product photos separate from historical pricing data.
    # Instead of requiring a bulk photo-shoot project up front, any image a PM sets on a
    # draft item can be saved here with one click; future items with a similar description
    # then surface it automatically via the same semantic matching used for price search.

    def save_photo_to_library(self, description, image_base64):
        try:
            description = (description or "").strip()
            if not description or not image_base64:
                return {"success": False, "error": "Need both a description and an image to save."}

            model = self._get_model()
            embedding = model.encode(description).tolist()
            photo_id = f"photo_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

            self.photo_collection.add(
                ids=[photo_id],
                embeddings=[embedding],
                documents=[description],
                metadatas=[{
                    "description": description,
                    "image_base64": image_base64,
                    "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }],
            )
            return {"success": True, "id": photo_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

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
                    matches.append({
                        "id": photo_id,
                        "description": metadata.get("description", ""),
                        "image_base64": metadata.get("image_base64", ""),
                        "similarity": _distance_to_similarity(distance),
                    })
            return {"success": True, "matches": matches}
        except Exception as e:
            return {"success": False, "error": str(e)}

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
                try:
                    items.append(calculators.compute_item_boq(spec, card))
                except rate_card.MissingRateError as exc:
                    # A missing code is a data problem the PM can fix in the CSV; naming the
                    # item beats failing the whole batch with a bare KeyError.
                    errors.append(f"{spec.get('label') or f'Item {index + 1}'}: {exc}")
                except Exception as exc:
                    errors.append(f"{spec.get('label') or f'Item {index + 1}'}: {exc}")

            if not items:
                return {"success": False, "error": "; ".join(errors) or "Nothing could be costed."}

            summary = calculators.aggregate(items, margin_pct, card)
            return {"success": True, "items": items, "summary": summary, "errors": errors}
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
            items = [calculators.compute_item_boq(spec, card) for spec in specs]
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
            return {"success": True, "item": item}
        except Exception as e:
            return {"success": False, "error": str(e)}

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
    webview.start(debug=True)


if __name__ == '__main__':
    main()
