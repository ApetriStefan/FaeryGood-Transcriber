#!/usr/bin/env bash
# ==============================================================================
# Faery Transcriber - Standalone macOS App Bundle Packager
# Double-click in macOS Finder to build FaeryTranscriber.app
# ==============================================================================

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit 1

echo "=================================================="
echo " 🛠️ Building Standalone FaeryTranscriber.app..."
echo "=================================================="

# Detect Python >= 3.10
PYTHON_CMD=""
for cmd in \
    "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3" \
    "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3" \
    "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3" \
    "/Library/Frameworks/Python.framework/Versions/3.10/bin/python3" \
    "/usr/local/bin/python3" \
    "/opt/homebrew/bin/python3" \
    "$(which python3 2>/dev/null)"; do
    if [ -x "$cmd" ] && "$cmd" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
        PYTHON_CMD="$cmd"
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "❌ Python 3.10 or newer is required to build the standalone app."
    read -p "Press Enter to exit..."
    exit 1
fi

# Ensure virtual environment is ready and compatible
if [ -d ".venv" ] && ! .venv/bin/python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
    echo "⚠️ Resetting incompatible .venv..."
    rm -rf ".venv"
fi

if [ ! -d ".venv" ]; then
    echo "📦 Initializing virtual environment..."
    "$PYTHON_CMD" -m venv .venv
fi

source .venv/bin/activate
pip install -r requirements.txt -q

# Run PyInstaller using spec file
echo "⚙️ Compiling application bundle via PyInstaller..."
pyinstaller --clean -y FaeryTranscriber.spec

APP_PATH="dist/Faery Good Transcriber.app"
if [ ! -d "$APP_PATH" ] && [ -d "dist/FaeryTranscriber.app" ]; then
    APP_PATH="dist/FaeryTranscriber.app"
fi
BINARY_PATH="dist/FaeryTranscriber/FaeryTranscriber"

if [ -d "$APP_PATH" ]; then
    echo "🧹 Removing macOS Gatekeeper quarantine attributes..."
    xattr -cr "$APP_PATH" 2>/dev/null || true

    # Ensure executable bit is set
    chmod +x "$APP_PATH"/Contents/MacOS/* 2>/dev/null || true

    # Ad-hoc codesign with microphone entitlement for macOS TCC stability
    if command -v codesign >/dev/null 2>&1; then
        echo "🔐 Signing application bundle with microphone entitlement..."
        if [ -f "macos_entitlements.plist" ]; then
            codesign --force --deep --sign - --entitlements "macos_entitlements.plist" "$APP_PATH" 2>/dev/null || true
        else
            codesign --force --deep --sign - "$APP_PATH" 2>/dev/null || true
        fi
    fi

    echo "=================================================="
    echo " ✅ SUCCESS! Standalone Mac App built at:"
    echo "    $DIR/$APP_PATH"
    echo "=================================================="
    
    # Reveal in macOS Finder
    open -R "$APP_PATH"
elif [ -d "dist/FaeryTranscriber" ]; then
    echo "🧹 Cleaning folder permissions..."
    xattr -cr "dist/FaeryTranscriber" 2>/dev/null || true
    echo "✅ Executable built in dist/FaeryTranscriber"
    open dist
else
    echo "❌ Build failed. Please inspect the log output above."
    read -p "Press Enter to exit..."
fi

deactivate
