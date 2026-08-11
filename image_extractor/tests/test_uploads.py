"""Drag-and-drop, which arrives as bytes rather than paths.

A webview never hands the page a filesystem path for a dropped file, so the page reads the
file and sends it here. These pin the parts that made dropping fail silently before.
"""
import base64


def _upload(path, name=None):
    return {"name": name or path.name,
            "data": "data:application/octet-stream;base64," + base64.b64encode(path.read_bytes()).decode()}


def test_a_dropped_workbook_is_extracted(temp_store, make_xlsx):
    import main

    result = main.ExtractorApi().extract_uploads([_upload(make_xlsx({"Costs": [("C7", (1, 2, 3))]}))])

    assert result["success"] is True
    assert result["counts"]["images"] == 1
    assert result["images"][0]["cell"] == "C7"
    assert temp_store.exists(result["images"][0]["ref"])


def test_every_format_survives_the_round_trip(temp_store, make_xlsx, make_docx, make_pdf):
    import main

    uploads = [_upload(make_xlsx()), _upload(make_docx()), _upload(make_pdf())]
    result = main.ExtractorApi().extract_uploads(uploads)

    assert result["counts"]["documents"] == 3
    assert {f["kind"] for f in result["files"]} == {"xlsx", "docx", "pdf"}


def test_the_temp_directory_does_not_leak_into_what_the_user_sees(temp_store, make_xlsx):
    """The bytes are staged in a temp folder; reporting that path back would be noise at
    best and confusing at worst."""
    import main

    result = main.ExtractorApi().extract_uploads([_upload(make_xlsx(), name="Q01183.xlsx")])

    assert result["files"][0]["path"] == "Q01183.xlsx"
    assert result["images"][0]["source_path"] == "Q01183.xlsx"
    assert result["images"][0]["source_file"] == "Q01183.xlsx"


def test_the_staging_directory_is_cleaned_up(temp_store, make_xlsx, tmp_path, monkeypatch):
    import main

    created = []
    import tempfile as _tempfile

    real_mkdtemp = _tempfile.mkdtemp
    monkeypatch.setattr(main.tempfile, "mkdtemp",
                        lambda *a, **k: created.append(real_mkdtemp(*a, **k)) or created[-1])

    main.ExtractorApi().extract_uploads([_upload(make_xlsx())])

    from pathlib import Path
    assert created and not Path(created[0]).exists()


def test_a_dropped_file_keeps_only_its_name_not_a_path(temp_store, make_xlsx):
    """A name arriving as `..\\..\\something.xlsx` must not escape the staging folder."""
    import main

    result = main.ExtractorApi().extract_uploads(
        [_upload(make_xlsx(), name=r"..\..\evil.xlsx")]
    )

    assert result["success"] is True
    assert result["files"][0]["file"] == "evil.xlsx"


def test_undecodable_payload_is_skipped_not_fatal(temp_store, make_xlsx):
    import main

    result = main.ExtractorApi().extract_uploads([
        {"name": "broken.xlsx", "data": "not base64 at all!!"},
        _upload(make_xlsx()),
    ])

    assert result["success"] is True
    assert result["counts"]["images"] == 1
    assert any(s["file"] == "broken.xlsx" for s in result["skipped"])
    assert result["counts"]["skipped"] == len(result["skipped"])


def test_nothing_dropped_is_an_error_not_a_crash(temp_store):
    import main

    assert main.ExtractorApi().extract_uploads([])["success"] is False


def test_an_upload_run_can_then_be_exported_and_copied(temp_store, make_xlsx, tmp_path, monkeypatch):
    """The drop path has to leave the API in the same state the dialog path does."""
    import clipboard
    import export
    import main

    api = main.ExtractorApi()
    api.extract_uploads([_upload(make_xlsx())])

    out = export.export(api.last_result, tmp_path / "out")
    assert out["written"] == 1

    monkeypatch.setattr(clipboard, "copy_text", lambda text: (True, None))
    assert api.copy_all_images() == {"success": True, "count": 1}
