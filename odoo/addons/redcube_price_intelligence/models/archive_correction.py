# -*- coding: utf-8 -*-
"""PM corrections to parsed line items, kept outside the rebuilt archive.

Archive items are destroyed and rebuilt from source documents on every re-index, so anything a
human fixed has to live somewhere the rebuild does not touch. Keyed by (source file,
description) rather than by item id, so a correction re-attaches to the same line even though
the item record itself is new.

`corrected_field_ids` is the load-bearing part. In the previous build every review action
snapshotted the rate, unit and venue together and the re-index re-applied all three — so
setting a venue in bulk, or merely dismissing a review flag, pinned that item's price forever
and a later price change in the source spreadsheet could never reach the system again. Only
fields a human actually edited are re-applied.
"""
from odoo import api, fields, models


class ArchiveCorrection(models.Model):
    _name = "redcube.archive.correction"
    _description = "Archive Correction"
    _order = "write_date desc"

    source_name = fields.Char(string="Source File", required=True, index=True)
    # Stored lower-cased and stripped; the same line read from the same file must match
    # regardless of how the parser happened to case it.
    description_key = fields.Char(string="Description Key", required=True, index=True)
    display_description = fields.Text(string="Description")

    rate = fields.Float(string="Corrected Rate", digits="Product Price")
    uom_label = fields.Char(string="Corrected Unit")
    venue = fields.Char(string="Corrected Venue")

    corrected_field_ids = fields.Char(
        string="Corrected Fields",
        help="Comma-separated list of the fields the PM actually edited — only these are "
             "re-applied on re-index. Empty means 'reviewed and deliberately left as-is', "
             "which clears the review flag without pinning any value.",
    )

    reviewed_by = fields.Many2one("res.users", string="Reviewed By", default=lambda s: s.env.user)

    _correction_uniq = models.Constraint(
        "unique(source_name, description_key)",
        "One correction per line item per source document.",
    )

    @api.model
    def normalize_key(self, description):
        return (description or "").strip().lower()

    def field_list(self):
        self.ensure_one()
        allowed = {"rate", "uom_label", "venue"}
        raw = (self.corrected_field_ids or "").split(",")
        return [f for f in (x.strip() for x in raw) if f in allowed]

    def apply_to(self, values):
        """Applies this correction to a freshly parsed item's values dict, in place.

        The review flag is always cleared: the record exists because a human already looked.
        """
        self.ensure_one()
        fields_to_apply = set(self.field_list())

        if "rate" in fields_to_apply:
            values["rate"] = self.rate
            values["rate_confidence"] = "high"
        if "uom_label" in fields_to_apply and self.uom_label:
            values["uom_label"] = self.uom_label
        if "venue" in fields_to_apply and self.venue:
            values["venue"] = self.venue
            values["venue_confidence"] = "high"

        values["needs_review"] = False
        values["flag_reason"] = (
            "corrected by PM: " + ", ".join(sorted(fields_to_apply))
            if fields_to_apply else "reviewed by PM - left as-is"
        )
        return values
