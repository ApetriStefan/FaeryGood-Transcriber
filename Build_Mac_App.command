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

# Ensure virtual environment is ready
if [ ! -d ".venv" ]; then
    echo "📦 Initializing virtual environment..."
    python3 -m venv .venv
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
