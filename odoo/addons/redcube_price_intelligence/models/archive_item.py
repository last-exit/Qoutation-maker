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

    # Set the first time this item is quoted from. Lets a product show the spread of what it
    # has historically sold for, which is the number a PM actually needs when defending a
    # price rather than a single list price.
    product_id = fields.Many2one(
        "product.template", string="Product", ondelete="set null", index=True, copy=False,
    )

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
    # "none" is not the same as "low" and both are kept: "low" means the venue was guessed
    # from a subtitle and wants verifying, "none" means the document carried no venue signal
    # at all. The review queue treats them differently, so collapsing them would lose the
    # distinction between "check this" and "this needs filling in".
    venue_confidence = fields.Selection(
        [("high", "High"), ("medium", "Medium"), ("low", "Low"), ("none", "Not Found")],
        default="medium", string="Venue Confidence",
    )
    needs_review = fields.Boolean(string="Needs Review", index=True, default=False)
    # A plain stored column rather than a computed field that inspects the vector column.
    # Odoo would not dispatch to a `search=` hook on a non-stored computed boolean here, and
    # even when it did the hook scanned the whole table on every query. Set by
    # write_embeddings, which is the only thing that populates the vector.
    has_embedding = fields.Boolean(string="Embedded", index=True, default=False, copy=False)
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

    # --- Vector search ----------------------------------------------------------------

    def init(self):
        """Adds the pgvector column and its index.

        Odoo's ORM has no vector field type, so the column is managed here and queried with
        raw SQL. Keeping it on this table rather than in a separate vector store means a
        similarity search is an ordinary SQL filter — it can be combined with venue, date or
        confidence in one query, and there is no second datastore to drift out of sync.
        """
        super().init()
        self.env.cr.execute("CREATE EXTENSION IF NOT EXISTS vector")
        self.env.cr.execute(
            "ALTER TABLE redcube_archive_item ADD COLUMN IF NOT EXISTS embedding vector(%s)"
            % EMBEDDING_DIM
        )
        # HNSW over cosine distance. The embedding model returns unit vectors, so cosine and
        # inner product rank identically; cosine is used because its distance is bounded to
        # [0, 2], which makes the similarity percentage shown to a PM meaningful.
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS redcube_archive_item_embedding_idx
            ON redcube_archive_item USING hnsw (embedding vector_cosine_ops)
        """)

    @staticmethod
    def _vector_literal(vector):
        """pgvector's text input format: `[0.1,0.2,...]`.

        Elements are cast to plain Python floats first. numpy 2 renders a float32 scalar as
        `np.float32(0.023)`, so formatting a numpy array straight into the literal produces
        something Postgres rejects outright.
        """
        return "[" + ",".join(repr(float(x)) for x in vector) + "]"

    def write_embeddings(self, vectors_by_id):
        """Bulk-writes embeddings. `vectors_by_id` maps record id to a sequence of floats."""
        if not vectors_by_id:
            return 0
        # One statement rather than a round trip per row: a full archive is a few hundred
        # vectors and the per-statement overhead dominates the actual work.
        rows = [(record_id, self._vector_literal(vector))
                for record_id, vector in vectors_by_id.items()]
        self.env.cr.execute(
            """
            UPDATE redcube_archive_item AS item
            SET embedding = payload.embedding::vector, has_embedding = TRUE
            FROM (VALUES %s) AS payload(id, embedding)
            WHERE item.id = payload.id
            """ % ",".join(["(%s, %s)"] * len(rows)),
            [value for row in rows for value in row],
        )
        # The ORM cache still holds the pre-update value of has_embedding for these records.
        self.browse(list(vectors_by_id)).invalidate_recordset(["has_embedding"])
        return len(rows)

    @api.model
    def semantic_search(self, query_text, limit=10, extra_domain=None):
        """Finds archive items whose description means the same thing as `query_text`.

        Meaning rather than keywords is the entire point: the same play structure gets
        written up differently on every job, so an ILIKE search over descriptions misses the
        comparable pricing that a PM most needs to see.

        Returns a list of dicts with a `similarity` percentage, most similar first.
        """
        query_text = (query_text or "").strip()
        if not query_text:
            return []

        from ..lib.embedder import get_embedder
        vector = get_embedder().encode(query_text)
        vector_literal = str([float(x) for x in vector])

        # Restrict by the ORM first so record rules and any extra filter are honoured, then
        # rank that id set by distance. Doing it the other way round would let the vector
        # index return rows the user is not allowed to see.
        allowed_ids = self.search((extra_domain or []) + [("has_embedding", "=", True)]).ids
        if not allowed_ids:
            return []

        self.env.cr.execute(
            """
            SELECT id, 1 - (embedding <=> %s::vector) AS similarity
            FROM redcube_archive_item
            WHERE id = ANY(%s) AND embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (vector_literal, allowed_ids, vector_literal, limit),
        )
        ranked = self.env.cr.fetchall()

        by_id = {item.id: item for item in self.browse([r[0] for r in ranked])}
        results = []
        for record_id, similarity in ranked:
            item = by_id.get(record_id)
            if not item:
                continue
            results.append({
                "id": record_id,
                "title": item.title,
                "description": item.name,
                "rate": item.rate,
                "unit": item.uom_label,
                "quote_date": item.quote_date and item.quote_date.isoformat() or "",
                "venue": item.venue,
                "source_name": item.source_name,
                "similarity": round(max(0.0, min(1.0, similarity)) * 100, 1),
                "has_photo": bool(item.image_hash),
            })
        return results

    def _get_or_create_product(self):
        """The product a quotation line for this item should point at.

        Odoo requires a product on a sale line, but a bespoke builder has no catalogue to
        pick from — every structure is one-off. Rather than forcing everything onto a single
        "Custom Item" placeholder (which makes reporting by product meaningless) or minting a
        product per archive row (which fills the catalogue with 464 near-duplicates), products
        are keyed on the item's *title*. The same structure quoted across five jobs
        consolidates to one product, and a real catalogue accumulates as a by-product of
        quoting.

        Created as goods rather than a service — these are physical structures. Stock
        tracking is deliberately not set here: `is_storable` only exists once the Inventory
        module is installed, and a built-to-order structure is never picked from stock anyway.
        """
        self.ensure_one()
        title = (self.title or self.name or "Custom Item").strip()[:200]

        Product = self.env["product.product"]
        existing = Product.search([("archive_title_key", "=", title.lower())], limit=1)
        if existing:
            self.product_id = existing.product_tmpl_id
            return existing

        product = Product.create({
            "name": title,
            "archive_title_key": title.lower(),
            "type": "consu",
            "list_price": self.rate,
            "sale_ok": True,
            "purchase_ok": True,
            "uom_id": self.env.ref("uom.product_uom_unit").id,
        })
        self.product_id = product.product_tmpl_id
        return product

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
