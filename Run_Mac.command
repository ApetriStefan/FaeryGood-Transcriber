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

# Function: Validate that a candidate Python interpreter is >= 3.10
is_valid_python() {
    local p="$1"
    [ -n "$p" ] && [ -x "$p" ] || return 1
    "$p" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null
}

# Detect Python (strictly requiring Python >= 3.10)
PYTHON_CMD=""
for cmd in \
    "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3" \
    "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3" \
    "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3" \
    "/Library/Frameworks/Python.framework/Versions/3.10/bin/python3" \
    "/usr/local/bin/python3.13" \
    "/usr/local/bin/python3.12" \
    "/usr/local/bin/python3.11" \
    "/usr/local/bin/python3.10" \
    "/usr/local/bin/python3" \
    "/opt/homebrew/bin/python3.13" \
    "/opt/homebrew/bin/python3.12" \
    "/opt/homebrew/bin/python3.11" \
    "/opt/homebrew/bin/python3.10" \
    "/opt/homebrew/bin/python3" \
    "$HOME/.pyenv/shims/python3" \
    "$HOME/miniforge3/bin/python3" \
    "$HOME/miniconda3/bin/python3" \
    "$(which python3.13 2>/dev/null)" \
    "$(which python3.12 2>/dev/null)" \
    "$(which python3.11 2>/dev/null)" \
    "$(which python3.10 2>/dev/null)" \
    "$(which python3 2>/dev/null)" \
    "/usr/bin/python3"; do
    if is_valid_python "$cmd"; then
        PYTHON_CMD="$cmd"
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "❌ Python 3.10 or newer was not found on your Mac."
    CHOICE=$(osascript <<'EOF' 2>/dev/null || true
try
    set dialogResult to display alert "Python 3.12 Required" message "Faery Good Transcriber requires Python 3.10 or newer (your Mac currently has Apple's older built-in Python 3.9). Would you like to install the official Python 3.12 package now?" buttons {"Cancel", "Install Python"} default button "Install Python"
    return button returned of dialogResult
on error
    return "Cancel"
end try
EOF
)
    if [ "$CHOICE" = "Install Python" ]; then
        echo "📥 Downloading official Python 3.12 installer from python.org..."
        PKG_PATH="/tmp/python-3.12.10-macos11.pkg"
        if curl -fSL "https://www.python.org/ftp/python/3.12.10/python-3.12.10-macos11.pkg" -o "$PKG_PATH"; then
            echo "📦 Opening Python 3.12 installer..."
            open "$PKG_PATH"
            osascript <<'EOF' 2>/dev/null || true
display alert "Python 3.12 Installer Started" message "The official Python installer has opened on your screen.

1. Complete the installation steps.
2. Once finished, double-click Run_Mac.command again!" buttons {"OK"} default button "OK"
EOF
        else
            echo "⚠️ Direct download failed. Opening python.org download page in your browser..."
            open "https://www.python.org/downloads/macos/"
        fi
    fi
    exit 0
fi

echo "✔ Using Python: $PYTHON_CMD"

# Auto-Reset Stale / Incompatible .venv (e.g. created with older Python < 3.10)
if [ -d ".venv" ]; then
    if ! is_valid_python ".venv/bin/python"; then
        echo "⚠️ Detected outdated or incompatible Python environment in .venv. Resetting..."
        rm -rf ".venv"
    fi
fi

# Setup virtual environment if missing
if [ ! -d ".venv" ]; then
    echo "📦 Initializing clean Python virtual environment (.venv)..."
    "$PYTHON_CMD" -m venv .venv || {
        echo "❌ Failed to create virtual environment."
        osascript -e 'display alert "Setup Notice - Faery Good Transcriber" message "Failed to create a local virtual environment (.venv). Please ensure you have write permissions in this folder and that all files were extracted from the archive." as warning' 2>/dev/null || true
        read -p "Press Enter to exit..."
        exit 1
    }
fi

# Activate virtual environment
source .venv/bin/activate

# Check and install requirements if needed
if ! python -c "import customtkinter, faster_whisper, imageio_ffmpeg, PIL, yt_dlp, yt_dlp_ejs, deno, sounddevice, pygame" >/dev/null 2>&1; then
    echo "📥 Installing required components (one-time setup, takes ~1 min)..."
    pip install --upgrade pip -q
    pip install -r requirements.txt -q || {
        echo "❌ Dependency installation failed."
        echo "   Please check the terminal output above, verify your internet connection, and ensure Python 3.10+ is installed."
        osascript -e 'display alert "Setup Incomplete - Faery Good Transcriber" message "Could not complete setup because component installation encountered an issue. Please check your internet connection, ensure Python 3.10+ is installed, and double-click Run_Mac.command again to resume." as warning' 2>/dev/null || true
        read -p "Press Enter to exit..."
        exit 1
    }
    echo "✔ Components installed successfully!"
else
    # Keep yt-dlp social extractors fresh silently in the background
    pip install --upgrade "yt-dlp[default]" yt-dlp-ejs deno -q >/dev/null 2>&1 || true
fi

# Ensure macOS Applications folder integration
install_app_bundle() {
    local target_dir="/Applications"
    if [ ! -w "$target_dir" ]; then
        target_dir="$HOME/Applications"
        mkdir -p "$target_dir" 2>/dev/null || true
    fi

    local bundle="$target_dir/Faery Good Transcriber.app"
    local contents="$bundle/Contents"
    local macos_dir="$contents/MacOS"
    local res_dir="$contents/Resources"
    local launcher="$macos_dir/Faery Good Transcriber"
    local plist="$contents/Info.plist"

    mkdir -p "$macos_dir" "$res_dir" 2>/dev/null || return 0

    # Write Contents/Info.plist
    cat <<'EOF' > "$plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>Faery Good Transcriber</string>
    <key>CFBundleDisplayName</key>
    <string>Faery Good Transcriber</string>
    <key>CFBundleIdentifier</key>
    <string>com.faerygood.transcriber</string>
    <key>CFBundleVersion</key>
    <string>1.3.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.3.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleExecutable</key>
    <string>Faery Good Transcriber</string>
    <key>CFBundleIconFile</key>
    <string>faery_icon.icns</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSMinimumSystemVersion</key>
    <string>11.0</string>
    <key>LSApplicationCategoryType</key>
    <string>public.app-category.video</string>
    <key>NSDocumentsFolderUsageDescription</key>
    <string>Faery Good Transcriber stores generated transcripts in your Documents folder.</string>
    <key>NSMicrophoneUsageDescription</key>
    <string>Faery Good Transcriber uses your microphone when you record voice notes for local on-device transcription.</string>
    <key>NSHumanReadableCopyright</key>
    <string>Crafted for Faery Good (https://faerygood.com/) • Whimsy is Power</string>
</dict>
</plist>
EOF

    # Write Contents/MacOS/Faery Good Transcriber launcher script
    cat <<EOF > "$launcher"
#!/usr/bin/env bash
REPO_DIR="$DIR"
cd "\$REPO_DIR" || exit 1
if [ -f "\$REPO_DIR/.venv/bin/python" ]; then
    exec "\$REPO_DIR/.venv/bin/python" "\$REPO_DIR/app.py"
elif [ -x "\$REPO_DIR/Run_Mac.command" ]; then
    exec "\$REPO_DIR/Run_Mac.command"
else
    exec python3 "\$REPO_DIR/app.py"
fi
EOF

    chmod +x "$launcher" 2>/dev/null || true

    # Copy Faery Good icon to Resources
    if [ -f "$DIR/assets/faery_icon.icns" ]; then
        cp "$DIR/assets/faery_icon.icns" "$res_dir/faery_icon.icns" 2>/dev/null || true
    fi

    # Remove macOS Gatekeeper quarantine attributes
    xattr -cr "$bundle" 2>/dev/null || true

    # Register with LaunchServices for instant Spotlight searchability
    local lsregister="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
    if [ -x "$lsregister" ]; then
        "$lsregister" -f "$bundle" 2>/dev/null || true
    elif command -v lsregister >/dev/null 2>&1; then
        lsregister -f "$bundle" 2>/dev/null || true
    fi

    touch "$bundle" 2>/dev/null || true

    echo "✔ Added \"Faery Good Transcriber\" to Applications (Searchable via Spotlight ⌘+Space)"
}

install_app_bundle 2>/dev/null || true

# Launch Application
echo "✨ Launching Faery Good Transcriber..."
python app.py || {
    osascript -e 'display alert "Faery Good Transcriber Notice" message "The application stopped unexpectedly. If this issue persists, please verify all files were extracted from the archive." as warning' 2>/dev/null || true
}

deactivate
