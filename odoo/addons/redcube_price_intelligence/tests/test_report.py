# -*- coding: utf-8 -*-
"""The quotation document.

This is the artefact the client actually receives, so the tests care about what appears on
the page rather than about internals: that the photo is there, that the specification is
separated from the product name, that a borrowed photo is declared, and that the totals on
the page reconcile with the order.
"""
import base64
import io

from odoo import fields
from odoo.tests import TransactionCase, tagged

REPORT = "redcube_price_intelligence.report_quotation_redcube"


def _png(colour=(180, 60, 40)):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (120, 90), colour).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue())


@tagged("post_install", "-at_install", "redcube_price_intelligence")
class TestQuotationReport(TransactionCase):

    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create({"name": "Report Client"})
        self.item = self.env["redcube.archive.item"].create({
            "content_hash": "report-1",
            "name": "Pirate Ship\n- L5.8 x W3.4 x H3.2m\n- Twin commercial swings",
            "rate": 12000.0,
            "uom_label": "Set",
            "image": _png(),
            "image_hash": "a" * 64,
            "quote_date": fields.Date.subtract(fields.Date.today(), days=200),
        })
        self.order = self._order_with(self.item)

    def _order_with(self, item, discount=0.0):
        return self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": item._get_or_create_product().id,
                "name": item.name,
                "product_uom_qty": 2,
                "price_unit": 12000.0,
                "discount": discount,
                "archive_item_id": item.id,
            })],
        })

    def _render_html(self, order):
        """The rendered document as text.

        Under --test-enable Odoo short-circuits PDF generation and returns HTML, which is
        the more useful thing to assert against anyway: it says what actually reached the
        page rather than only that some bytes came back.
        """
        content, _kind = self.env["ir.actions.report"]._render_qweb_html(REPORT, order.ids)
        return content.decode() if isinstance(content, bytes) else content

    # --- Rendering --------------------------------------------------------------------

    def test_renders_a_real_pdf(self):
        """force_report_rendering overrides the test-mode short circuit, so this exercises
        wkhtmltopdf for real — the path that actually runs in production."""
        content, kind = self.env["ir.actions.report"].with_context(
            force_report_rendering=True,
        )._render_qweb_pdf(REPORT, res_ids=self.order.ids)
        self.assertEqual(kind, "pdf")
        self.assertTrue(content.startswith(b"%PDF"))
        self.assertGreater(len(content), 1000)

    def test_document_shows_the_product_and_its_specification(self):
        html = self._render_html(self.order)
        self.assertIn("Pirate Ship", html)
        self.assertIn("Twin commercial swings", html)
        self.assertIn("Set", html, "the unit from the source quotation should be printed")
        self.assertIn("Payment Terms", html)

    def test_document_embeds_the_photo(self):
        html = self._render_html(self.order)
        self.assertIn("data:image/", html, "the photo should be inlined into the document")

    def test_photo_column_appears_only_when_there_are_photos(self):
        """An always-present empty column makes a text-only quotation look broken."""
        self.assertTrue(self.order._report_has_photos())

        textless = self.env["redcube.archive.item"].create({
            "content_hash": "report-2", "name": "Transportation and crew", "rate": 1500.0,
        })
        # A product with no image either, so nothing can supply a photo.
        product = textless._get_or_create_product()
        product.image_1920 = False
        self.assertFalse(self._order_with(textless)._report_has_photos())

    def test_line_photo_prefers_the_archive_item(self):
        """The archive photo is of the structure that was actually built."""
        line = self.order.order_line
        self.assertEqual(line._report_image(), self.item.image)

    def test_line_photo_falls_back_to_the_product(self):
        product = self.env["product.product"].create({
            "name": "Hand Entered", "type": "consu", "image_1920": _png((10, 90, 160)),
        })
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": product.id, "product_uom_qty": 1, "price_unit": 100.0,
            })],
        })
        self.assertTrue(order.order_line._report_image())

    # --- Content ----------------------------------------------------------------------

    def test_name_is_separated_from_specification(self):
        """Printing them as one blob buries the product the client is being sold."""
        name, spec = self.order.order_line._report_name_and_spec()
        self.assertEqual(name, "Pirate Ship")
        self.assertEqual(len(spec), 2)
        self.assertIn("Twin commercial swings", spec[1])

    def test_empty_description_does_not_crash_the_document(self):
        line = self.order.order_line
        line.name = ""
        self.assertEqual(line._report_name_and_spec(), ("", []))

    def test_unit_prefers_the_label_from_the_source_quotation(self):
        """Odoo defaults every UoM to "Units"; the archive knows it was a Set."""
        self.assertEqual(self.order.order_line._report_unit(), "Set")

    def test_unit_falls_back_to_the_product_uom(self):
        line = self.order.order_line
        line.archive_item_id = False
        self.assertTrue(line._report_unit())

    def test_borrowed_photo_is_declared_on_the_document(self):
        """A borrowed photo shows a comparable structure, not this one. Printing it
        unlabelled on a document a client signs against would misrepresent the job."""
        self.assertFalse(self.order.order_line._report_photo_note())

        self.item.image_origin = "matched from Another Job.xlsx"
        self.assertIn("Reference image", self.order.order_line._report_photo_note())

    # --- Totals -----------------------------------------------------------------------

    def test_totals_reconcile_without_a_discount(self):
        order = self.order
        self.assertAlmostEqual(order._report_gross_subtotal(), 24000.0, places=2)
        self.assertEqual(order._report_discount_amount(), 0.0)
        self.assertAlmostEqual(order.amount_untaxed, 24000.0, places=2)

    def test_totals_reconcile_with_a_discount(self):
        order = self._order_with(self.item, discount=7.5)
        gross = order._report_gross_subtotal()
        discount = order._report_discount_amount()

        self.assertAlmostEqual(gross, 24000.0, places=2)
        self.assertAlmostEqual(discount, 1800.0, places=2)
        # What the page shows must equal what the order charges, or the document and the
        # invoice disagree.
        self.assertAlmostEqual(gross - discount, order.amount_untaxed, places=2)

    def test_section_and_note_lines_are_not_priced(self):
        """Structural rows are not things being sold and must not reach the totals."""
        self.order.write({"order_line": [(0, 0, {
            "display_type": "line_section", "name": "Play Structures",
        })]})
        self.assertEqual(len(self.order._report_lines()), 1)

    # --- Branding ---------------------------------------------------------------------

    def test_brand_falls_back_when_nothing_is_configured(self):
        """A fresh install with no configuration must still produce a usable document."""
        params = self.env["ir.config_parameter"].sudo()
        for key in ("redcube.primary_hex", "redcube.accent_hex", "redcube.payment_terms"):
            params.search([("key", "=", key)]).unlink()

        brand = self.order._report_brand()
        self.assertTrue(brand["primary"].startswith("#"))
        self.assertTrue(brand["accent"].startswith("#"))
        self.assertEqual(len(brand["terms"]), 3)

    def test_payment_terms_come_from_configuration(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "redcube.payment_terms", "Net 30 days.\n\n100% on completion.",
        )
        terms = self.order._report_brand()["terms"]
        self.assertEqual(terms, ["Net 30 days.", "100% on completion."],
                         "blank lines should not become empty bullets")
