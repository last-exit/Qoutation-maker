@echo off
:: Automatically change directory to the folder where this batch file is located
cd /d "%~dp0"

echo Checking dependencies...
venv\Scripts\python.exe -m pip install -r requirements.txt --quiet --disable-pip-version-check
if errorlevel 1 (
    echo Dependency install failed. See errors above.
    pause
    exit /b 1
)

echo Starting Smart Quotation Engine Desktop Application...
venv\Scripts\python.exe app.py
if errorlevel 1 (
    echo.
    echo The application exited with an error. See the traceback above.
    pause
)
