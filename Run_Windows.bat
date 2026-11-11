@echo off
setlocal EnableDelayedExpansion
title Faery Good Transcriber Launcher
cd /d "%~dp0"

echo ==================================================
echo   Faery Good Transcriber - Windows Launcher
echo ==================================================

:: 1. Validate virtual environment if it exists
if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
    if errorlevel 1 (
        echo [Notice] Outdated or incompatible Python found in .venv. Resetting virtual environment...
        rmdir /s /q ".venv" >nul 2>&1
    ) else (
        .venv\Scripts\python.exe -c "import customtkinter, faster_whisper, imageio_ffmpeg, PIL, yt_dlp, yt_dlp_ejs, deno, sounddevice, pygame" >nul 2>&1
        if not errorlevel 1 (
            echo Starting Faery Good Transcriber...
            call .venv\Scripts\activate.bat
            python app.py
            if errorlevel 1 goto :runtime_error
            goto :end
        )
        echo Existing virtual environment needs dependency setup...
    )
)

:: 2. Check if Python 3.10+ is installed on this PC
set "PY_CMD="

:: Check python in system PATH
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1 && set "PY_CMD=python"

:: Check py -3 launcher in system PATH
if not defined PY_CMD (
    py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1 && set "PY_CMD=py -3"
)

:: Check standard Windows user install locations (if user omitted 'Add to PATH' during install)
if not defined PY_CMD (
    for %%V in (313 312 311 310) do (
        if not defined PY_CMD (
            if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
                "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1 && set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
            )
        )
    )
)

:: Check Program Files install locations
if not defined PY_CMD (
    for %%V in (313 312 311 310) do (
        if not defined PY_CMD (
            if exist "%ProgramFiles%\Python%%V\python.exe" (
                "%ProgramFiles%\Python%%V\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1 && set "PY_CMD=%ProgramFiles%\Python%%V\python.exe"
            )
        )
    )
)

:: 3. If Python 3.10+ is missing, pop up friendly native Windows GUI alert with 1-click download link
if not defined PY_CMD (
    echo [Notice] Python 3.10 or newer was not detected on this computer.
    powershell -NoProfile -ExecutionPolicy Bypass -Command "[void][System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms'); $m = 'Faery Good Transcriber requires Python 3.10 or newer to run on Windows.' + [Environment]::NewLine + [Environment]::NewLine + 'Would you like to open the official Python download page now?' + [Environment]::NewLine + [Environment]::NewLine + '(Tip: When running the installer, remember to check the box: Add python.exe to PATH)'; $r = [System.Windows.Forms.MessageBox]::Show($m, 'Python 3.10+ Required - Faery Good Transcriber', [System.Windows.Forms.MessageBoxButtons]::YesNo, [System.Windows.Forms.MessageBoxIcon]::Information); if ($r -eq [System.Windows.Forms.DialogResult]::Yes) { Start-Process 'https://www.python.org/downloads/' }"
    goto :end
)

:: 4. First-time setup: initialize virtual environment and install components
echo.
echo Welcome! Preparing your Transcriber for the first time...
echo This one-time setup usually takes about 1-2 minutes.
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Initializing clean Python virtual environment (.venv)...
    %PY_CMD% -m venv .venv
    if errorlevel 1 (
        echo [Error] Could not initialize virtual environment.
        powershell -NoProfile -ExecutionPolicy Bypass -Command "[void][System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms'); [System.Windows.Forms.MessageBox]::Show('Failed to create a local virtual environment (.venv).' + [Environment]::NewLine + [Environment]::NewLine + 'Please ensure you have write permissions in this folder and that all files were extracted from the ZIP archive.', 'Setup Notice - Faery Good Transcriber', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Warning) | Out-Null"
        goto :end
    )
)

call .venv\Scripts\activate.bat
echo Installing required components...
python -m pip install --upgrade pip -q
pip install -r requirements.txt -q
if errorlevel 1 (
    echo [Error] Dependency installation failed.
    echo Please check the error output above, verify your internet connection, and ensure Python >= 3.10 is installed.
    powershell -NoProfile -ExecutionPolicy Bypass -Command "[void][System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms'); [System.Windows.Forms.MessageBox]::Show('Could not complete setup because component installation encountered an issue.' + [Environment]::NewLine + [Environment]::NewLine + 'Please check your internet connection, verify Python 3.10+ is installed, and double-click Run_Windows.bat again to resume.', 'Setup Incomplete - Faery Good Transcriber', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Warning) | Out-Null"
    goto :end
)

echo Setup completed successfully!
echo.
echo Starting Faery Good Transcriber...
python app.py
if errorlevel 1 goto :runtime_error
goto :end

:runtime_error
powershell -NoProfile -ExecutionPolicy Bypass -Command "[void][System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms'); [System.Windows.Forms.MessageBox]::Show('Faery Good Transcriber stopped unexpectedly.' + [Environment]::NewLine + [Environment]::NewLine + 'If this issue persists, please verify all files were extracted from the ZIP archive.', 'Faery Good Transcriber Notice', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Warning) | Out-Null"

:end
endlocal
