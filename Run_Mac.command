#!/usr/bin/env bash
# ==============================================================================
# Faery Good Transcriber - 1-Click Mac Launcher
# Double-click this file in macOS Finder to start the application.
# ==============================================================================

# Change working directory to script location
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit 1

echo "=================================================="
echo " 🦋 Faery Good Transcriber - Starting up..."
echo "=================================================="

# Detect Python 3
PYTHON_CMD=""
for cmd in "/opt/homebrew/bin/python3" "/usr/local/bin/python3" "/usr/bin/python3" "$(which python3 2>/dev/null)"; do
    if [ -n "$cmd" ] && [ -x "$cmd" ]; then
        PYTHON_CMD="$cmd"
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "❌ Python 3 was not found on your Mac."
    osascript -e 'display alert "Python 3 Required" message "Faery Good Transcriber requires Python 3. Would you like to open the official Python download page?" buttons {"Cancel", "Download Python"} default button "Download Python"' -e 'if button returned of result is "Download Python" then open location "https://www.python.org/downloads/"'
    exit 1
fi

echo "✔ Using Python: $PYTHON_CMD"

# Setup virtual environment if missing
if [ ! -d ".venv" ]; then
    echo "📦 Initializing clean Python virtual environment (.venv)..."
    "$PYTHON_CMD" -m venv .venv || {
        echo "❌ Failed to create virtual environment."
        read -p "Press Enter to exit..."
        exit 1
    }
fi

# Activate virtual environment
source .venv/bin/activate

# Check and install requirements if needed
if ! python -c "import customtkinter, faster_whisper, imageio_ffmpeg, PIL, yt_dlp" >/dev/null 2>&1; then
    echo "📥 Installing required components (one-time setup, takes ~1 min)..."
    pip install --upgrade pip -q
    pip install -r requirements.txt -q || {
        echo "❌ Dependency installation failed. Please check your internet connection."
        read -p "Press Enter to exit..."
        exit 1
    }
    echo "✔ Components installed successfully!"
else
    # Keep yt-dlp social extractors fresh silently in the background
    pip install --upgrade yt-dlp -q >/dev/null 2>&1 || true
fi

# Launch Application
echo "✨ Launching Faery Good Transcriber..."
python app.py

deactivate
