# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Specification File for Faery Good Transcriber
Custom-crafted for Ericka & Faery Good (https://faerygood.com/)
Optimized for:
- macOS Sonoma (Intel x86_64, 4-core i7, 32GB RAM)
- Windows 11 (x86_64)
"""

import os
import sys
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []

# Bundle Faery Good custom artwork, logos, theme, and icons
if os.path.isdir("assets"):
    datas.append(("assets", "assets"))

# Collect all dynamic assets and binaries for critical packages
for pkg in ["customtkinter", "imageio_ffmpeg", "ctranslate2", "faster_whisper", "PIL", "yt_dlp", "pygame"]:
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

block_cipher = None

win_icon = "assets/faery_icon.ico" if os.path.exists("assets/faery_icon.ico") else None
mac_icon = "assets/faery_icon.icns" if os.path.exists("assets/faery_icon.icns") else None

a = Analysis(
    ['app.py'],
    pathex=[],
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
    console=False,  # Windowed GUI mode, no terminal black box
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

# On macOS, generate the standalone .app application bundle with Faery Good icon
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='FaeryTranscriber.app',
        icon=mac_icon,
        bundle_identifier='com.faerygood.transcriber',
        info_plist={
            'CFBundleName': 'Faery Good Transcriber',
            'CFBundleDisplayName': 'Faery Good Transcriber',
            'CFBundleGetInfoString': 'Faery Good Transcriber — Whimsy is Power',
            'CFBundleIdentifier': 'com.faerygood.transcriber',
            'CFBundleVersion': '1.2.0',
            'CFBundleShortVersionString': '1.2.0',
            'NSHighResolutionCapable': True,
            'NSRequiresAquaSystemAppearance': False,
            'LSMinimumSystemVersion': '11.0',
            'LSApplicationCategoryType': 'public.app-category.video',
            'NSDocumentsFolderUsageDescription': 'Faery Good Transcriber stores generated transcripts in your Documents folder.',
            'NSHumanReadableCopyright': 'Crafted for Faery Good (https://faerygood.com/) • Whimsy is Power',
        },
    )

