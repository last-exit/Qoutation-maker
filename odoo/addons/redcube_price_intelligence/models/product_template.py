# -*- coding: utf-8 -*-
"""Products created from the price archive.

Keyed on a normalized title so the same structure quoted across several jobs consolidates to
one product instead of accumulating near-duplicates. Without the key, matching on `name` alone
would collide with products a PM created by hand and re-point them at archive pricing.
"""
from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    archive_title_key = fields.Char(
        string="Archive Key", index=True, copy=False,
        help="Lower-cased title this product was created from, used to reuse it the next "
             "time the same structure is quoted. Empty for products entered by hand.",
    )
    archive_item_ids = fields.One2many(
        "redcube.archive.item", "product_id", string="Historical Quotes",
    )
    archive_quote_count = fields.Integer(compute="_compute_archive_stats")
    archive_rate_min = fields.Float(compute="_compute_archive_stats", digits="Product Price")
    archive_rate_max = fields.Float(compute="_compute_archive_stats", digits="Product Price")

    @api.depends("archive_item_ids.rate")
    def _compute_archive_stats(self):
        for product in self:
            rates = product.archive_item_ids.mapped("rate")
            product.archive_quote_count = len(rates)
            # The spread matters more than the average: it is the range this has actually
            # sold within, which is what a PM needs when defending a number.
            product.archive_rate_min = min(rates) if rates else 0.0
            product.archive_rate_max = max(rates) if rates else 0.0

    _archive_title_key_uniq = models.Constraint(
        "unique(archive_title_key)",
        "Two products cannot share an archive title key — they would be the same structure.",
    )

    def action_view_archive_items(self):
        """The historical quotes behind this product's price range."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Historical Quotes",
            "res_model": "redcube.archive.item",
            "view_mode": "list,form",
            "domain": [("product_id", "=", self.id)],
        }
