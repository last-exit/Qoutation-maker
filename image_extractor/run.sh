#!/bin/bash
# macOS / Linux launcher. Runs from the folder this file lives in, so the store and the
# exports land beside the code.
cd "$(dirname "$0")"

STAMP="venv/.deps-installed"

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Only reinstall when requirements.txt changed, so launching offline still works.
if [ ! -f "$STAMP" ] || [ requirements.txt -nt "$STAMP" ]; then
    echo "Installing dependencies..."
    venv/bin/python -m pip install -r requirements.txt --disable-pip-version-check || {
        echo "Dependency install failed."
        exit 1
    }
    touch "$STAMP"
fi

echo "Starting Document Image Extractor..."
venv/bin/python main.py
