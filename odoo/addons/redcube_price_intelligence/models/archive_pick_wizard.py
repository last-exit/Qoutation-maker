# -*- coding: utf-8 -*-
"""The "Price from Archive" dialog on a quotation.

Search by describing the structure, see what comparable work was actually quoted at and how
long ago, tick the lines you want, and they land on the order with the rate uplifted for age
and the photo attached.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .sale_order import DEFAULT_MARKUP_RATE, elapsed_years, uplift


class ArchivePickWizard(models.TransientModel):
    _name = "redcube.archive.pick.wizard"
    _description = "Price from Archive"

    order_id = fields.Many2one("sale.order", string="Quotation", required=True, readonly=True)
    query = fields.Char(string="Describe the item", required=True)
    limit = fields.Integer(string="Results", default=8)
    markup_rate = fields.Float(
        string="Annual Uplift", digits=(3, 4),
        default=lambda self: self._default_markup(),
        help="Compounded over the age of each historical quote. 0.04 means 4% a year.",
    )
    only_with_photo = fields.Boolean(string="Only items with a photo")
    line_ids = fields.One2many("redcube.archive.pick.line", "wizard_id", string="Matches")
    searched = fields.Boolean(default=False)

    @api.model
    def _default_markup(self):
        return float(self.env["ir.config_parameter"].sudo().get_param(
            "redcube.markup_rate", DEFAULT_MARKUP_RATE,
        ))

    def action_search(self):
        self.ensure_one()
        self.line_ids.unlink()

        domain = [("image_hash", "!=", False)] if self.only_with_photo else None
        matches = self.env["redcube.archive.item"].semantic_search(
            self.query, limit=self.limit or 8, extra_domain=domain,
        )

        Item = self.env["redcube.archive.item"]
        lines = []
        for match in matches:
            item = Item.browse(match["id"])
            lines.append((0, 0, {
                "item_id": item.id,
                "similarity": match["similarity"],
                "historical_rate": item.rate,
                "adjusted_rate": round(uplift(item.rate, item.quote_date, self.markup_rate), 2),
                "age_years": round(elapsed_years(item.quote_date), 1),
                "quantity": 1.0,
            }))

        self.write({"line_ids": lines, "searched": True})
        self.env["ir.config_parameter"].sudo().set_param("redcube.markup_rate", self.markup_rate)
        return self._reopen()

    def action_add_selected(self):
        """Adds the ticked matches to the quotation."""
        self.ensure_one()
        chosen = self.line_ids.filtered("selected")
        if not chosen:
            raise UserError(_("Tick at least one match to add it to the quotation."))

        SaleLine = self.env["sale.order.line"]
        sequence = max(self.order_id.order_line.mapped("sequence") or [0])
        for line in chosen:
            sequence += 1
            item = line.item_id
            SaleLine.create({
                "order_id": self.order_id.id,
                "sequence": sequence,
                "product_id": item._get_or_create_product().id,
                # The full description, not just the title: the spec block under the product
                # name is what the client is actually agreeing to.
                "name": item.name,
                "product_uom_qty": line.quantity,
                "price_unit": line.adjusted_rate,
                "archive_item_id": item.id,
                "archive_similarity": line.similarity,
            })

        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "res_id": self.order_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def _reopen(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }


class ArchivePickLine(models.TransientModel):
    _name = "redcube.archive.pick.line"
    _description = "Archive Match"
    _order = "similarity desc"

    wizard_id = fields.Many2one("redcube.archive.pick.wizard", required=True, ondelete="cascade")
    item_id = fields.Many2one("redcube.archive.item", string="Archive Item", required=True)
    selected = fields.Boolean(string="Add")

    title = fields.Char(related="item_id.title", string="Item", readonly=True)
    image = fields.Image(related="item_id.image", string="Photo", readonly=True)
    venue = fields.Char(related="item_id.venue", readonly=True)
    quote_date = fields.Date(related="item_id.quote_date", string="Quoted", readonly=True)
    source_name = fields.Char(related="item_id.source_name", string="Source", readonly=True)
    uom_label = fields.Char(related="item_id.uom_label", string="Unit", readonly=True)
    # Shown next to the price so a borrowed photo is never passed off as this item's own.
    image_origin = fields.Char(related="item_id.image_origin", readonly=True)
    rate_confidence = fields.Selection(related="item_id.rate_confidence", readonly=True)

    similarity = fields.Float(string="Match %", readonly=True)
    historical_rate = fields.Float(string="Quoted At", digits="Product Price", readonly=True)
    age_years = fields.Float(string="Age (yrs)", readonly=True)
    adjusted_rate = fields.Float(string="Today's Rate", digits="Product Price")
    quantity = fields.Float(string="Qty", default=1.0)
