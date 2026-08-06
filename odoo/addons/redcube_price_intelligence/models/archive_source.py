# -*- coding: utf-8 -*-
"""Source documents the price archive was built from.

Tracked as records rather than bare filenames for two reasons. Venue is a property of the job
document, not of each line, so correcting it once has to apply to every line that came from
that file. And when a sync silently reads fewer files than expected, the only way to notice is
to have a list of what was actually read and when.
"""
from odoo import fields, models


class ArchiveSource(models.Model):
    _name = "redcube.archive.source"
    _description = "Archive Source Document"
    _order = "document_date desc, name"

    name = fields.Char(string="File Name", required=True, index=True)
    # Kept relative to the configured archive root. An absolute path baked into the database
    # breaks the moment the archive moves between a laptop folder, an external disk and a NAS
    # share — which is exactly the move being planned.
    relative_path = fields.Char(string="Path In Archive")
    file_type = fields.Selection(
        [("xlsx", "Excel"), ("pdf", "PDF"), ("docx", "Word")], string="Type",
    )

    document_date = fields.Date(string="Document Date")
    venue = fields.Char(string="Venue")

    item_ids = fields.One2many("redcube.archive.item", "source_id", string="Line Items")
    item_count = fields.Integer(compute="_compute_counts", store=True)
    photo_count = fields.Integer(compute="_compute_counts", store=True)

    last_indexed = fields.Datetime(string="Last Indexed")
    # Detects a document that changed on disk since it was last read, so a re-index can skip
    # everything untouched instead of re-parsing the whole archive every time.
    content_fingerprint = fields.Char(
        string="Fingerprint", help="Hash of file size and modification time at last index.",
    )

    notes = fields.Text()

    def _compute_counts(self):
        for source in self:
            source.item_count = len(source.item_ids)
            source.photo_count = len(source.item_ids.filtered("image_hash"))

    _name_uniq = models.Constraint(
        "unique(name)", "Each source document is indexed once.",
    )
