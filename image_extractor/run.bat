@echo off
:: Windows launcher. Changes to the folder this file lives in, so the store and the exports
:: always land beside the code rather than wherever the shell happened to be.
cd /d "%~dp0"

set STAMP=venv\.deps-installed

if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

:: Only reinstall when requirements.txt is newer than the last successful install — doing it
:: on every launch makes startup slow and makes the tool unable to start without a network
:: connection.
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

echo Starting Document Image Extractor...
venv\Scripts\python.exe main.py
if errorlevel 1 (
    echo.
    echo The extractor exited with an error. See above for details.
    pause
)
