#!/bin/bash
# Points backups at Google Drive once Drive for Desktop is installed and signed in.
# Moves any existing archives across so nothing is stranded in the old location.
cd "$(dirname "$0")" || exit 1

venv/bin/python - <<'PY'
import shutil
from pathlib import Path
import backup

drives = [f for f in backup.find_cloud_folders() if f["provider"] == "Google Drive"]
if not drives:
    print("Google Drive is not mounted on this Mac yet.")
    print()
    print("Install Google Drive for Desktop and sign in:")
    print("    https://www.google.com/drive/download/")
    print()
    print("Then run this again. Backups are going to iCloud until then, which is")
    print("still off this laptop — so nothing is at risk in the meantime.")
    raise SystemExit(1)

target = Path(drives[0]["path"])
old = Path(backup.load_config()["destination"])
target.mkdir(parents=True, exist_ok=True)

moved = 0
if old.is_dir() and old.resolve() != target.resolve():
    for archive in old.glob("*" + backup.ARCHIVE_SUFFIX):
        shutil.move(str(archive), target / archive.name)
        moved += 1

backup.save_config(destination=str(target))
print(f"Backups now go to: {target}")
if moved:
    print(f"Moved {moved} existing archive(s) across.")
print()
print("Taking a fresh backup to confirm the new location works...")
result = backup.create()
print(f"  {result['path']}")
print(f"  {result['bytes'] / 1e6:.1f} MB, verified: {result['verified']}")
PY
read -r -p "Press Enter to close..."
