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
        osascript -e 'display alert "Setup Notice - Faery Good Transcriber" message "Failed to create a local virtual environment (.venv). Please ensure you have write permissions in this folder and that all files were extracted from the archive." as warning' 2>/dev/null || true
        read -p "Press Enter to exit..."
        exit 1
    }
fi

# Activate virtual environment
source .venv/bin/activate

# Check and install requirements if needed
if ! python -c "import customtkinter, faster_whisper, imageio_ffmpeg, PIL, yt_dlp, pygame" >/dev/null 2>&1; then
    echo "📥 Installing required components (one-time setup, takes ~1 min)..."
    pip install --upgrade pip -q
    pip install -r requirements.txt -q || {
        echo "❌ Dependency installation failed. Please check your internet connection."
        osascript -e 'display alert "Internet Connection Needed" message "Could not complete setup because component installation encountered an issue. Please check your internet connection and double-click Run_Mac.command again to resume." as warning' 2>/dev/null || true
        read -p "Press Enter to exit..."
        exit 1
    }
    echo "✔ Components installed successfully!"
else
    # Keep yt-dlp social extractors fresh silently in the background
    pip install --upgrade yt-dlp -q >/dev/null 2>&1 || true
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
