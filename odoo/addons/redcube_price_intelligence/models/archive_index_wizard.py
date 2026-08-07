# -*- coding: utf-8 -*-
"""The "Index Archive" dialog.

A wizard rather than a bare server action so the folder being read is visible and editable
before anything runs, and so the result — including what failed — is shown rather than
written to a log nobody opens.
"""
from odoo import _, api, fields, models


class ArchiveIndexWizard(models.TransientModel):
    _name = "redcube.archive.index.wizard"
    _description = "Index Price Archive"

    archive_path = fields.Char(
        string="Archive Folder", required=True,
        default=lambda self: self.env["redcube.archive.indexer"].archive_path(),
        help="Path as seen by the Odoo container. The host folder is bind-mounted here by "
             "docker-compose; change ARCHIVE_PATH in odoo/.env to point somewhere else.",
    )
    force = fields.Boolean(
        string="Re-read unchanged documents",
        help="Normally a document whose size and timestamp are unchanged is skipped. Tick "
             "this after a parser change rather than a document change.",
    )

    state = fields.Selection(
        [("setup", "Setup"), ("done", "Done")], default="setup",
    )
    result_message = fields.Text(string="Result", readonly=True)
    created_count = fields.Integer(readonly=True)
    updated_count = fields.Integer(readonly=True)
    removed_count = fields.Integer(readonly=True)
    total_count = fields.Integer(readonly=True)

    def action_index(self):
        self.ensure_one()
        summary = self.env["redcube.archive.indexer"].run(
            root=self.archive_path, force=self.force
        )
        # Remember the folder so the next run defaults to it.
        self.env["ir.config_parameter"].sudo().set_param(
            "redcube.archive_path", self.archive_path
        )
        self.write({
            "state": "done",
            "result_message": summary.get("message", ""),
            "created_count": summary.get("created", 0),
            "updated_count": summary.get("updated", 0),
            "removed_count": summary.get("removed", 0),
            "total_count": summary.get("indexed", 0),
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_view_archive(self):
        self.ensure_one()
        return self.env["ir.actions.act_window"]._for_xml_id(
            "redcube_price_intelligence.action_archive_item"
        )


class ArchiveSearchWizard(models.TransientModel):
    """Semantic search over the archive, standalone.

    Exists on its own before the sale.order integration so the search can be judged on its
    own terms: type how you would describe a structure to a colleague and see what
    comparable work was actually quoted at.
    """
    _name = "redcube.archive.search.wizard"
    _description = "Search Price Archive"

    query = fields.Char(string="Describe the item", required=True)
    limit = fields.Integer(string="Results", default=10)
    result_html = fields.Html(string="Matches", readonly=True, sanitize=False)

    def action_search(self):
        self.ensure_one()
        matches = self.env["redcube.archive.item"].semantic_search(self.query, limit=self.limit)
        self.result_html = self._render(matches)
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    @api.model
    def _render(self, matches):
        if not matches:
            return "<p>Nothing comparable in the archive yet. Index a folder of past " \
                   "quotations first.</p>"
        from markupsafe import Markup, escape
        rows = []
        for match in matches:
            rows.append(Markup(
                "<tr>"
                "<td style='padding:4px 10px;'><b>{sim}%</b></td>"
                "<td style='padding:4px 10px;'>{title}</td>"
                "<td style='padding:4px 10px;text-align:right;'>{rate:,.2f}</td>"
                "<td style='padding:4px 10px;'>{unit}</td>"
                "<td style='padding:4px 10px;'>{date}</td>"
                "<td style='padding:4px 10px;'>{venue}</td>"
                "<td style='padding:4px 10px;color:#888;'>{source}</td>"
                "</tr>"
            ).format(
                sim=match["similarity"], title=escape(match["title"] or ""),
                rate=match["rate"], unit=escape(match["unit"] or ""),
                date=escape(match["quote_date"] or ""), venue=escape(match["venue"] or ""),
                source=escape(match["source_name"] or ""),
            ))
        return Markup(
            "<table style='width:100%;border-collapse:collapse;'>"
            "<thead><tr style='text-align:left;border-bottom:1px solid #ddd;'>"
            "<th style='padding:4px 10px;'>Match</th><th style='padding:4px 10px;'>Item</th>"
            "<th style='padding:4px 10px;text-align:right;'>Rate</th>"
            "<th style='padding:4px 10px;'>Unit</th><th style='padding:4px 10px;'>Quoted</th>"
            "<th style='padding:4px 10px;'>Venue</th><th style='padding:4px 10px;'>Source</th>"
            "</tr></thead><tbody>{}</tbody></table>"
        ).format(Markup("").join(rows))
