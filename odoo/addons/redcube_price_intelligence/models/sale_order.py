# -*- coding: utf-8 -*-
"""Quoting a bespoke job from what comparable work actually sold for.

Odoo prices a line from `product.list_price`. For a company that builds one-off structures
there is no meaningful list price — the useful question is "what did we charge the last time
we built something like this, and how long ago". This puts that question on the quotation.

Rates are uplifted for age rather than used raw. A structure quoted at 12,750 two years ago is
not a 12,750 structure today, and quoting it as one silently erodes margin on every reused
price.
"""
from datetime import datetime

from odoo import _, api, fields, models

# Default annual uplift applied to a historical rate, compounded over the age of the quote.
# Overridable per search and stored in ir.config_parameter so a PM can set it once.
DEFAULT_MARKUP_RATE = 0.04


def elapsed_years(quote_date):
    """Age of a historical quote in *fractional* years.

    Fractional deliberately. A whole-year subtraction made the uplift a no-op for anything
    quoted in the current calendar year — on the real archive that was three quarters of all
    matches, every one displaying an "adjusted" rate identical to the original while the
    label still claimed a markup had been applied.
    """
    if not quote_date:
        return 0.0
    if isinstance(quote_date, str):
        try:
            quote_date = datetime.strptime(quote_date[:10], "%Y-%m-%d").date()
        except ValueError:
            return 0.0
    # A future-dated quote (clock skew, a typo'd year) must never discount the rate.
    return max(0.0, (fields.Date.today() - quote_date).days / 365.25)


def uplift(rate, quote_date, markup_rate=DEFAULT_MARKUP_RATE):
    return float(rate or 0.0) * ((1.0 + float(markup_rate or 0.0)) ** elapsed_years(quote_date))


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_open_price_archive(self):
        """Opens the archive search against this quotation."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Price from Archive"),
            "res_model": "redcube.archive.pick.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_order_id": self.id},
        }


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    # Provenance. Without it, a rate on a quotation is a number nobody can defend three months
    # later; with it, the source document and date are one click away.
    archive_item_id = fields.Many2one(
        "redcube.archive.item", string="Priced From", ondelete="set null", index=True,
        help="The historical line item this price was derived from.",
    )
    archive_similarity = fields.Float(
        string="Match", help="How closely the archive item matched what was searched for.",
    )
