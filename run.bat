@echo off
:: Automatically change directory to the folder where this batch file is located
cd /d "%~dp0"
echo Starting Red Cube Smart Quotation Engine Desktop Application...
venv\Scripts\python.exe app.py
