@echo off
:: Windows launcher. Changes to the folder this file lives in.
cd /d "%~dp0"

set STAMP=venv\.deps-installed

if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

:: Only reinstall when requirements.txt is newer than the last successful install. Doing it on
:: every launch made startup slow and made the app unable to start without a network
:: connection, on a laptop expected to work offline in a client meeting.
set NEEDS_INSTALL=0
if not exist "%STAMP%" set NEEDS_INSTALL=1
for /f %%i in ('dir /b /o-d requirements.txt "%STAMP%" 2^>nul') do (
    if "%%i"=="requirements.txt" set NEEDS_INSTALL=1
    goto :checked
)
:checked

if "%NEEDS_INSTALL%"=="1" (
    echo Installing dependencies...
    venv\Scripts\python.exe -m pip install -r requirements.txt --quiet --disable-pip-version-check
    if errorlevel 1 (
        echo Dependency install failed. See errors above.
        pause
        exit /b 1
    )
    echo. > "%STAMP%"
)

echo Starting Smart Quotation Engine...
venv\Scripts\python.exe app.py
if errorlevel 1 (
    echo.
    echo The application exited with an error. See logs\quotation_engine.log for details.
    pause
)
