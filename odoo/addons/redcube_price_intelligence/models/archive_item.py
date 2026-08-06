# -*- coding: utf-8 -*-
"""The indexed historical price archive.

One record per line item recovered from a past quotation document. This is the table the
quoting workflow searches against, and it is deliberately *not* `product.template`: these are
observations of what was quoted on a particular job on a particular date, not things the
company sells from a catalogue. Several archive items commonly describe the same structure at
different prices, and that spread is the useful information.

Records are rebuilt from source documents on each re-index, so the model carries no state a
human entered — except review corrections, which live in `redcube.archive.correction` keyed by
source document and description precisely so they survive the rebuild.
"""
import hashlib

from odoo import api, fields, models

# Dimensions of all-MiniLM-L6-v2's output. Fixed by the model; changing embedding models means
# a migration, not a config change.
EMBEDDING_DIM = 384


class ArchiveItem(models.Model):
    _name = "redcube.archive.item"
    _description = "Historical Quotation Line Item"
    _order = "quote_date desc, id desc"
    # Chatter, so a PM can note why a suspicious rate is actually correct.
    _inherit = ["mail.thread"]

    # --- Identity ---------------------------------------------------------------------
    # A content hash of (source document, description, rate). The previous desktop build
    # keyed items by their position in the parse output, so re-indexing silently re-pointed
    # every id at a different product and corrections landed on the wrong item.
    content_hash = fields.Char(
        string="Content Hash", index=True, required=True, copy=False,
        help="Stable identity across re-indexing: sha256 of source file, description and rate.",
    )

    name = fields.Text(string="Description", required=True, tracking=True)
    # The first line of the description. Quote lines carry the product name on line one and a
    # spec block beneath it, and the name alone is what corresponds to a catalog entry.
    title = fields.Char(string="Title", compute="_compute_title", store=True, index=True)

    # --- Commercials ------------------------------------------------------------------
    rate = fields.Float(string="Historical Rate", digits="Product Price", tracking=True)
    uom_label = fields.Char(string="Unit", default="Pcs")
    currency_id = fields.Many2one(
        "res.currency", string="Currency",
        default=lambda self: self.env.company.currency_id,
    )

    # --- Provenance -------------------------------------------------------------------
    quote_date = fields.Date(string="Quoted On", index=True)
    venue = fields.Char(string="Venue", index=True)
    source_id = fields.Many2one(
        "redcube.archive.source", string="Source Document", ondelete="cascade", index=True,
    )
    source_name = fields.Char(related="source_id.name", store=True, string="Source File")

    # --- Photo ------------------------------------------------------------------------
    # Extracted from the source document and stored as a standard Odoo attachment, so it gets
    # the filestore, access rules and web routes for free rather than sitting as base64 in a
    # column. The hash is kept alongside so identical photos across documents collapse to one
    # stored file.
    image = fields.Image(string="Product Photo", max_width=900, max_height=900)
    image_hash = fields.Char(string="Photo Hash", index=True)
    image_origin = fields.Char(
        string="Photo Origin",
        help="Blank when the photo came from this item's own document; otherwise names the "
             "quotation it was borrowed from.",
    )

    # --- Extraction confidence --------------------------------------------------------
    rate_confidence = fields.Selection(
        [("high", "High"), ("medium", "Medium"), ("low", "Low")],
        default="medium", string="Rate Confidence",
    )
    venue_confidence = fields.Selection(
        [("high", "High"), ("medium", "Medium"), ("low", "Low")],
        default="medium", string="Venue Confidence",
    )
    needs_review = fields.Boolean(string="Needs Review", index=True, default=False)
    flag_reason = fields.Char(string="Review Reason")

    active = fields.Boolean(default=True)

    # Odoo 19 replaced the _sql_constraints list with declarative models.Constraint fields.
    _content_hash_uniq = models.Constraint(
        "unique(content_hash)",
        "Two archive items cannot share a content hash — they would be the same line item.",
    )

    @api.depends("name")
    def _compute_title(self):
        for item in self:
            for line in (item.name or "").splitlines():
                if line.strip():
                    item.title = line.strip()[:255]
                    break
            else:
                item.title = ""

    @staticmethod
    def build_content_hash(source_name, description, rate):
        """Stable identity for an item. Must match the indexer exactly."""
        key = "\x1f".join((
            str(source_name or "").strip().lower(),
            str(description or "").strip().lower(),
            f"{float(rate or 0):.4f}",
        ))
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]

    def action_view_source(self):
        """Opens the original quotation this line was read out of, so a PM can see the row in
        context before deciding whether the rate is trustworthy."""
        self.ensure_one()
        if not self.source_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": "redcube.archive.source",
            "res_id": self.source_id.id,
            "view_mode": "form",
            "target": "current",
        }
