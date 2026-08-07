# -*- coding: utf-8 -*-
{
    "name": "Red Cube Price Intelligence",
    "version": "19.0.1.0.0",
    "summary": "Price historical quotations from your own archive, with semantic search",
    "description": """
Historical Price Intelligence
=============================

Odoo prices a quotation from a product's list price. That works when you sell a catalogue.
It does not work for bespoke builds, where the honest answer to "what do we charge for this"
is "what did we charge last time we built something like it".

This module indexes the company's archive of past quotations — spreadsheets, PDFs and Word
documents — and makes it searchable by meaning rather than by keyword. From a quotation you
can search "play tower with slide and rockwall", see what comparable structures were actually
quoted at, how long ago, at which venue, and with the product photo pulled out of the original
document; then drop the line straight into the order with the rate uplifted for age.

What it adds:

* An indexed archive of historical line items, with the rate, unit, date, venue and source
  document each one came from.
* Semantic search over that archive using sentence embeddings stored in pgvector, so wording
  differences between two quotes for the same structure do not hide the match.
* Product photos extracted from the source documents, deduplicated by content hash, and
  borrowed across near-identical items that were quoted without a picture.
* A review queue for low-confidence extractions, with corrections that survive re-indexing.
""",
    "author": "Red Cube",
    "website": "https://github.com/last-exit/Qoutation-maker",
    "category": "Sales/Sales",
    "license": "LGPL-3",
    # sale_management brings quotations; product is where catalog cost/list prices live.
    # purchase and hr_timesheet bring the cost side of job costing; analytic
    # accounts are what tie a purchase or a crew hour back to the job it was for.
    "depends": ["base", "sale_management", "product", "purchase", "project",
                "hr_timesheet", "analytic"],
    "data": [
        "security/redcube_security.xml",
        "security/ir.model.access.csv",
        "views/archive_item_views.xml",
        "views/archive_source_views.xml",
        "views/wizard_views.xml",
        "views/sale_order_views.xml",
        "views/job_costing_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
