#!/usr/bin/env bash
# ==============================================================================
# Faery Good Transcriber - macOS DMG Installer Creator
# Double-click in macOS Finder to create FaeryTranscriber-Intel-Mac.dmg
# ==============================================================================

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit 1

echo "========================================================"
echo " 🦋 Packaging Faery Good Transcriber into .dmg installer"
echo "========================================================"

APP_PATH="dist/FaeryTranscriber.app"

# If the .app bundle hasn't been built yet, build it first
if [ ! -d "$APP_PATH" ]; then
    echo "⚙️ Application bundle not found. Building first via Build_Mac_App.command..."
    ./Build_Mac_App.command || exit 1
fi

STAGING_DIR="dist/dmg_staging"
DMG_NAME="FaeryTranscriber-Intel-Mac.dmg"

echo "📦 Preparing DMG staging directory..."
rm -rf "$STAGING_DIR" "$DMG_NAME"
mkdir -p "$STAGING_DIR"

# Copy .app bundle into staging
cp -R "$APP_PATH" "$STAGING_DIR/"

# Apply custom Faery Good icon to the mounted DMG volume if available
if [ -f "assets/faery_icon.icns" ]; then
    cp "assets/faery_icon.icns" "$STAGING_DIR/.VolumeIcon.icns"
    if command -v SetFile >/dev/null 2>&1; then
        SetFile -c icnC "$STAGING_DIR/.VolumeIcon.icns" 2>/dev/null || true
        SetFile -a C "$STAGING_DIR" 2>/dev/null || true
    fi
fi

# Create standard /Applications symlink for drag-and-drop installation
ln -s /Applications "$STAGING_DIR/Applications"

echo "🔨 Creating compressed Apple Disk Image (DMG)..."
hdiutil create -volname "Faery Good Transcriber" \
               -srcfolder "$STAGING_DIR" \
               -ov \
               -format UDZO \
               "$DMG_NAME"

# Clean up staging
rm -rf "$STAGING_DIR"

if [ -f "$DMG_NAME" ]; then
    echo "========================================================"
    echo " ✨ SUCCESS! Faery Good Installer created:"
    echo "    $DIR/$DMG_NAME"
    echo "========================================================"
    echo "Ericka can simply double-click this DMG, drag"
    echo "FaeryTranscriber into Applications, and launch!"
    
    # Reveal in Finder
    open -R "$DMG_NAME"
else
    echo "❌ Failed to create DMG."
    read -p "Press Enter to exit..."
fi

