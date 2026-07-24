import os
import re
import json
import webbrowser
from datetime import datetime
from pathlib import Path

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

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "chroma_db"))
COLLECTION_NAME = "quotation_items"
PHOTO_COLLECTION_NAME = "photo_library"


class QuotationApi:
    def __init__(self):
        self.model = None
        self.client = chromadb.PersistentClient(path=DB_PATH)
        self.collection = self.client.get_or_create_collection(name=COLLECTION_NAME)
        # Separate collection from historical pricing data: a small, PM-curated bank of real
        # product photos, keyed by description via the same semantic search as item matching.
        # Grows organically as PMs save photos while quoting, instead of needing a bulk upload.
        self.photo_collection = self.client.get_or_create_collection(name=PHOTO_COLLECTION_NAME)
        self.sync_path = "G:\\My Drive"

    def _get_model(self):
        """Lazy loads sentence-transformers model to save initial window boot time."""
        if self.model is None:
            print("Loading sentence-transformers model (all-MiniLM-L6-v2)...")
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
        return self.model

    # --- Status / analytics -------------------------------------------------

    def get_bundles(self):
        """Returns the configured Quick Quote Bundles (common project packages).

        Read from bundles.json on every call rather than cached at import, so a PM can edit
        their package presets and see the change on the next app open without a code change.
        """
        try:
            path = Path(__file__).resolve().parent / "bundles.json"
            if not path.exists():
                return {"success": True, "bundles": []}
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {"success": True, "bundles": data.get("bundles", [])}
        except Exception as e:
            return {"success": False, "error": str(e), "bundles": []}

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
            excel_files, pdf_files, word_files = [], [], []
            for file in path_obj.rglob("*"):
                if file.name.startswith("~$") or not file.is_file():
                    continue
                suffix = file.suffix.lower()
                if suffix == ".xlsx":
                    excel_files.append(file)
                elif suffix == ".pdf":
                    pdf_files.append(file)
                elif suffix == ".docx":
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
                    'rate_confidence': str(item.get('rate_confidence', 'medium')),
                    'venue_confidence': str(item.get('venue_confidence', 'medium')),
                    'needs_review': bool(item.get('needs_review', False)),
                    'flag_reason': str(item.get('flag_reason', '')),
                })

            self.collection.add(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=documents)

            return {
                "success": True,
                "indexed_count": len(unique_items),
                "message": f"Indexing complete: {len(unique_items)} unique historical items indexed."
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
                    similarity = 1.0 / (1.0 + distance)

                    rate = float(metadata.get('historical_rate', 0.0))
                    quote_date = metadata.get('quote_date', '')

                    historical_year = current_year
                    if quote_date:
                        try:
                            historical_year = int(quote_date.split('-')[0])
                        except ValueError:
                            pass

                    elapsed_years = max(0, current_year - historical_year)
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
                        'similarity': round(similarity * 100, 1),
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
                    similarity = round((1.0 / (1.0 + distance)) * 100, 1)
                    matches.append({
                        "id": photo_id,
                        "description": metadata.get("description", ""),
                        "image_base64": metadata.get("image_base64", ""),
                        "similarity": similarity,
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

    # --- Sharing ----------------------------------------------------------------

    def open_external_link(self, url):
        try:
            webbrowser.open(url)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_path(self, path):
        return pdf_export.open_file(path)

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
