# -*- coding: utf-8 -*-
"""What the client actually receives.

The document is the product, for a business whose entire sales motion is emailing a
photo-rich quotation. Odoo's stock sale report is a text table — accurate, and useless for
selling a play structure nobody can picture. This carries the same information the desktop
build's document did: the product photo, the name separated from its specification, and
totals that reconcile.
"""
from odoo import api, fields, models

DEFAULT_TERMS = (
    "50% advance payment required upon confirmation of order.\n"
    "Balance 50% payable prior to event build / handover.\n"
    "Prices are exclusive of any items not explicitly listed above."
)


class SaleOrderReport(models.Model):
    _inherit = "sale.order"

    def _report_brand(self):
        """Brand colours and boilerplate, read from config so the business can change them
        without a code change — the same reason the desktop build kept company.json."""
        params = self.env["ir.config_parameter"].sudo()
        return {
            "primary": "#" + params.get_param("redcube.primary_hex", "141313"),
            "accent": "#" + params.get_param("redcube.accent_hex", "DB302F"),
            "tagline": params.get_param("redcube.tagline", "Quotation & Cost Estimate"),
            "terms": [
                line.strip()
                for line in params.get_param("redcube.payment_terms", DEFAULT_TERMS).splitlines()
                if line.strip()
            ],
        }

    def _report_lines(self):
        """Line items only — section and note rows are structural, not things being priced."""
        self.ensure_one()
        return self.order_line.filtered(lambda l: not l.display_type)

    def _report_discount_amount(self):
        """Total discount given, as a positive number, or 0.

        Shown as its own line because a client who negotiated a discount should see it
        acknowledged rather than silently folded into the unit rates.
        """
        self.ensure_one()
        return sum(
            line.product_uom_qty * line.price_unit * (line.discount or 0.0) / 100.0
            for line in self._report_lines()
        )

    def _report_gross_subtotal(self):
        """Subtotal before any discount."""
        self.ensure_one()
        return sum(line.product_uom_qty * line.price_unit for line in self._report_lines())

    def _report_has_photos(self):
        """Whether to render the photo column at all.

        A always-present empty column makes a text-only quotation look broken, and squeezes
        the description for no gain.
        """
        self.ensure_one()
        return any(line._report_image() for line in self._report_lines())


class SaleOrderLineReport(models.Model):
    _inherit = "sale.order.line"

    def _report_image(self):
        """The photo to print for this line.

        Prefers the archive item the price came from, because that is the actual structure
        that was built and photographed. Falls back to the product image for lines added by
        hand. Returns False rather than a placeholder so the template can decide.
        """
        self.ensure_one()
        if self.archive_item_id and self.archive_item_id.image:
            return self.archive_item_id.image
        return self.product_id.image_1920 or False

    def _report_name_and_spec(self):
        """Splits the line description into its product name and specification lines.

        A line's identity is its name *and* its spec. Printing them as one blob buries the
        product; separating them lets the name be emphasised while the measurements stay
        readable underneath — which is how the desktop documents read.
        """
        self.ensure_one()
        lines = [ln.rstrip() for ln in (self.name or "").split("\n")]
        lines = [ln for ln in lines if ln.strip()]
        if not lines:
            return "", []
        return lines[0].strip(), lines[1:]

    def _report_unit(self):
        """The unit to print.

        Prefers the label the source quotation actually used — the archive carries "Pcs",
        "Set", "Lump Sum" and similar, while Odoo's product UoM defaults everything to
        "Units". Printing "Units" against a lump-sum installation reads wrong to a client who
        has seen the company's previous documents.
        """
        self.ensure_one()
        if self.archive_item_id and self.archive_item_id.uom_label:
            return self.archive_item_id.uom_label
        return self.product_uom_id.name or ""

    def _report_photo_note(self):
        """Says so when a photo came from a different job.

        A borrowed photo shows a comparable structure, not this one. Printing it unlabelled
        on a document a client signs against is the difference between a reference image and
        a misrepresentation.
        """
        self.ensure_one()
        origin = self.archive_item_id.image_origin if self.archive_item_id else ""
        return "Reference image — indicative of style and finish" if origin else ""
