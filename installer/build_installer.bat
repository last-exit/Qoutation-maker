@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0\.."
title Quotation Engine - Build Installer

echo.
echo   ============================================
echo    Building the Quotation Engine installer
echo   ============================================
echo.
echo   This takes 15-30 minutes and produces a ~2 GB installer.
echo.

:: ---------------------------------------------------------------------------------------
:: Python version. onnxruntime 1.19.2 publishes wheels for CPython 3.8 - 3.12 only, so on
:: 3.13 there is no onnxruntime to install, let alone bundle. Catch it here rather than
:: twenty minutes into a build.
:: ---------------------------------------------------------------------------------------
where python >nul 2>nul
if errorlevel 1 (
  echo   [X] Python was not found on PATH.
  echo       Install Python 3.11 or 3.12 from https://python.org/downloads
  echo       and tick "Add Python to PATH".
  goto :fail
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
for /f "tokens=1,2 delims=." %%a in ("!PYVER!") do (
  set PYMAJOR=%%a
  set PYMINOR=%%b
)
echo   Python !PYVER!
if not "!PYMAJOR!"=="3" goto :badpython
if !PYMINOR! LSS 8 goto :badpython
if !PYMINOR! GTR 12 goto :badpython
goto :pythonok

:badpython
echo.
echo   [X] Python !PYVER! cannot be used for this build.
echo       onnxruntime 1.19.2 ships wheels for CPython 3.8 - 3.12 only.
echo       Install Python 3.12 and run this again.
goto :fail

:pythonok

:: ---------------------------------------------------------------------------------------
:: Build environment. Kept separate from any venv used for development so that a stray
:: locally-installed package cannot end up inside the shipped bundle.
:: ---------------------------------------------------------------------------------------
if not exist build-venv (
  echo   Creating the build environment...
  python -m venv build-venv || goto :fail
)

echo   Installing dependencies...
build-venv\Scripts\python.exe -m pip install --upgrade pip --quiet || goto :fail
build-venv\Scripts\python.exe -m pip install -r requirements.txt --quiet || goto :fail

:: PyInstaller 6+ is required: the bundled torch hook depends on module_collection_mode,
:: which older versions do not support. hooks-contrib carries the webview, onnxruntime,
:: torch, cv2 and easyocr hooks this build relies on.
build-venv\Scripts\python.exe -m pip install --quiet "pyinstaller>=6.0" pyinstaller-hooks-contrib || goto :fail

:: ---------------------------------------------------------------------------------------
echo.
echo   Fetching models (needed for the app to work offline)...
build-venv\Scripts\python.exe installer\fetch_models.py || goto :fail

echo.
echo   Generating the application icon...
build-venv\Scripts\python.exe tools\make_icon.py || goto :fail

:: ---------------------------------------------------------------------------------------
echo.
echo   Freezing the application (this is the slow part)...
rmdir /s /q build 2>nul
rmdir /s /q dist\QuotationEngine 2>nul
build-venv\Scripts\python.exe -m PyInstaller installer\quotation_engine.spec --noconfirm || goto :fail

if not exist "dist\QuotationEngine\QuotationEngine.exe" (
  echo   [X] PyInstaller finished but produced no executable.
  goto :fail
)

:: The chromadb schemas directory is the one bundled file whose absence does not show up
:: until an embedding function is constructed at runtime, so check for it explicitly rather
:: than discovering it on the PM's machine.
if not exist "dist\QuotationEngine\_internal\schemas\embedding_functions" (
  echo.
  echo   [X] chromadb's schemas\embedding_functions is missing from the bundle.
  echo       Search would fail at runtime. Check the datas entry in the spec file.
  goto :fail
)
if not exist "dist\QuotationEngine\_internal\models\all-MiniLM-L6-v2\model.onnx" (
  echo   [X] The search model is missing from the bundle.
  goto :fail
)
if not exist "dist\QuotationEngine\_internal\easyocr_models\craft_mlt_25k.pth" (
  echo   [X] The OCR models are missing from the bundle.
  goto :fail
)

:: ---------------------------------------------------------------------------------------
:: The WebView2 bootstrapper. Small, and the app shows no window without the runtime.
:: ---------------------------------------------------------------------------------------
if not exist "installer\redist\MicrosoftEdgeWebview2Setup.exe" (
  echo.
  echo   Downloading the WebView2 bootstrapper...
  if not exist "installer\redist" mkdir "installer\redist"
  powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile 'installer\redist\MicrosoftEdgeWebview2Setup.exe' } catch { exit 1 }"
  if errorlevel 1 (
    echo   [X] Could not download the WebView2 bootstrapper.
    echo       Fetch it by hand from https://developer.microsoft.com/microsoft-edge/webview2/
    echo       and save it as installer\redist\MicrosoftEdgeWebview2Setup.exe
    goto :fail
  )
)

:: ---------------------------------------------------------------------------------------
echo.
echo   Building the installer...
set ISCC=
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe
if "!ISCC!"=="" (
  echo.
  echo   [X] Inno Setup 6 was not found.
  echo       Install it from https://jrsoftware.org/isdl.php and run this again.
  echo       The frozen app in dist\QuotationEngine\ is fine - only the wizard is missing.
  goto :fail
)

"!ISCC!" installer\quotation_engine.iss || goto :fail

echo.
echo   ============================================
echo    Done.
echo   ============================================
echo.
for %%f in (dist\installer\*.exe) do echo    %%f  (%%~zf bytes^)
echo.
echo   Test it on a machine that has never had Python installed.
echo.
pause
exit /b 0

:fail
echo.
echo   Build failed. The messages above say where.
echo.
pause
exit /b 1
