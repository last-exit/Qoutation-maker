# -*- coding: utf-8 -*-
"""Builds the price archive from a folder of past quotation documents.

Incremental and non-destructive by construction. The desktop build deleted the whole
collection and rebuilt it, and it did so *before* loading the embedding model — so any
failure in between left the business with an empty price library and no backup. Here items
are matched by content hash: unchanged ones are left alone, changed ones are written, and
only items whose source document was re-read and no longer contains them are removed. A crash
part-way leaves the archive exactly as it was.
"""
import logging
import os
import re
from pathlib import Path

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..lib import imaging, parsing

_logger = logging.getLogger(__name__)

# Quotations this system produced are output, not source pricing. Re-reading them fed
# already-marked-up rates back into the archive — the same structure appeared at 29,120 then
# 35,200 then 42,592 as the markup compounded on each pass — and scraped their header labels
# and totals in as products.
SELF_GENERATED_RE = re.compile(r'_Quotation_\d{8}_\d{4}\.(xlsx|docx|pdf)$', re.I)

SUPPORTED_SUFFIXES = {".xlsx": "xlsx", ".pdf": "pdf", ".docx": "docx"}

# Cosine similarity thresholds for lending a photo to an item that has none. Above AUTO two
# items are effectively the same product quoted twice; between SUGGEST and AUTO it is likely
# but not certain, so the borrowed photo is labelled more cautiously. Below SUGGEST the item
# is left without a picture rather than showing the client something from a different job.
CROSSFILL_AUTO = 0.82
CROSSFILL_SUGGEST = 0.70

# Line items that price labour, logistics or fees rather than a physical product. "storage"
# is deliberately absent: here it describes a product feature far more often than a fee
# ("Lego Wall with Storage"), and misclassifying a product as a service costs it its photo.
GENERIC_SERVICE_RE = re.compile(
    r'\b(delivery|transport(ation)?|installation|install|crew|labour|labor|manpower|'
    r'dismantl\w*|removal|freight|shipping|handling|rental|hire|'
    r'supervis\w*|management fee|contingency|misc(ellaneous)?|sundr\w+|'
    r'discount|vat|charges?|fees?)\b', re.I)


def _is_generic_service(description):
    text = str(description or "").strip()
    if not text:
        return True
    # Only when that is what the line is *about* — a product whose spec mentions
    # "installation" further down still deserves its photo.
    return bool(GENERIC_SERVICE_RE.search(text.split("\n")[0]))


class ArchiveIndexer(models.AbstractModel):
    _name = "redcube.archive.indexer"
    _description = "Price Archive Indexer"

    # --- Configuration ----------------------------------------------------------------

    @api.model
    def archive_path(self):
        """Folder to index. Defaults to the bind mount configured in docker-compose."""
        return self.env["ir.config_parameter"].sudo().get_param(
            "redcube.archive_path", "/mnt/archive"
        )

    # --- Scanning ---------------------------------------------------------------------

    @api.model
    def _discover(self, root):
        """Every indexable document under `root`, with what was skipped and why.

        Anything not scanned is reported rather than dropped. An earlier filename filter
        ("quotation", "cost sheet", ...) silently skipped 12 real pricing files — including
        the two largest photo sources — and nobody noticed for months. The folder is the
        filter.
        """
        found, self_generated, unreadable = [], [], []
        for path in sorted(Path(root).rglob("*")):
            if path.name.startswith("~$") or not path.is_file():
                continue
            file_type = SUPPORTED_SUFFIXES.get(path.suffix.lower())
            if not file_type:
                continue
            if SELF_GENERATED_RE.search(path.name):
                self_generated.append(path.name)
                continue
            try:
                path.stat()
            except OSError:
                unreadable.append(path.name)
                continue
            found.append((path, file_type))
        return found, self_generated, unreadable

    @staticmethod
    def _fingerprint(path):
        """Cheap change-detection: size plus modification time. Avoids re-parsing hundreds of
        untouched documents on every run, without hashing whole files."""
        stat = path.stat()
        return f"{stat.st_size}:{int(stat.st_mtime)}"

    @api.model
    def _parse(self, path, file_type):
        parser = {
            "xlsx": parsing.parse_excel_file,
            "pdf": parsing.parse_pdf_file,
            "docx": parsing.parse_docx_file,
        }[file_type]
        return parser(path)

    # --- Indexing ---------------------------------------------------------------------

    @api.model
    def run(self, root=None, force=False):
        """Indexes the archive. Returns a summary dict for the UI.

        `force` re-parses documents whose fingerprint is unchanged, which is what you want
        after a parser change rather than a document change.
        """
        root = root or self.archive_path()
        if not os.path.isdir(root):
            raise UserError(_(
                "Archive folder not found: %s\n\n"
                "Set ARCHIVE_PATH in odoo/.env to a local folder, external drive or NAS "
                "mount, then restart the container.", root,
            ))

        Source = self.env["redcube.archive.source"]
        Item = self.env["redcube.archive.item"]
        Correction = self.env["redcube.archive.correction"]

        imaging.reset()
        documents, self_generated, unreadable = self._discover(root)
        if not documents:
            return {
                "indexed": 0, "created": 0, "updated": 0, "removed": 0,
                "documents": 0, "skipped_self_generated": len(self_generated),
                "message": _("No spreadsheets, PDFs or Word documents found in %s.", root),
            }

        corrections = {
            (c.source_name, c.description_key): c
            for c in Correction.search([])
        }

        parsed_items = []
        touched_source_ids = []
        documents_parsed = 0
        failed_documents = []
        # Documents that were read but yielded no priceable lines. The parsers catch their own
        # errors and return an empty list, so without tracking this a corrupt or unrecognised
        # document contributes nothing and reports nothing — the exact failure mode that lost
        # 12 real pricing files to an earlier filename filter.
        empty_documents = []

        for path, file_type in documents:
            source = Source.search([("name", "=", path.name)], limit=1)
            fingerprint = self._fingerprint(path)
            if source and source.content_fingerprint == fingerprint and not force:
                # Unchanged since last run; its existing items stay as they are.
                continue

            try:
                raw_items = self._parse(path, file_type)
            except Exception as exc:
                # One unreadable document must not abandon the whole archive.
                _logger.exception("Failed to parse %s", path.name)
                failed_documents.append(f"{path.name}: {exc}")
                continue

            if not source:
                source = Source.create({
                    "name": path.name,
                    "relative_path": str(path.relative_to(root)),
                    "file_type": file_type,
                })
            else:
                source.relative_path = str(path.relative_to(root))
                source.file_type = file_type

            documents_parsed += 1
            touched_source_ids.append(source.id)
            if not raw_items:
                empty_documents.append(path.name)

            for raw in raw_items:
                values = self._item_values(raw, source)
                key = (source.name, Correction.normalize_key(raw.get("original_description")))
                fix = corrections.get(key)
                if fix:
                    fix.apply_to(values)
                parsed_items.append((source, values))

            source.write({
                "last_indexed": fields.Datetime.now(),
                "content_fingerprint": fingerprint,
                "venue": (raw_items[0].get("venue") if raw_items else source.venue) or source.venue,
                "document_date": self._first_date(raw_items) or source.document_date,
            })

        if not parsed_items and not touched_source_ids:
            return {
                "indexed": Item.search_count([]), "created": 0, "updated": 0, "removed": 0,
                "documents": 0, "skipped_self_generated": len(self_generated),
                "message": _("Everything is already up to date — no documents have changed."),
            }

        # Same description at the same rate from the same document is one observation.
        deduped = {}
        for source, values in parsed_items:
            deduped.setdefault(values["content_hash"], (source, values))

        created, updated = self._upsert(deduped)
        removed = self._remove_stale(touched_source_ids, set(deduped))

        embedded = self._embed(list(deduped))
        crossfilled = self._crossfill_photos(list(deduped))

        summary = {
            "indexed": Item.search_count([]),
            "created": created,
            "updated": updated,
            "removed": removed,
            "embedded": embedded,
            "crossfilled": crossfilled,
            "documents": documents_parsed,
            "photos": imaging.blob_count(),
            "skipped_self_generated": len(self_generated),
            "failed_documents": failed_documents,
            "empty_documents": empty_documents,
            "unreadable": unreadable,
        }
        summary["message"] = self._summarize(summary)
        imaging.reset()
        _logger.info("Archive index complete: %s", summary["message"])
        return summary

    # --- Record writing ---------------------------------------------------------------

    @api.model
    def _item_values(self, raw, source):
        Item = self.env["redcube.archive.item"]
        description = raw.get("original_description") or ""
        rate = float(raw.get("historical_rate") or 0)
        return {
            "content_hash": Item.build_content_hash(source.name, description, rate),
            "name": description,
            "rate": rate,
            "uom_label": raw.get("unit") or "Pcs",
            "quote_date": self._as_date(raw.get("quote_date")),
            "venue": raw.get("venue") or "",
            "source_id": source.id,
            "image_hash": raw.get("image_ref") or "",
            "rate_confidence": raw.get("rate_confidence") or "medium",
            "venue_confidence": raw.get("venue_confidence") or "medium",
            "needs_review": bool(raw.get("needs_review")),
            "flag_reason": raw.get("flag_reason") or "",
        }

    @staticmethod
    def _as_date(value):
        text = str(value or "").strip()[:10]
        for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
            try:
                from datetime import datetime
                return datetime.strptime(text[:len(datetime.now().strftime(fmt))], fmt).date()
            except ValueError:
                continue
        return False

    @classmethod
    def _first_date(cls, raw_items):
        for raw in raw_items or []:
            parsed = cls._as_date(raw.get("quote_date"))
            if parsed:
                return parsed
        return False

    @staticmethod
    def _same_value(record, field_name, value):
        """Whether a record already holds `value`, comparing like with like.

        A naive `record[field] != value` is wrong for two field types here. A many2one reads
        back as a recordset, which never equals the plain integer id the parser produced, so
        every item looked changed and was rewritten on every run. Floats need a tolerance,
        since a rate that round-trips through the database can differ in the last bit.
        """
        current = record[field_name]
        field = record._fields[field_name]

        if field.type == "many2one":
            return current.id == (value or False)
        if field.type == "float":
            return abs((current or 0.0) - float(value or 0.0)) < 1e-6
        if field.type == "date" and value:
            return current and current.isoformat() == getattr(value, "isoformat", lambda: value)()
        return current == (value if value is not None else False)

    @api.model
    def _upsert(self, deduped):
        """Creates new items and updates changed ones, matched on content hash.

        Nothing is deleted here. That is what makes a failed run harmless.
        """
        Item = self.env["redcube.archive.item"]
        existing = {
            item.content_hash: item
            for item in Item.with_context(active_test=False).search(
                [("content_hash", "in", list(deduped))]
            )
        }

        to_create, created, updated = [], 0, 0
        for content_hash, (_source, values) in deduped.items():
            record = existing.get(content_hash)
            payload = dict(values)
            image_bytes = imaging.get_blob(payload.get("image_hash") or "")
            if image_bytes:
                import base64
                payload["image"] = base64.b64encode(image_bytes)
            else:
                payload.pop("image_hash", None)

            if record:
                changed = {
                    k: v for k, v in payload.items()
                    if k != "image" and not self._same_value(record, k, v)
                }
                if "image" in payload and not record.image_hash:
                    changed["image"] = payload["image"]
                    changed["image_hash"] = payload.get("image_hash", "")
                if changed:
                    record.write(changed)
                    updated += 1
            else:
                to_create.append(payload)

        if to_create:
            Item.create(to_create)
            created = len(to_create)
        return created, updated

    @api.model
    def _remove_stale(self, touched_source_ids, live_hashes):
        """Drops items whose document was re-read and no longer contains them.

        Scoped to documents actually parsed this run — an item from a document that was
        skipped as unchanged, or that failed to parse, is untouched.
        """
        if not touched_source_ids:
            return 0
        stale = self.env["redcube.archive.item"].search([
            ("source_id", "in", touched_source_ids),
            ("content_hash", "not in", list(live_hashes)),
        ])
        count = len(stale)
        stale.unlink()
        return count

    # --- Embeddings and photos --------------------------------------------------------

    @api.model
    def _embed(self, content_hashes):
        """Computes and stores description embeddings for the given items."""
        if not content_hashes:
            return 0
        Item = self.env["redcube.archive.item"]
        items = Item.search([("content_hash", "in", content_hashes)])
        if not items:
            return 0

        from ..lib.embedder import get_embedder
        vectors = get_embedder().encode([item.name for item in items])
        Item.write_embeddings({item.id: vectors[i] for i, item in enumerate(items)})
        return len(items)

    @api.model
    def _crossfill_photos(self, content_hashes):
        """Lends a photo to items that have none from their nearest photographed twin.

        The same structure is often quoted with a picture on one job and text-only on
        another. Borrowed photos are labelled in `image_origin` so the UI can say where they
        came from rather than passing another job's photo off as this line's own.
        """
        if not content_hashes:
            return 0
        import numpy as np

        Item = self.env["redcube.archive.item"]
        items = Item.search([("content_hash", "in", content_hashes)])
        have = [i for i in items if i.image_hash]
        need = [i for i in items if not i.image_hash and not _is_generic_service(i.name)]
        if not have or not need:
            return 0

        from ..lib.embedder import get_embedder
        model = get_embedder()
        have_vectors = np.asarray(model.encode([i.name for i in have]), dtype=np.float32)
        need_vectors = np.asarray(model.encode([i.name for i in need]), dtype=np.float32)

        # Apple's Accelerate BLAS leaves floating-point status flags set in unused SIMD
        # lanes, so this matmul warns on perfectly clean unit vectors. Verified against a
        # float64 reference: results agree to 3.5e-08 and pick the same nearest neighbour.
        with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
            sims = have_vectors @ need_vectors.T

        filled = 0
        for column, item in enumerate(need):
            best = int(np.argmax(sims[:, column]))
            score = float(sims[best, column])
            if score < CROSSFILL_SUGGEST:
                continue
            donor = have[best]
            if not donor.image:
                continue
            prefix = "matched" if score >= CROSSFILL_AUTO else "suggested"
            item.write({
                "image": donor.image,
                "image_hash": donor.image_hash,
                "image_origin": f"{prefix} from {donor.source_name}",
            })
            filled += 1
        return filled

    # --- Reporting --------------------------------------------------------------------

    @api.model
    def _summarize(self, summary):
        parts = [_(
            "%(documents)s document(s) read: %(created)s new item(s), %(updated)s updated, "
            "%(removed)s removed. %(indexed)s items in the archive.",
            **summary,
        )]
        if summary.get("crossfilled"):
            parts.append(_("%s photo(s) matched from other quotations.", summary["crossfilled"]))
        if summary.get("skipped_self_generated"):
            parts.append(_(
                "Ignored %s quotation(s) this system generated itself, so their marked-up "
                "prices do not re-enter the archive.", summary["skipped_self_generated"],
            ))
        # Failures are stated outright. Silently skipping documents is exactly how an earlier
        # filename filter lost 12 pricing files without anyone noticing.
        if summary.get("failed_documents"):
            parts.append(_("%s document(s) could not be read: %s",
                           len(summary["failed_documents"]),
                           "; ".join(summary["failed_documents"][:3])))
        if summary.get("empty_documents"):
            parts.append(_(
                "%s document(s) were read but contained no priceable lines: %s. They may be "
                "corrupt, or laid out in a way the parser does not recognise.",
                len(summary["empty_documents"]), "; ".join(summary["empty_documents"][:3]),
            ))
        return " ".join(parts)
