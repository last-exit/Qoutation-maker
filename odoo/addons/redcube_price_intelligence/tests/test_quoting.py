# -*- coding: utf-8 -*-
"""Quoting from the archive, the legacy import, and job costing."""
import json
import os
import sqlite3
import tempfile

from odoo import fields
from odoo.tests import TransactionCase, tagged

from ..models.sale_order import elapsed_years, uplift


@tagged("post_install", "-at_install", "redcube_price_intelligence")
class TestAgeUplift(TransactionCase):

    def test_uplift_compounds_over_fractional_years(self):
        """Whole-year arithmetic made the uplift a no-op for anything quoted this year — on
        the real archive that was three quarters of all matches, every one showing an
        'adjusted' rate identical to the original."""
        # A year is 365.25 days so leap years do not accumulate a drift, which means
        # "730 days ago" is very slightly under two years. Assert the actual contract —
        # compounding over the measured age — rather than a rounded-off approximation.
        two_years_ago = fields.Date.subtract(fields.Date.today(), days=730)
        years = elapsed_years(two_years_ago)
        self.assertAlmostEqual(years, 2.0, places=1)
        self.assertAlmostEqual(
            uplift(1000.0, two_years_ago, 0.04), 1000.0 * 1.04 ** years, places=6,
        )
        # Compounded, not simple: two years must beat two single-year uplifts added on.
        self.assertGreater(uplift(1000.0, two_years_ago, 0.04), 1080.0)

        six_months_ago = fields.Date.subtract(fields.Date.today(), days=182)
        adjusted = uplift(1000.0, six_months_ago, 0.04)
        self.assertGreater(adjusted, 1000.0)
        self.assertLess(adjusted, 1040.0, "half a year should earn about half the uplift")

    def test_future_dated_quote_is_never_discounted(self):
        """A typo'd year or clock skew must not reduce a price."""
        next_year = fields.Date.add(fields.Date.today(), days=365)
        self.assertEqual(uplift(1000.0, next_year, 0.04), 1000.0)
        self.assertEqual(elapsed_years(next_year), 0.0)

    def test_missing_date_leaves_the_rate_alone(self):
        self.assertEqual(uplift(1000.0, False, 0.04), 1000.0)

    def test_zero_markup_is_identity(self):
        old = fields.Date.subtract(fields.Date.today(), days=1000)
        self.assertAlmostEqual(uplift(1000.0, old, 0.0), 1000.0, places=6)


@tagged("post_install", "-at_install", "redcube_price_intelligence")
class TestQuotingFromArchive(TransactionCase):

    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create({"name": "Test Client"})
        self.item = self.env["redcube.archive.item"].create({
            "content_hash": "quote-test-1",
            "name": "Pirate Ship\nL5.8 x W3.4m\n- Twin swings",
            "rate": 10000.0,
            "quote_date": fields.Date.subtract(fields.Date.today(), days=365),
            "uom_label": "Pcs",
        })

    def test_product_is_created_from_the_title_and_reused(self):
        """Keyed on title so the same structure across five jobs is one product, not five."""
        first = self.item._get_or_create_product()
        self.assertEqual(first.name, "Pirate Ship")

        twin = self.env["redcube.archive.item"].create({
            "content_hash": "quote-test-2", "name": "Pirate Ship\ndifferent spec", "rate": 12000.0,
        })
        self.assertEqual(twin._get_or_create_product(), first,
                         "the same title must not mint a second product")

    def test_product_records_the_spread_it_has_sold_within(self):
        self.item._get_or_create_product()
        twin = self.env["redcube.archive.item"].create({
            "content_hash": "quote-test-3", "name": "Pirate Ship\nlarger", "rate": 15000.0,
        })
        twin._get_or_create_product()

        template = self.item.product_id
        self.assertEqual(template.archive_quote_count, 2)
        self.assertEqual(template.archive_rate_min, 10000.0)
        self.assertEqual(template.archive_rate_max, 15000.0)

    def test_adding_a_match_puts_an_uplifted_line_on_the_order(self):
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        wizard = self.env["redcube.archive.pick.wizard"].create({
            "order_id": order.id, "query": "pirate ship", "markup_rate": 0.04,
        })
        line = self.env["redcube.archive.pick.line"].create({
            "wizard_id": wizard.id, "item_id": self.item.id, "selected": True,
            "historical_rate": self.item.rate, "quantity": 2.0,
            "adjusted_rate": round(uplift(self.item.rate, self.item.quote_date, 0.04), 2),
            "similarity": 88.0,
        })
        wizard.action_add_selected()

        self.assertEqual(len(order.order_line), 1)
        sale_line = order.order_line
        self.assertEqual(sale_line.product_uom_qty, 2.0)
        self.assertAlmostEqual(sale_line.price_unit, line.adjusted_rate, places=2)
        # The full description, not just the title: the spec block is what the client agrees to.
        self.assertIn("Twin swings", sale_line.name)
        # Provenance, so the price can be defended three months later.
        self.assertEqual(sale_line.archive_item_id, self.item)
        self.assertEqual(sale_line.archive_similarity, 88.0)

    def test_adding_nothing_selected_is_refused(self):
        from odoo.exceptions import UserError
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        wizard = self.env["redcube.archive.pick.wizard"].create({
            "order_id": order.id, "query": "pirate ship",
        })
        with self.assertRaises(UserError):
            wizard.action_add_selected()


@tagged("post_install", "-at_install", "redcube_price_intelligence")
class TestLegacyImport(TransactionCase):

    def _legacy_db(self, discount_type="percent", discount_value=5.0):
        """A miniature of the desktop app's history.db."""
        folder = tempfile.mkdtemp(prefix="legacy-")
        path = os.path.join(folder, "history.db")
        conn = sqlite3.connect(path)
        conn.execute("""CREATE TABLE clients (
            id INTEGER PRIMARY KEY, name TEXT, normalized_name TEXT, phone TEXT,
            normalized_phone TEXT, email TEXT, merged_into INTEGER)""")
        conn.execute("INSERT INTO clients VALUES (1,'Acme360','acme360','0501234567','501234567',NULL,NULL)")
        conn.execute("""CREATE TABLE quotations (
            id INTEGER PRIMARY KEY, client_id INTEGER, client_name TEXT, client_phone TEXT,
            venue TEXT, quote_date TEXT, items_json TEXT, discount_type TEXT,
            discount_value REAL, subtotal REAL, vat REAL, grand_total REAL, status TEXT,
            payment_status TEXT, amount_paid REAL, valid_until TEXT, quote_number TEXT,
            created_at TEXT)""")
        items = json.dumps([
            {"description": "Pirate Ship", "qty": 1, "rate": 20000.0},
            {"description": "Delivery", "qty": 1, "rate": 10006.0},
        ])
        line_total = 30006.0
        discounted = line_total * (1 - discount_value / 100.0) if discount_type == "percent" \
            else line_total - discount_value
        grand = round(discounted * 1.05, 2)
        conn.execute(
            "INSERT INTO quotations VALUES (1,1,'Acme360','0501234567','Kite Beach','2026-01-01',"
            "?,?,?,?,?,?,'Sent','Unpaid',0,'2026-01-15','Q-7','2026-01-01 10:00:00')",
            (items, discount_type, discount_value, line_total, round(discounted * 0.05, 2), grand),
        )
        conn.commit()
        conn.close()
        return folder, grand

    def test_import_preserves_the_printed_quote_reference(self):
        """A client holding a PDF labelled Q-7 must find Q-7 here. Re-numbering on import
        would break every reference already sent out."""
        folder, _grand = self._legacy_db()
        wizard = self.env["redcube.legacy.import"].create({"legacy_path": folder})
        wizard.action_import()

        order = self.env["sale.order"].search([("legacy_quote_ref", "=", "Q-7")], limit=1)
        self.assertTrue(order)
        self.assertEqual(order.name, "Q-7")
        self.assertEqual(order.partner_id.name, "Acme360")
        self.assertEqual(len(order.order_line), 2)

    def test_percent_discount_reproduces_the_document_total(self):
        folder, grand = self._legacy_db("percent", 5.0)
        self.env["redcube.legacy.import"].create({"legacy_path": folder}).action_import()

        order = self.env["sale.order"].search([("legacy_quote_ref", "=", "Q-7")], limit=1)
        # A cent of drift is expected: the two systems round the tax on a discounted
        # subtotal differently at the last float bit. Anything larger is a real discrepancy,
        # which is why the importer reconciles at the same tolerance.
        self.assertLess(abs(order.amount_total - grand), 0.02)

    def test_flat_discount_reproduces_the_document_total(self):
        """A flat amount gets its own line rather than being converted to a percentage.

        Odoo stores a discount to two decimals, so a flat 1,500 on a 30,006 order becomes
        5.00% and discounts 1,500.30 — putting the order 30 cents from the client's PDF.
        """
        folder, grand = self._legacy_db("flat", 1500.0)
        self.env["redcube.legacy.import"].create({"legacy_path": folder}).action_import()

        order = self.env["sale.order"].search([("legacy_quote_ref", "=", "Q-7")], limit=1)
        self.assertLess(abs(order.amount_total - grand), 0.02)
        self.assertTrue(order.order_line.filtered(lambda l: l.price_unit < 0),
                        "the flat discount should be an explicit line")

    def test_reimport_does_not_duplicate(self):
        folder, _grand = self._legacy_db()
        Import = self.env["redcube.legacy.import"]
        Import.create({"legacy_path": folder}).action_import()
        wizard = Import.create({"legacy_path": folder})
        wizard.action_import()

        self.assertEqual(
            self.env["sale.order"].search_count([("legacy_quote_ref", "=", "Q-7")]), 1,
        )
        self.assertIn("already present", wizard.result_message)

    def test_missing_folder_is_refused_with_something_actionable(self):
        from odoo.exceptions import UserError
        wizard = self.env["redcube.legacy.import"].create({"legacy_path": "/no/such/folder"})
        with self.assertRaises(UserError):
            wizard.action_import()

    def test_discount_percent_conversion(self):
        Import = self.env["redcube.legacy.import"]
        self.assertEqual(Import._discount_percent("percent", 5.0, 1000.0), 5.0)
        # A flat amount deliberately yields no percentage — Odoo's two-decimal discount field
        # cannot represent it exactly, so it becomes its own line instead.
        self.assertEqual(Import._discount_percent("flat", 250.0, 1000.0), 0.0)
        self.assertEqual(Import._discount_percent(None, 250.0, 1000.0), 0.0)
        self.assertEqual(Import._discount_percent("percent", 5.0, 0.0), 0.0)
        # A percentage over 100 would invert the price.
        self.assertEqual(Import._discount_percent("percent", 150.0, 1000.0), 100.0)

    def test_flat_discount_line_is_exact(self):
        Import = self.env["redcube.legacy.import"]
        line = Import._discount_line_values("flat", 1500.0, 3)
        self.assertEqual(line[2]["price_unit"], -1500.0)
        self.assertIsNone(Import._discount_line_values("percent", 5.0, 3))
        self.assertIsNone(Import._discount_line_values("flat", 0.0, 3))


@tagged("post_install", "-at_install", "redcube_price_intelligence")
class TestJobCosting(TransactionCase):

    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create({"name": "Job Client"})
        self.product = self.env["product.product"].create({
            "name": "Play Tower", "type": "consu", "list_price": 20000.0,
        })
        self.order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": self.product.id, "product_uom_qty": 1, "price_unit": 20000.0,
            })],
        })

    def test_confirming_opens_a_job_account(self):
        self.assertFalse(self.order.analytic_account_id)
        self.order.action_confirm()
        self.assertTrue(self.order.analytic_account_id,
                        "costs have nowhere to land without a job account")

    def test_margin_is_quoted_until_costs_are_booked(self):
        self.order.action_confirm()
        self.assertFalse(self.order.has_cost_data)
        self.assertEqual(self.order.actual_cost, 0.0)
        self.assertEqual(self.order.actual_margin, self.order.quoted_revenue)

    def test_booked_costs_produce_a_measured_margin(self):
        self.order.action_confirm()
        for amount, label in ((-11000.0, "Timber"), (-2400.0, "Install crew")):
            self.env["account.analytic.line"].create({
                "name": label, "account_id": self.order.analytic_account_id.id,
                "amount": amount, "date": fields.Date.today(),
            })
        self.order.invalidate_recordset()

        self.assertTrue(self.order.has_cost_data)
        self.assertEqual(self.order.actual_cost, 13400.0)
        self.assertEqual(self.order.actual_margin, 6600.0)
        self.assertAlmostEqual(self.order.actual_margin_pct, 33.0, places=1)

    def test_revenue_postings_are_not_counted_as_cost(self):
        """Analytic amounts are signed; only the spend side is cost."""
        self.order.action_confirm()
        self.env["account.analytic.line"].create({
            "name": "Deposit received", "account_id": self.order.analytic_account_id.id,
            "amount": 5000.0, "date": fields.Date.today(),
        })
        self.order.invalidate_recordset()
        self.assertEqual(self.order.actual_cost, 0.0)

    def test_purchase_linked_to_a_job_gets_its_analytic_account(self):
        self.order.action_confirm()
        supplier = self.env["res.partner"].create({"name": "Supplier", "supplier_rank": 1})
        po = self.env["purchase.order"].create({
            "partner_id": supplier.id,
            "sale_order_id": self.order.id,
            "order_line": [(0, 0, {
                "product_id": self.product.id, "name": "Timber", "product_qty": 1,
                "price_unit": 11000.0, "date_planned": fields.Datetime.now(),
            })],
        })
        po._onchange_sale_order_id()

        account_id = str(self.order.analytic_account_id.id)
        self.assertEqual(po.order_line.analytic_distribution, {account_id: 100.0},
                         "without this the supplier cost never reaches the job")
