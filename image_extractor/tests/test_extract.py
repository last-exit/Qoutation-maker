"""Extraction from each document format, and what happens when a document misbehaves."""
import pytest

import extract


# --- Excel --------------------------------------------------------------------------------

def test_excel_image_is_found_with_its_anchor_cell(temp_store, make_xlsx):
    result = extract.extract_file(make_xlsx({"Costs": [("C7", (200, 30, 30))]}))

    assert result["success"] is True
    assert result["kind"] == "xlsx"
    [image] = result["images"]
    assert image["sheet"] == "Costs"
    assert image["cell"] == "C7"
    assert image["row"] == 7 and image["column"] == 3
    assert image["location"] == "Costs!C7"
    assert temp_store.exists(image["ref"])


def test_excel_reads_every_sheet_not_just_the_active_one(temp_store, make_xlsx):
    """The quotation app only parsed sheets that looked like quotations. Here every image in
    the workbook is the point, wherever it sits."""
    path = make_xlsx({
        "First": [("A1", (10, 20, 30))],
        "Second": [("B2", (40, 50, 60)), ("D9", (70, 80, 90))],
    })
    images = extract.extract_file(path)["images"]

    assert len(images) == 3
    assert {img["sheet"] for img in images} == {"First", "Second"}


def test_excel_takes_images_with_no_labelled_column(temp_store, make_xlsx):
    """A cost sheet embeds photos without ever labelling a column for them. Every one still
    has to come out."""
    images = extract.extract_file(make_xlsx({"S": [("H14", (1, 2, 3))]}))["images"]
    assert [img["cell"] for img in images] == ["H14"]


# --- Word ---------------------------------------------------------------------------------

def test_docx_finds_pictures_in_table_cells_and_body(temp_store, make_docx):
    images = extract.extract_file(make_docx())["images"]

    placements = {img["placement"] for img in images}
    assert placements == {"table-cell", "body"}

    cell_image = next(img for img in images if img["placement"] == "table-cell")
    assert cell_image["table"] == 1
    assert cell_image["row"] == 2 and cell_image["column"] == 3

    body_image = next(img for img in images if img["placement"] == "body")
    assert body_image["paragraph"] >= 1
    assert all(temp_store.exists(img["ref"]) for img in images)


def test_docx_body_only_document(temp_store, make_docx):
    images = extract.extract_file(make_docx(with_table=False))["images"]
    assert len(images) == 1
    assert images[0]["placement"] == "body"


def test_docx_with_no_pictures_is_success_not_failure(temp_store, make_docx):
    result = extract.extract_file(make_docx(with_table=False, with_body=False))
    assert result["success"] is True
    assert result["images"] == []


# --- PDF ----------------------------------------------------------------------------------

def test_pdf_images_carry_page_and_bounding_box(temp_store, make_pdf):
    # The rectangles match the fixture image's 4:3 aspect, so PyMuPDF's aspect-preserving
    # fit lands the image on exactly the box asked for.
    path = make_pdf([
        (60, 80, 160, 155, (200, 30, 30)),
        (20, 400, 120, 475, (30, 200, 60)),
    ])
    images = extract.extract_file(path)["images"]

    assert [img["page"] for img in images] == [1, 2]
    first = images[0]
    assert first["bbox"] == pytest.approx([60, 80, 160, 155], abs=1.5)
    # y0/y1 are what a consumer would band against to line an image up with nearby text.
    assert first["y0"] == pytest.approx(80, abs=1.5)
    assert first["y1"] == pytest.approx(155, abs=1.5)


def test_pdf_page_cap_is_reported_not_silent(temp_store, png_bytes, tmp_path, monkeypatch):
    """A scanned page can hold hundreds of image fragments. The cap protects the window —
    but a truncated result the user is never told about would be worse than a slow one."""
    import fitz

    monkeypatch.setattr(extract, "MAX_IMAGES_PER_PDF_PAGE", 1)

    doc = fitz.open()
    page = doc.new_page()
    for i, color in enumerate([(10, 10, 200), (200, 10, 10)]):
        page.insert_image(fitz.Rect(20 + i * 60, 20, 60 + i * 60, 60),
                          stream=png_bytes(color=color))
    path = tmp_path / "capped.pdf"
    doc.save(str(path))
    doc.close()

    result = extract.extract_file(path)
    assert len(result["images"]) == 1
    assert any("only the first 1" in w for w in result["warnings"])


# --- Batch behaviour ------------------------------------------------------------------------

def test_same_picture_in_two_documents_is_one_file_and_two_records(temp_store, make_xlsx, make_pdf):
    """Deduplication falls out of the store: two sightings, two records, one file on disk."""
    color = (123, 45, 67)
    xlsx = make_xlsx({"S": [("A1", color)]}, name="a.xlsx")
    pdf = make_pdf([(10, 10, 74, 58, color)], name="a.pdf")

    result = extract.extract_files([xlsx, pdf])

    assert result["counts"]["images"] == 2
    assert result["counts"]["unique"] == 1
    assert len({img["ref"] for img in result["images"]}) == 1
    assert temp_store.stats()["count"] == 1


def test_a_missing_file_does_not_abort_the_batch(temp_store, make_xlsx, tmp_path):
    good = make_xlsx()
    result = extract.extract_files([tmp_path / "nope.xlsx", good])

    assert result["counts"]["documents"] == 1
    assert result["counts"]["images"] == 1
    assert result["skipped"][0]["reason"] == "File not found."


def test_an_unsupported_type_is_skipped_with_a_reason(temp_store, make_xlsx, tmp_path):
    stray = tmp_path / "notes.txt"
    stray.write_text("not a document this tool reads", encoding="utf-8")

    result = extract.extract_files([stray, make_xlsx()])

    assert result["counts"]["images"] == 1
    assert "Unsupported type '.txt'" in result["skipped"][0]["reason"]


def test_a_corrupt_document_is_reported_not_raised(temp_store, tmp_path):
    broken = tmp_path / "broken.docx"
    broken.write_bytes(b"this is not a zip archive at all")

    result = extract.extract_file(broken)
    assert result["success"] is False
    assert result["error"]
    assert result["images"] == []


def test_batch_counts_add_up(temp_store, make_xlsx, make_docx, make_pdf):
    result = extract.extract_files([
        make_xlsx({"S": [("A1", (1, 2, 3)), ("B2", (4, 5, 6))]}),
        make_docx(),
        make_pdf([(10, 10, 74, 58, (9, 9, 9))]),
    ])

    assert result["counts"]["documents"] == 3
    assert result["counts"]["images"] == len(result["images"]) == 5
    assert result["counts"]["skipped"] == 0
    assert all(img["image_src"].startswith("store/") for img in result["images"])
