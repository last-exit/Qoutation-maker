"""The readable-name export and its manifest."""
import json

import export
import extract


def _run(paths):
    return extract.extract_files(paths)


def test_export_writes_readable_names_under_the_source_document(temp_store, make_xlsx, tmp_path):
    result = _run([make_xlsx({"Costs": [("C7", (200, 30, 30))]}, name="Q01183 Cost Sheet.xlsx")])
    out = export.export(result, tmp_path / "out")

    assert out["written"] == 1
    files = sorted(p.relative_to(out["out_dir"]).as_posix()
                   for p in (tmp_path / "out").rglob("*.jpg"))
    assert files == ["Q01183-Cost-Sheet/Q01183-Cost-Sheet_Costs-C7_01.jpg"]


def test_pdf_and_docx_names_say_where_the_image_came_from(temp_store, make_pdf, make_docx, tmp_path):
    result = _run([make_pdf([(10, 10, 74, 58, (1, 2, 3))], name="quote.pdf"),
                   make_docx(name="letter.docx")])
    export.export(result, tmp_path / "out")

    names = sorted(p.name for p in (tmp_path / "out").rglob("*.jpg"))
    assert names[0].startswith("letter_")
    assert any("_p1_" in n for n in names)          # pdf page
    assert any("_t1-r2c3_" in n for n in names)     # docx table cell


def test_illegal_filename_characters_are_sanitized(temp_store, make_xlsx, tmp_path):
    """Excel happily accepts a sheet name Windows will not accept as a filename — `<`, `>`,
    `"` and `|` are all legal in a sheet title."""
    result = _run([make_xlsx({'Q1 "Cost" <A>': [("A1", (5, 5, 5))]})])
    export.export(result, tmp_path / "out")

    [written] = list((tmp_path / "out").rglob("*.jpg"))
    assert not set(written.name) & set('<>:"/\\|?*')
    assert "Q1-Cost-A" in written.name


def test_a_name_collision_never_overwrites(temp_store, tmp_path, png_bytes):
    ref = temp_store.store_bytes(png_bytes())
    other = temp_store.store_bytes(png_bytes(color=(9, 9, 9)))
    # Two different images that would slugify to the same filename.
    result = {
        "images": [
            {"ref": ref, "kind": "pdf", "page": 1, "index": 1, "source_file": "a.pdf",
             "location": "Page 1", "image_src": temp_store.web_src(ref)},
            {"ref": other, "kind": "pdf", "page": 1, "index": 1, "source_file": "a.pdf",
             "location": "Page 1", "image_src": temp_store.web_src(other)},
        ],
        "files": [], "skipped": [], "warnings": [],
        "counts": {"documents": 1, "images": 2, "unique": 2, "skipped": 0},
    }
    out = export.export(result, tmp_path / "out")

    assert out["written"] == 2
    names = sorted(p.name for p in (tmp_path / "out").rglob("*.jpg"))
    assert names == ["a_p1_01-2.jpg", "a_p1_01.jpg"]


def test_one_picture_in_two_documents_is_written_once_listed_twice(temp_store, make_xlsx,
                                                                   make_pdf, tmp_path):
    color = (77, 88, 99)
    result = _run([make_xlsx({"S": [("A1", color)]}, name="a.xlsx"),
                   make_pdf([(10, 10, 74, 58, color)], name="b.pdf")])
    out = export.export(result, tmp_path / "out")

    assert out["written"] == 1
    manifest = json.loads((tmp_path / "out" / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["images"]) == 2
    exported = {img["exported_path"] for img in manifest["images"]}
    assert len(exported) == 1
    assert any(img.get("duplicate_of") for img in manifest["images"])


def test_manifest_carries_schema_counts_and_locations(temp_store, make_xlsx, make_pdf, tmp_path):
    result = _run([make_xlsx({"Costs": [("C7", (1, 2, 3))]}, name="a.xlsx"),
                   make_pdf([(10, 10, 74, 58, (4, 5, 6))], name="b.pdf")])
    export.export(result, tmp_path / "out")

    manifest = json.loads((tmp_path / "out" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == export.MANIFEST_SCHEMA
    assert manifest["generated_at"]
    assert manifest["counts"]["documents"] == 2
    assert manifest["counts"]["images"] == 2
    assert manifest["counts"]["written"] == 2
    assert manifest["counts"]["missing"] == 0

    xlsx_entry = next(i for i in manifest["images"] if i["kind"] == "xlsx")
    assert xlsx_entry["sheet"] == "Costs" and xlsx_entry["cell"] == "C7"
    assert xlsx_entry["stored_path"].endswith(".jpg")
    assert xlsx_entry["exported_path"].endswith(".jpg")

    pdf_entry = next(i for i in manifest["images"] if i["kind"] == "pdf")
    assert pdf_entry["page"] == 1 and len(pdf_entry["bbox"]) == 4


def test_skipped_documents_and_warnings_reach_the_manifest(temp_store, make_xlsx, tmp_path):
    result = _run([tmp_path / "gone.pdf", make_xlsx()])
    export.export(result, tmp_path / "out")

    manifest = json.loads((tmp_path / "out" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["skipped"][0]["reason"] == "File not found."


def test_missing_store_bytes_are_reported_not_crashed(temp_store, tmp_path):
    """The store is a directory of loose files; it can be moved out from under a run."""
    result = {
        "images": [{"ref": "0" * 64, "kind": "pdf", "page": 1, "index": 1,
                    "source_file": "a.pdf", "location": "Page 1", "image_src": ""}],
        "files": [], "skipped": [], "warnings": [],
        "counts": {"documents": 1, "images": 1, "unique": 1, "skipped": 0},
    }
    out = export.export(result, tmp_path / "out")

    assert out["written"] == 0
    assert out["missing"] == ["0" * 64]
    manifest = json.loads((tmp_path / "out" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["images"][0]["exported_path"] == ""
