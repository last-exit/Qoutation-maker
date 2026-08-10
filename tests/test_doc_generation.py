"""End-to-end generation of the client-facing quotation documents.

`compute_totals` is covered in test_totals.py; this covers the step after it — actually
writing the Excel and Word files. These are the artefacts that leave the building, so the
bar here is that the file opens, carries the right money, and does not silently drop a line
item. A quotation that will not open in the client's Word is a lost job regardless of how
correct the arithmetic was.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import doc_generator as dg  # noqa: E402

openpyxl = pytest.importorskip("openpyxl")
docx = pytest.importorskip("docx")


ITEMS = [
    {"description": "Feature wall, MDF + PU spray", "qty": 2, "rate": 1500.0, "unit": "no"},
    {"description": "Reception counter", "qty": 1, "rate": 3250.5, "unit": "no"},
]
META = {
    "client_name": "Test Client",
    "project_name": "Ballroom Activation",
    "quote_number": "RC-TEST-001",
    "venue": "Test Venue",
    "date": "2026-08-10",
}


@pytest.fixture
def template(tmp_path):
    """The app ships a fallback template generator for a fresh install; use it so the test
    exercises the same path a new machine would."""
    path = tmp_path / "template.xlsx"
    dg.create_fallback_template(path)
    return path


def test_fallback_template_is_created_for_a_fresh_install(template):
    assert template.exists()
    assert openpyxl.load_workbook(str(template)).active is not None


def test_excel_quotation_is_written_and_opens(tmp_path, template):
    out = tmp_path / "quote.xlsx"

    dg.generate_excel_dynamic(ITEMS, META, template, out)

    assert out.exists() and out.stat().st_size > 0
    wb = openpyxl.load_workbook(str(out))
    assert wb.active is not None


def test_every_line_item_reaches_the_excel_sheet(tmp_path, template):
    """A dropped row is worse than a wrong total: it is invisible on the client's copy and
    the work still gets built."""
    out = tmp_path / "quote.xlsx"
    dg.generate_excel_dynamic(ITEMS, META, template, out)

    ws = openpyxl.load_workbook(str(out)).active
    text = "\n".join(
        str(cell.value) for row in ws.iter_rows() for cell in row if cell.value is not None
    )

    for item in ITEMS:
        assert item["description"] in text


def test_the_grand_total_on_the_sheet_matches_compute_totals(tmp_path, template):
    out = tmp_path / "quote.xlsx"
    dg.generate_excel_dynamic(ITEMS, META, template, out)

    expected = dg.compute_totals(ITEMS)["grand_total"]
    ws = openpyxl.load_workbook(str(out)).active
    numbers = [
        round(float(cell.value), 2)
        for row in ws.iter_rows() for cell in row
        if isinstance(cell.value, (int, float))
    ]

    assert expected in numbers, f"grand total {expected} not present in sheet numbers"


def test_word_quotation_is_written_and_opens(tmp_path):
    out = tmp_path / "quote.docx"

    dg.generate_word_dynamic(ITEMS, META, out)

    assert out.exists() and out.stat().st_size > 0
    assert docx.Document(str(out)) is not None


def test_word_quotation_carries_the_client_and_every_item(tmp_path):
    out = tmp_path / "quote.docx"
    dg.generate_word_dynamic(ITEMS, META, out)

    doc = docx.Document(str(out))
    text = "\n".join(p.text for p in doc.paragraphs)
    for table in doc.tables:
        for row in table.rows:
            text += "\n" + "\n".join(c.text for c in row.cells)

    assert META["client_name"] in text
    for item in ITEMS:
        assert item["description"] in text


def test_word_quotation_is_a4_not_us_letter(tmp_path):
    """python-docx defaults to Letter, which is the wrong paper for a UAE business and
    shifts every column width the layout assumes."""
    out = tmp_path / "quote.docx"
    dg.generate_word_dynamic(ITEMS, META, out)

    section = docx.Document(str(out)).sections[0]
    assert section.page_width == pytest.approx(7560000, rel=0.02)   # 210mm in EMU


def test_an_empty_quotation_still_produces_a_document(tmp_path, template):
    """The PM can save a draft before adding lines; that must not raise."""
    out_x = tmp_path / "empty.xlsx"
    out_w = tmp_path / "empty.docx"

    dg.generate_excel_dynamic([], META, template, out_x)
    dg.generate_word_dynamic([], META, out_w)

    assert out_x.exists()
    assert out_w.exists()


def test_company_branding_is_loaded_from_config():
    """One install serves one company; if this ever comes back empty the masthead and the
    document's accent colours silently fall back to nothing."""
    assert dg.COMPANY.get("name")
    assert dg.COMPANY.get("primary_hex")
    bytes.fromhex(dg.COMPANY["primary_hex"])   # must be valid hex, or Word generation raises
    bytes.fromhex(dg.COMPANY["accent_hex"])
