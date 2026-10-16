@echo off
setlocal
cd /d "%~dp0"

echo ==================================================
echo  🦋 Faery Good Transcriber - Windows Launcher
echo ==================================================

if not exist ".venv\Scripts\python.exe" (
    echo Initializing virtual environment...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

echo Starting Faery Good Transcriber...
python app.py

endlocal
