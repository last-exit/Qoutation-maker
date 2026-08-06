#!/bin/bash
# Linux / terminal launcher.
cd "$(dirname "$0")"

STAMP="venv/.deps-installed"

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Only reinstall when requirements.txt changed — see run.command for why.
if [ ! -f "$STAMP" ] || [ requirements.txt -nt "$STAMP" ]; then
    echo "Installing dependencies..."
    venv/bin/python -m pip install -r requirements.txt --disable-pip-version-check || {
        echo "Dependency install failed."
        exit 1
    }
    touch "$STAMP"
fi

echo "Starting Smart Quotation Engine..."
venv/bin/python app.py
