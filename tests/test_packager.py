"""Packaging the app for another machine.

The test that matters most here is the negative one. This folder holds live client data —
invoices, history, the search index — and a packaging routine that ships any of it to
whoever receives the zip is a data breach, not a bug. The allowlist exists for that reason
and these tests are what keep it honest.
"""

import os
import stat
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import packager  # noqa: E402


class TestNothingPrivateIsShipped:
    def test_no_database_ever_enters_the_package(self):
        included = [r for _, r in packager.collect_files()]
        assert not [f for f in included
                    if f.suffix.lower() in (".db", ".sqlite", ".sqlite3",
                                            ".db-wal", ".db-shm")]

    def test_the_search_index_and_backups_are_left_behind(self):
        names = [str(r).replace("\\", "/") for _, r in packager.collect_files()]
        assert not [n for n in names
                    if n.startswith(("chroma_db", "backups", "graphify-out", "venv"))]

    def test_real_credentials_are_excluded_but_the_template_travels(self):
        names = [r.name for _, r in packager.collect_files()]
        assert "credentials.json" not in names
        assert "credentials.json.template" in names

    def test_an_unknown_file_type_is_not_swept_in(self):
        """The rule is an allowlist: anything unrecognised stays out by default."""
        assert packager._is_safe(__import__("pathlib").Path("secrets.env")) is False
        assert packager._is_safe(__import__("pathlib").Path("chroma_db/x.bin")) is False


class TestThePackageIsComplete:
    def test_the_app_itself_is_there(self, tmp_path):
        target, _, _ = packager.build(destination=tmp_path / "p.zip")
        names = zipfile.ZipFile(target).namelist()
        for needed in ("app.py", "index.html", "app.js", "style.css",
                       "requirements.txt", "calculators.py"):
            assert any(n.endswith(needed) for n in names), needed

    def test_the_rate_card_travels_so_prices_survive(self, tmp_path):
        target, _, _ = packager.build(destination=tmp_path / "p.zip")
        names = zipfile.ZipFile(target).namelist()
        assert any("master_rate_card" in n for n in names)

    def test_both_platforms_get_a_one_click_setup(self, tmp_path):
        target, _, _ = packager.build(destination=tmp_path / "p.zip")
        names = [n.split("/")[-1] for n in zipfile.ZipFile(target).namelist()]
        assert "Setup Windows.bat" in names
        assert "Setup Mac or Linux.command" in names
        assert "READ ME FIRST.md" in names

    def test_the_mac_script_is_executable(self, tmp_path):
        """Without the executable bit a double-click opens it in a text editor."""
        target, _, _ = packager.build(destination=tmp_path / "p.zip")
        archive = zipfile.ZipFile(target)
        info = next(i for i in archive.infolist()
                    if i.filename.endswith("Setup Mac or Linux.command"))
        assert (info.external_attr >> 16) & stat.S_IXUSR
