# -*- coding: utf-8 -*-
"""Indexer and archive-model tests, run inside Odoo.

Built against a workbook created in the test rather than a committed fixture, so the whole
path is exercised: openpyxl reads it, the parser classifies its columns, an embedded photo is
extracted and normalized, and records land in Postgres with vectors attached.

Run with:
    docker compose exec odoo odoo -d redcube --test-enable --test-tags redcube_price_intelligence \\
        -u redcube_price_intelligence --stop-after-init
"""
import base64
import io
import os
import tempfile

from odoo.tests import TransactionCase, tagged

from ..lib import imaging


def _workbook(folder, name, rows, with_photo=True):
    """Writes a quotation-shaped .xlsx into `folder`."""
    import openpyxl
    from openpyxl.drawing.image import Image as XLImage
    from PIL import Image

    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(["Description", "Unit", "Qty", "Rate", "Total"])
    for description, rate in rows:
        sheet.append([description, "Pcs", 1, rate, rate])

    if with_photo:
        photo_path = os.path.join(folder, f"{name}.png")
        Image.new("RGB", (240, 180), (180, 60, 40)).save(photo_path)
        drawing = XLImage(photo_path)
        drawing.anchor = "G2"
        sheet.add_image(drawing)

    path = os.path.join(folder, f"{name}.xlsx")
    book.save(path)
    return path


@tagged("post_install", "-at_install", "redcube_price_intelligence")
class TestArchiveIndexer(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Item = cls.env["redcube.archive.item"]
        cls.Source = cls.env["redcube.archive.source"]
        cls.Correction = cls.env["redcube.archive.correction"]
        cls.Indexer = cls.env["redcube.archive.indexer"]

    def setUp(self):
        super().setUp()
        self.folder = tempfile.mkdtemp(prefix="archive-")
        imaging.reset()
        self.addCleanup(imaging.reset)

    # --- Identity ---------------------------------------------------------------------

    def test_content_hash_is_stable_and_position_independent(self):
        """Ids used to be the row's position in the parse output, so a re-sync silently
        re-pointed every id at a different product."""
        first = self.Item.build_content_hash("a.xlsx", "Pirate Ship", 100.0)
        again = self.Item.build_content_hash("a.xlsx", "Pirate Ship", 100.0)
        self.assertEqual(first, again)
        self.assertEqual(first, self.Item.build_content_hash("A.XLSX", "  pirate ship ", 100.0))
        self.assertNotEqual(first, self.Item.build_content_hash("a.xlsx", "Pirate Ship", 101.0))
        self.assertNotEqual(first, self.Item.build_content_hash("b.xlsx", "Pirate Ship", 100.0))

    def test_title_is_the_first_line(self):
        item = self.Item.create({
            "content_hash": "t1",
            "name": "Jungle Gym Playhouse\n10m x 5m\n- Slide",
        })
        self.assertEqual(item.title, "Jungle Gym Playhouse")

    # --- Indexing ---------------------------------------------------------------------

    def test_indexes_a_workbook(self):
        _workbook(self.folder, "Cost Sheet - Alpha", [("Pirate Ship", 500), ("Swing Set", 250)])
        summary = self.Indexer.run(root=self.folder)

        self.assertEqual(summary["documents"], 1)
        self.assertEqual(summary["created"], 2)
        items = self.Item.search([("source_name", "=", "Cost Sheet - Alpha.xlsx")])
        self.assertEqual(len(items), 2)
        self.assertEqual(sorted(items.mapped("rate")), [250.0, 500.0])

    def test_embedded_photo_is_extracted_and_stored(self):
        _workbook(self.folder, "Cost Sheet - Photo", [("Pirate Ship", 500)])
        self.Indexer.run(root=self.folder)

        item = self.Item.search([("source_name", "=", "Cost Sheet - Photo.xlsx")], limit=1)
        self.assertTrue(item.image_hash, "the embedded photo should have been extracted")
        self.assertTrue(item.image, "the photo bytes should be attached to the record")
        # Normalized to JPEG before hashing — that is what makes the same photo arriving in
        # two formats collapse to one stored file.
        self.assertEqual(base64.b64decode(item.image)[:2], b"\xff\xd8")

    def test_reindex_is_incremental(self):
        _workbook(self.folder, "Cost Sheet - Beta", [("Pirate Ship", 500)])
        self.Indexer.run(root=self.folder)

        second = self.Indexer.run(root=self.folder)
        self.assertEqual(second["documents"], 0, "an unchanged document must not be re-read")
        self.assertEqual(second["created"], 0)
        self.assertEqual(second["removed"], 0)

    def test_changed_document_updates_and_removes_its_stale_lines(self):
        _workbook(self.folder, "Cost Sheet - Gamma", [("Pirate Ship", 500), ("Old Item", 99)])
        self.Indexer.run(root=self.folder)
        self.assertTrue(self.Item.search([("name", "=", "Old Item")]))

        # Same document, re-priced, with a line dropped.
        _workbook(self.folder, "Cost Sheet - Gamma", [("Pirate Ship", 750)])
        summary = self.Indexer.run(root=self.folder, force=True)

        self.assertFalse(self.Item.search([("name", "=", "Old Item")]),
                         "a line the document no longer contains should go")
        self.assertTrue(self.Item.search([("rate", "=", 750.0)]), "the new price should land")
        self.assertGreaterEqual(summary["removed"], 1)

    def test_stale_removal_is_scoped_to_documents_actually_read(self):
        """A document skipped as unchanged must keep its items, or an incremental run would
        quietly delete most of the archive."""
        _workbook(self.folder, "Cost Sheet - One", [("Pirate Ship", 500)])
        _workbook(self.folder, "Cost Sheet - Two", [("Swing Set", 250)])
        self.Indexer.run(root=self.folder)

        _workbook(self.folder, "Cost Sheet - One", [("Pirate Ship", 600)])
        self.Indexer.run(root=self.folder)

        self.assertTrue(self.Item.search([("name", "=", "Swing Set")]),
                        "the untouched document's items must survive")

    def test_self_generated_quotations_are_skipped(self):
        """Re-reading our own output fed already-marked-up rates back into the archive."""
        _workbook(self.folder, "Client_Quotation_20260101_1200", [("Pirate Ship", 9999)])
        summary = self.Indexer.run(root=self.folder)

        self.assertEqual(summary["skipped_self_generated"], 1)
        self.assertFalse(self.Item.search([("rate", "=", 9999.0)]))

    def test_unreadable_document_does_not_abandon_the_run(self):
        with open(os.path.join(self.folder, "Broken.xlsx"), "wb") as handle:
            handle.write(b"this is not a spreadsheet")
        _workbook(self.folder, "Cost Sheet - Good", [("Pirate Ship", 500)])

        summary = self.Indexer.run(root=self.folder)
        self.assertTrue(self.Item.search([("name", "=", "Pirate Ship")]),
                        "the readable document should still have been indexed")
        # The parsers catch their own errors and return an empty list, so a corrupt document
        # shows up as "read but produced nothing" rather than as a raised exception. Either
        # way it must be reported: silently skipping documents is how an earlier filename
        # filter lost 12 pricing files unnoticed.
        reported = summary["failed_documents"] + summary["empty_documents"]
        self.assertIn("Broken.xlsx", reported)
        self.assertIn("Broken.xlsx", summary["message"])

    def test_missing_folder_raises_something_actionable(self):
        from odoo.exceptions import UserError
        with self.assertRaises(UserError):
            self.Indexer.run(root="/nonexistent/archive")

    # --- Corrections ------------------------------------------------------------------

    def test_venue_correction_survives_reindex_without_freezing_the_rate(self):
        """The bug that made the review queue untrustworthy: any review action pinned the
        rate too, so a price change in the source could never reach the archive again."""
        _workbook(self.folder, "Cost Sheet - Delta", [("Pirate Ship", 500)])
        self.Indexer.run(root=self.folder)

        self.Correction.create({
            "source_name": "Cost Sheet - Delta.xlsx",
            "description_key": self.Correction.normalize_key("Pirate Ship"),
            "display_description": "Pirate Ship",
            "venue": "Kite Beach",
            "corrected_field_ids": "venue",
        })

        _workbook(self.folder, "Cost Sheet - Delta", [("Pirate Ship", 750)])
        self.Indexer.run(root=self.folder, force=True)

        item = self.Item.search([("source_name", "=", "Cost Sheet - Delta.xlsx")], limit=1)
        self.assertEqual(item.venue, "Kite Beach", "the correction should be re-applied")
        self.assertEqual(item.rate, 750.0, "the rate must still come from the document")

    def test_correction_with_no_pinned_fields_only_clears_the_flag(self):
        correction = self.Correction.create({
            "source_name": "x.xlsx", "description_key": "pirate ship",
            "rate": 1.0, "venue": "Nowhere", "corrected_field_ids": "",
        })
        values = correction.apply_to({"rate": 750.0, "venue": "Kite Beach", "needs_review": True})
        self.assertEqual(values["rate"], 750.0)
        self.assertEqual(values["venue"], "Kite Beach")
        self.assertFalse(values["needs_review"])

    def test_unknown_correction_fields_are_ignored(self):
        correction = self.Correction.create({
            "source_name": "x.xlsx", "description_key": "y",
            "rate": 1.0, "corrected_field_ids": "rate,sabotage",
        })
        self.assertEqual(correction.field_list(), ["rate"])

    # --- Vectors ----------------------------------------------------------------------

    def test_vector_literal_survives_numpy_scalars(self):
        """numpy 2 renders a float32 as `np.float32(0.02)`, which Postgres rejects outright."""
        import numpy as np
        literal = self.Item._vector_literal(np.asarray([0.5, -0.25], dtype=np.float32))
        self.assertNotIn("np.float32", literal)
        self.assertTrue(literal.startswith("[") and literal.endswith("]"))

    def test_indexing_populates_embeddings(self):
        _workbook(self.folder, "Cost Sheet - Vec", [("Pirate Ship", 500), ("Swing Set", 250)])
        self.Indexer.run(root=self.folder)

        items = self.Item.search([("source_name", "=", "Cost Sheet - Vec.xlsx")])
        self.assertTrue(all(items.mapped("has_embedding")),
                        "every indexed item should carry a vector")
        self.env.cr.execute(
            "SELECT COUNT(*) FROM redcube_archive_item WHERE id = ANY(%s) AND embedding IS NOT NULL",
            (items.ids,),
        )
        self.assertEqual(self.env.cr.fetchone()[0], len(items))

    def test_semantic_search_ranks_by_meaning(self):
        _workbook(self.folder, "Cost Sheet - Search", [
            ("Wooden play tower with slide", 5000),
            ("Transportation and crew charges", 1500),
        ])
        self.Indexer.run(root=self.folder)

        results = self.Item.semantic_search("climbing frame with a slide for children", limit=2)
        self.assertTrue(results, "semantic search should return matches")
        self.assertIn("play tower", results[0]["title"].lower(),
                      "the play structure should outrank the logistics line")
        self.assertGreater(results[0]["similarity"], results[-1]["similarity"])

    def test_semantic_search_on_empty_query_returns_nothing(self):
        self.assertEqual(self.Item.semantic_search("   "), [])

    def test_semantic_search_respects_an_extra_domain(self):
        _workbook(self.folder, "Cost Sheet - Scoped", [("Pirate Ship", 500)])
        self.Indexer.run(root=self.folder)

        wide = self.Item.semantic_search("pirate ship", limit=5)
        self.assertTrue(wide)
        narrow = self.Item.semantic_search(
            "pirate ship", limit=5, extra_domain=[("venue", "=", "No Such Venue")]
        )
        self.assertEqual(narrow, [])

    def test_forced_reindex_of_unchanged_documents_writes_nothing(self):
        """A many2one reads back as a recordset, so comparing it to the plain id the parser
        produced made every item look changed and rewritten on every run."""
        _workbook(self.folder, "Cost Sheet - Idem", [("Pirate Ship", 500), ("Swing Set", 250)])
        self.Indexer.run(root=self.folder)

        forced = self.Indexer.run(root=self.folder, force=True)
        self.assertEqual(forced["documents"], 2 - 1, "the one document is re-read under force")
        self.assertEqual(forced["created"], 0)
        self.assertEqual(forced["updated"], 0, "identical content must not be rewritten")
        self.assertEqual(forced["removed"], 0)
