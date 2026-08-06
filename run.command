#!/bin/bash
# macOS double-clickable launcher.
cd "$(dirname "$0")"

STAMP="venv/.deps-installed"

if [ ! -d "venv" ]; then
    echo "Creating virtual environment for macOS..."
    python3 -m venv venv
fi

# Dependencies are installed only when requirements.txt has actually changed. Reinstalling on
# every launch made startup slow and, worse, made the app refuse to start with no network —
# on a laptop that is expected to work offline in a client meeting.
if [ ! -f "$STAMP" ] || [ requirements.txt -nt "$STAMP" ]; then
    echo "Installing dependencies..."
    venv/bin/python -m pip install -r requirements.txt --disable-pip-version-check
    if [ $? -ne 0 ]; then
        echo ""
        echo "Dependency installation failed."
        read -p "Press Enter to exit..."
        exit 1
    fi
    touch "$STAMP"
fi

echo ""
echo "Starting Smart Quotation Engine..."
venv/bin/python app.py
if [ $? -ne 0 ]; then
    echo ""
    echo "The application exited with an error. See logs/quotation_engine.log for details."
    read -p "Press Enter to exit..."
fi
