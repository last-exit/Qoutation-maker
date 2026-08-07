# -*- coding: utf-8 -*-
"""One-time import of the desktop app's data into Odoo.

Reads the SQLite stores directly rather than going through the desktop app's API, so the
import needs nothing running and can be re-run safely. Everything is matched on a natural key
so a second run updates rather than duplicates:

  * clients   — on the normalized name and phone the desktop build already computed
  * catalog   — on the normalized description
  * quotes    — on the quote number the document was printed with

Quote numbers are preserved exactly. A client holding a PDF labelled Q-7 must be able to find
Q-7 in the system; re-numbering on import would break every reference the business has already
sent out.
"""
import json
import logging
import os
import sqlite3

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

LEGACY_ROOT = "/mnt/legacy"

# The desktop lifecycle maps onto Odoo's sale order states. "Sent" is a real quotation that
# has gone out; "Won" is a confirmed order; "Lost" is cancelled.
STATUS_TO_STATE = {"Sent": "sent", "Won": "sale", "Lost": "cancel"}


class LegacyImport(models.TransientModel):
    _name = "redcube.legacy.import"
    _description = "Import Desktop App Data"

    legacy_path = fields.Char(
        string="Desktop App Folder", required=True, default=LEGACY_ROOT,
        help="Path as seen by the container. docker-compose mounts LEGACY_PATH here.",
    )
    import_clients = fields.Boolean(string="Clients", default=True)
    import_catalog = fields.Boolean(string="Catalog & Costs", default=True)
    import_quotes = fields.Boolean(string="Quotation History", default=True)

    state = fields.Selection([("setup", "Setup"), ("done", "Done")], default="setup")
    result_message = fields.Text(readonly=True)

    # --- Reading ----------------------------------------------------------------------

    @staticmethod
    def _rows(db_path, query):
        if not os.path.exists(db_path):
            return []
        # Read-only URI: the desktop app may still be running against these files, and an
        # import has no business writing to them.
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            return [dict(row) for row in conn.execute(query).fetchall()]
        except sqlite3.Error as exc:
            _logger.warning("Could not read %s: %s", db_path, exc)
            return []
        finally:
            conn.close()

    # --- Import steps -------------------------------------------------------------------

    @api.model
    def _import_clients(self, root):
        """Clients become partners, keyed on the identity the desktop build already resolved."""
        rows = self._rows(os.path.join(root, "history.db"), """
            SELECT id, name, normalized_name, phone, normalized_phone, email, merged_into
            FROM clients ORDER BY id
        """)
        Partner = self.env["res.partner"]
        mapping, created, updated = {}, 0, 0

        # Merged clients resolve to their target so no quote lands on a folded-away record.
        merged = {r["id"]: r["merged_into"] for r in rows if r.get("merged_into")}

        for row in rows:
            if row["id"] in merged:
                continue
            key = row["normalized_name"] or ""
            partner = Partner.search([("legacy_client_key", "=", key)], limit=1)
            values = {
                "name": row["name"] or key or "Unnamed Client",
                "phone": row["phone"] or False,
                "email": row["email"] or False,
                "legacy_client_key": key,
                "company_type": "company",
            }
            if partner:
                partner.write(values)
                updated += 1
            else:
                partner = Partner.create(values)
                created += 1
            mapping[row["id"]] = partner.id

        for source_id, target_id in merged.items():
            # Follow the chain so a merge of a merge still resolves.
            seen = set()
            while target_id in merged and target_id not in seen:
                seen.add(target_id)
                target_id = merged[target_id]
            if target_id in mapping:
                mapping[source_id] = mapping[target_id]

        return mapping, created, updated

    @api.model
    def _import_catalog(self, root):
        """Catalog items become products, carrying the cost price that makes margin work."""
        rows = self._rows(os.path.join(root, "catalog.db"), """
            SELECT description, normalized_description, unit, rate, cost_price, category
            FROM catalog_items
        """)
        Product = self.env["product.product"]
        created, updated = 0, 0

        for row in rows:
            key = (row.get("normalized_description") or row["description"] or "").strip().lower()
            if not key:
                continue
            product = Product.search([("archive_title_key", "=", key)], limit=1)
            values = {
                "name": (row["description"] or key)[:200],
                "archive_title_key": key,
                "type": "consu",
                "list_price": row.get("rate") or 0.0,
                "sale_ok": True,
                "purchase_ok": True,
            }
            # standard_price is the field margin reporting reads. It is a company-scoped
            # property, so it must be written after the product exists.
            cost = row.get("cost_price")
            if product:
                product.write(values)
                updated += 1
            else:
                product = Product.create(values)
                created += 1
            if cost is not None:
                product.standard_price = float(cost)

        return created, updated

    @api.model
    def _import_quotes(self, root, client_map):
        """Quotations become sale orders, preserving their printed reference."""
        rows = self._rows(os.path.join(root, "history.db"), """
            SELECT id, client_id, client_name, client_phone, venue, quote_date, items_json,
                   discount_type, discount_value, subtotal, vat, grand_total, status,
                   payment_status, amount_paid, valid_until, quote_number, created_at
            FROM quotations ORDER BY id
        """)
        Order = self.env["sale.order"]
        Partner = self.env["res.partner"]
        created, skipped = 0, 0
        mismatched = []

        for row in rows:
            reference = row.get("quote_number") or f"Q-{row['id']}"
            if Order.search([("legacy_quote_ref", "=", reference)], limit=1):
                skipped += 1
                continue

            partner_id = client_map.get(row.get("client_id"))
            if not partner_id:
                # A quote whose client row went missing still has a name on it.
                name = (row.get("client_name") or "Unknown Client").strip()
                partner = Partner.search([("name", "=", name)], limit=1) or Partner.create({
                    "name": name, "phone": row.get("client_phone") or False,
                    "company_type": "company",
                })
                partner_id = partner.id

            try:
                items = json.loads(row.get("items_json") or "[]")
            except Exception:
                items = []

            line_total = sum(
                float(i.get("qty") or 1) * float(i.get("rate") or 0)
                for i in items if isinstance(i, dict)
            )
            discount_pct = self._discount_percent(
                row.get("discount_type"), row.get("discount_value"), line_total,
            )

            order_lines = []
            for index, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                description = (item.get("description") or "Item").strip()
                product = self._product_for(description, item.get("rate") or 0.0)
                order_lines.append((0, 0, {
                    "sequence": index + 1,
                    "product_id": product.id,
                    "name": description,
                    "product_uom_qty": float(item.get("qty") or 1),
                    "price_unit": float(item.get("rate") or 0),
                    "discount": discount_pct,
                }))

            discount_line = self._discount_line_values(
                row.get("discount_type"), row.get("discount_value"), len(order_lines) + 1,
            )
            if discount_line:
                order_lines.append(discount_line)

            order = Order.create({
                "partner_id": partner_id,
                "date_order": row.get("created_at") or row.get("quote_date") or fields.Datetime.now(),
                "validity_date": row.get("valid_until") or False,
                "legacy_quote_ref": reference,
                # The printed reference is the name a client already has on paper.
                "name": reference,
                "order_line": order_lines,
            })

            state = STATUS_TO_STATE.get(row.get("status") or "Sent", "draft")
            if state == "sale":
                # Written directly rather than via action_confirm: this is a historical
                # record, and confirming would fire delivery and invoicing workflows for work
                # that finished months ago.
                order.write({"state": "sale"})
            elif state in ("sent", "cancel"):
                order.write({"state": state})

            # The imported order must total what the original document said, or a client
            # looking up their reference sees a different number than the PDF in their inbox.
            expected = float(row.get("grand_total") or 0)
            if expected:
                order.invalidate_recordset()
                drift = abs(order.amount_total - expected)
                if drift > 0.02:
                    mismatched.append(
                        f"{reference}: document {expected:,.2f} vs imported "
                        f"{order.amount_total:,.2f}"
                    )

            created += 1

        return created, skipped, mismatched

    @staticmethod
    def _discount_percent(discount_type, discount_value, line_total):
        """The per-line discount percentage, for percentage discounts only.

        A flat amount is deliberately *not* converted to a percentage here. Odoo stores the
        discount to two decimal places, so a flat 1,500 on a 30,006 order becomes 4.9990002%
        rounded to 5.00% — which discounts 1,500.30 and puts the order 30 cents away from the
        document the client is holding. Flat discounts get their own line instead, which is
        exact. See `_discount_line_values`.
        """
        value = float(discount_value or 0)
        if value <= 0 or line_total <= 0:
            return 0.0
        if discount_type == "percent":
            return min(100.0, value)
        return 0.0

    @api.model
    def _discount_product(self):
        """A single service product every imported flat discount is booked against."""
        Product = self.env["product.product"]
        product = Product.search([("archive_title_key", "=", "__discount__")], limit=1)
        if product:
            return product
        return Product.create({
            "name": "Discount",
            "archive_title_key": "__discount__",
            "type": "service",
            "list_price": 0.0,
            "sale_ok": True,
            "purchase_ok": False,
        })

    @api.model
    def _discount_line_values(self, discount_type, discount_value, sequence):
        """A negative line reproducing a flat discount exactly, or None."""
        value = float(discount_value or 0)
        if discount_type != "flat" or value <= 0:
            return None
        return (0, 0, {
            "sequence": sequence,
            "product_id": self._discount_product().id,
            "name": "Discount",
            "product_uom_qty": 1.0,
            "price_unit": -value,
        })

    @api.model
    def _product_for(self, description, rate):
        """Reuses the archive's product keying so imported history and future quotes agree."""
        title = description.splitlines()[0].strip()[:200] if description else "Item"
        key = title.lower()
        Product = self.env["product.product"]
        product = Product.search([("archive_title_key", "=", key)], limit=1)
        if product:
            return product
        return Product.create({
            "name": title, "archive_title_key": key, "type": "consu",
            "list_price": rate, "sale_ok": True, "purchase_ok": True,
        })

    # --- Entry point --------------------------------------------------------------------

    def action_import(self):
        self.ensure_one()
        root = self.legacy_path
        if not os.path.isdir(root):
            raise UserError(_(
                "Desktop app folder not found: %s\n\n"
                "Set LEGACY_PATH in odoo/.env and restart the container.", root,
            ))

        parts = []
        client_map = {}

        if self.import_clients:
            client_map, created, updated = self._import_clients(root)
            parts.append(_("Clients: %s new, %s updated.", created, updated))

        if self.import_catalog:
            created, updated = self._import_catalog(root)
            parts.append(_("Catalog: %s new, %s updated.", created, updated))

        if self.import_quotes:
            if not client_map:
                client_map, _c, _u = self._import_clients(root)
            created, skipped, mismatched = self._import_quotes(root, client_map)
            parts.append(_(
                "Quotations: %s imported, %s already present.", created, skipped,
            ))
            if mismatched:
                parts.append(_(
                    "%s quotation(s) did not reconcile against the original document total: "
                    "%s. Check the discount and tax on these before relying on them.",
                    len(mismatched), "; ".join(mismatched[:3]),
                ))

        message = " ".join(parts) or _("Nothing selected to import.")
        _logger.info("Legacy import: %s", message)
        self.write({"state": "done", "result_message": message})
        return {
            "type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id,
            "view_mode": "form", "target": "new",
        }


class ResPartner(models.Model):
    _inherit = "res.partner"

    legacy_client_key = fields.Char(
        string="Legacy Client Key", index=True, copy=False,
        help="Normalized name from the desktop app, used to match on re-import.",
    )


class SaleOrderLegacy(models.Model):
    _inherit = "sale.order"

    legacy_quote_ref = fields.Char(
        string="Legacy Reference", index=True, copy=False,
        help="Quote number printed on the original document. Preserved so a client holding "
             "a PDF can still find it here.",
    )
