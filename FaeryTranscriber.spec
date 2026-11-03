# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Specification File for Faery Good Transcriber
Custom-crafted for Ericka & Faery Good (https://faerygood.com/)
Optimized for:
- macOS Sonoma (Intel x86_64, 4-core i7, 32GB RAM / Apple Silicon)
- Windows 11 (x86_64)

Features:
- Pure windowed GUI (console=False, zero ugly command-line black boxes)
- Full recursive collection of custom Faery Good assets (mascot, icons, themes, announcer, music)
- Complete dynamic assets, binaries, and hidden imports for critical packages:
  customtkinter, faster_whisper, imageio_ffmpeg, ctranslate2, huggingface_hub, tokenizers, certifi, yt_dlp, pygame
"""

import os
import sys
from PyInstaller.utils.hooks import collect_all

# Resolve absolute path to the directory containing this spec file
spec_dir = os.path.abspath(SPECPATH if "SPECPATH" in locals() else (os.path.dirname(__file__) if "__file__" in locals() else os.getcwd()))
assets_dir = os.path.join(spec_dir, "assets")

datas = []
binaries = []
hiddenimports = []

# Bundle Faery Good custom artwork, logos, theme, announcer clips, and music tracks
if os.path.isdir(assets_dir):
    datas.append((assets_dir, "assets"))

# Collect all dynamic assets, binaries, C-extensions, and hidden imports for critical libraries
critical_pkgs = [
    "customtkinter",
    "imageio_ffmpeg",
    "ctranslate2",
    "faster_whisper",
    "huggingface_hub",
    "tokenizers",
    "certifi",
    "PIL",
    "yt_dlp",
    "pygame",
]

for pkg in critical_pkgs:
    try:
        pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
        datas += pkg_datas
        binaries += pkg_binaries
        hiddenimports += pkg_hiddenimports
    except Exception as e:
        print(f"[FaeryTranscriber.spec] Notice: collect_all for '{pkg}' returned: {e}")

win_icon = os.path.join(assets_dir, "faery_icon.ico") if os.path.exists(os.path.join(assets_dir, "faery_icon.ico")) else None
mac_icon = os.path.join(assets_dir, "faery_icon.icns") if os.path.exists(os.path.join(assets_dir, "faery_icon.icns")) else None

block_cipher = None

a = Analysis(
    [os.path.join(spec_dir, "app.py")],
    pathex=[spec_dir],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter.test', 'unittest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FaeryTranscriber',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Windowed GUI mode: zero command-line friction / no terminal black box
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='x86_64',
    codesign_identity=None,
    entitlements_file=None,
    icon=win_icon if sys.platform == 'win32' else mac_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FaeryTranscriber',
)

# On macOS, generate the standalone .app application bundle with custom Faery Good icon
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='Faery Good Transcriber.app',
        icon=mac_icon,
        bundle_identifier='com.faerygood.transcriber',
        info_plist={
            'CFBundleName': 'Faery Good Transcriber',
            'CFBundleDisplayName': 'Faery Good Transcriber',
            'CFBundleGetInfoString': 'Faery Good Transcriber — Whimsy is Power',
            'CFBundleIdentifier': 'com.faerygood.transcriber',
            'CFBundleVersion': '1.3.0',
            'CFBundleShortVersionString': '1.3.0',
            'NSHighResolutionCapable': True,
            'NSRequiresAquaSystemAppearance': False,
            'LSMinimumSystemVersion': '11.0',
            'LSApplicationCategoryType': 'public.app-category.video',
            'NSDocumentsFolderUsageDescription': 'Faery Good Transcriber stores generated transcripts in your Documents folder.',
            'NSHumanReadableCopyright': 'Crafted for Faery Good (https://faerygood.com/) • Whimsy is Power',
        },
    )
