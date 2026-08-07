# -*- coding: utf-8 -*-
"""Quoted versus actual, per job.

A quotation says what the job should earn. What it actually costs only becomes visible once
purchase orders, crew hours and transport land against it — and only if they all land in the
same place. That place is an analytic account, created when the order is confirmed and stamped
onto every downstream cost.

The margin figures the desktop build reported were estimates: they multiplied a quoted rate by
a catalog cost that was usually missing. These are facts, because they read what was actually
spent.
"""
from odoo import _, api, fields, models


class SaleOrderJobCosting(models.Model):
    _inherit = "sale.order"

    analytic_account_id = fields.Many2one(
        "account.analytic.account", string="Job Account", copy=False, index=True,
        help="Every cost booked against this job — purchases, crew hours, transport — is "
             "recorded here, which is what makes quoted-versus-actual possible.",
    )

    quoted_revenue = fields.Monetary(
        string="Quoted", compute="_compute_job_costing", currency_field="currency_id",
    )
    actual_cost = fields.Monetary(
        string="Actual Cost", compute="_compute_job_costing", currency_field="currency_id",
    )
    actual_margin = fields.Monetary(
        string="Actual Margin", compute="_compute_job_costing", currency_field="currency_id",
    )
    actual_margin_pct = fields.Float(
        string="Margin %", compute="_compute_job_costing",
    )
    has_cost_data = fields.Boolean(
        string="Has Cost Data", compute="_compute_job_costing",
        help="False when nothing has been booked against the job yet — the margin shown is "
             "then the quoted one, not a measured one.",
    )

    @api.depends("order_line.price_subtotal", "analytic_account_id")
    def _compute_job_costing(self):
        AnalyticLine = self.env["account.analytic.line"]
        for order in self:
            order.quoted_revenue = sum(order.order_line.mapped("price_subtotal"))

            cost = 0.0
            if order.analytic_account_id:
                lines = AnalyticLine.search([
                    ("account_id", "=", order.analytic_account_id.id),
                ])
                # Analytic amounts are signed: costs are negative, revenue positive. Only the
                # spend side belongs here.
                cost = -sum(line.amount for line in lines if line.amount < 0)

            order.actual_cost = cost
            order.has_cost_data = bool(cost)
            order.actual_margin = order.quoted_revenue - cost
            order.actual_margin_pct = (
                round(100.0 * order.actual_margin / order.quoted_revenue, 1)
                if order.quoted_revenue else 0.0
            )

    def _ensure_analytic_account(self):
        """Creates the job account on demand, one per order."""
        Analytic = self.env["account.analytic.account"]
        plan = self.env["account.analytic.plan"].search([], limit=1) or \
            self.env["account.analytic.plan"].create({"name": "Jobs"})
        for order in self:
            if order.analytic_account_id:
                continue
            order.analytic_account_id = Analytic.create({
                "name": f"{order.name} — {order.partner_id.name}"[:120],
                "plan_id": plan.id,
                "partner_id": order.partner_id.id,
                "company_id": order.company_id.id,
            })
        return self.mapped("analytic_account_id")

    def action_confirm(self):
        """Confirming a quotation opens the job it will be costed against."""
        result = super().action_confirm()
        self._ensure_analytic_account()
        return result

    def action_open_job_account(self):
        self.ensure_one()
        self._ensure_analytic_account()
        return {
            "type": "ir.actions.act_window",
            "name": _("Job Costs"),
            "res_model": "account.analytic.line",
            "view_mode": "list,form",
            "domain": [("account_id", "=", self.analytic_account_id.id)],
            "context": {"default_account_id": self.analytic_account_id.id},
        }


class PurchaseOrderJobCosting(models.Model):
    _inherit = "purchase.order"

    sale_order_id = fields.Many2one(
        "sale.order", string="For Job", index=True,
        help="Links this purchase to the job it is for, so its cost lands on that job's "
             "account and shows up in quoted-versus-actual.",
    )

    @api.onchange("sale_order_id")
    def _onchange_sale_order_id(self):
        """Stamps the job's analytic account onto every line.

        Done as an onchange rather than only on confirm so the buyer can see where the cost
        is going before committing to the order.
        """
        if not self.sale_order_id:
            return
        account = self.sale_order_id.analytic_account_id or \
            self.sale_order_id._ensure_analytic_account()
        if not account:
            return
        for line in self.order_line:
            line.analytic_distribution = {str(account.id): 100.0}
