"""
Constants, Brand Palette, and Asset Discovery for Faery Good Transcriber
Tailored for Faery Good (https://faerygood.com/)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Disable Hugging Face symlink warnings on Windows platforms
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
# Suppress pygame community banner
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

# Windows High-DPI awareness initialization
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

import customtkinter as ctk

# ---------------------------------------------------------------------------
# Brand Identity & URLs
# ---------------------------------------------------------------------------
APP_NAME = "Faery Good Transcriber"
APP_VERSION = "1.3.0"
FAERY_GOOD_TAGLINE = "Whimsy is Power"
FAERY_GOOD_SUBTITLE = "Small Batch, Whimsical Apothecary for the Tender Hearted"
FAERY_GOOD_URL = "https://faerygood.com/"
BRAND_TAGLINE = "Whimsy is Power  •  Small-Batch Audio & Video Transcription for Reels & YouTube"
BRAND_SUBTITLE = "Crafted with love for Ericka Mabrie & Faery Good Apothecary"
BRAND_WEBSITE = FAERY_GOOD_URL

# ---------------------------------------------------------------------------
# File Paths & Defaults
# ---------------------------------------------------------------------------
CONFIG_FILE_NAME = ".faery_transcriber_config.json"
CONFIG_PATH = Path.home() / CONFIG_FILE_NAME
HISTORY_FILE_NAME = ".faery_transcriptions_history.json"
HISTORY_PATH = Path.home() / HISTORY_FILE_NAME

DEFAULT_OUTPUT_DIR = Path.home() / "Documents" / "Transcriptions"

SUPPORTED_MEDIA_EXTENSIONS = {".mp4", ".mov", ".m4a", ".mp3", ".wav", ".mkv"}

MODEL_DISPLAY_NAMES = {
    "High Accuracy (small.en - Recommended)": "small.en",
    "Standard (base.en - Fast)": "base.en",
}
DEFAULT_MODEL_DISPLAY = "High Accuracy (small.en - Recommended)"

COOKIE_BROWSER_OPTIONS = {
    "Auto / Public (Recommended)": None,
    "Safari (macOS)": "safari",
    "Chrome": "chrome",
    "Firefox": "firefox",
    "Edge": "edge",
}
DEFAULT_COOKIE_BROWSER = "Auto / Public (Recommended)"

MIN_DISK_SPACE_MB = 500  # Minimum free disk space in MB required for scratch audio conversion

# ---------------------------------------------------------------------------
# Color Palette (Refined for macOS Sonoma HIG)
# ---------------------------------------------------------------------------
FAERY_PURPLE = ("#7A2DB4", "#9146CC")                  # Primary Royal Faery Purple (rgb 122,45,180)
FAERY_PURPLE_HOVER = ("#632096", "#A45EE0")            # Deep Amethyst Hover
FAERY_LAVENDER_BG = ("#F3EFFB", "#120D1A")             # Apple Studio Alabaster-Lavender / Deep Obsidian Plum
FAERY_BG = FAERY_LAVENDER_BG
FAERY_CREAM_CARD = ("#FCFBF9", "#1B1326")              # Warm Porcelain Card / Elevated Dark Plum Surface
FAERY_ROSE_CARD = ("#FAF1F7", "#251936")               # Subtle Rose Quartz / Muted Amethyst Accent
FAERY_CARD_BORDER = ("#E4DAF2", "#2F2042")             # 1px Hairline Card Border
FAERY_DIVIDER = ("#EDE6F7", "#281B38")                 # Ultra-subtle 1px interior divider
FAERY_ACTIVE_BORDER = ("#7A2DB4", "#C07EF2")           # Highlighted Selection Border
FAERY_SEGMENT_TRACK = ("#EAE3F5", "#241834")           # macOS Sonoma Segmented Control Track
FAERY_SEGMENT_HOVER = ("#DFD5F0", "#2F2044")           # Segmented Unselected Hover
FAERY_SECONDARY_BTN = ("#EDE5F7", "#2D1D42")           # Borderless Apple-Tinted Pill Button
FAERY_SECONDARY_HOVER = ("#DFCFF2", "#3E2B57")         # Secondary Pill Button Hover
FAERY_SECONDARY_TEXT = ("#4A1773", "#F2E8FF")          # High-Contrast Secondary Pill Button Text
FAERY_SECONDARY_DISABLED_TEXT = ("#5E3E7A", "#AFA0C5") # High-Contrast Disabled Secondary Button Text
FAERY_TEXT_PRIMARY = ("#200D30", "#F8F2FF")            # High-Contrast Editorial Ink
FAERY_TEXT_MUTED = ("#461B6D", "#D8C2F2")              # Clear Apple Secondary Label Plum
FAERY_SAGE_GREEN = "#7EA156"                           # Apothecary Herbal Sage Green (Copied/Saved feedback)
FAERY_BERRY_RED = ("#FBE9EF", "#3A1828")               # Soft Tinted Destructive Surface
FAERY_BERRY_HOVER = ("#F5D0DD", "#4F1F35")
FAERY_BERRY_TEXT = ("#A82458", "#FF85B3")


# ---------------------------------------------------------------------------
# Asset Discovery Helpers
# ---------------------------------------------------------------------------
def get_assets_dir() -> Path:
    """Resolves the bundled or local assets directory across source and PyInstaller runs."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "assets"
    # Candidate 1: relative to repo root (parent of faery_app package)
    repo_assets = Path(__file__).resolve().parent.parent / "assets"
    if repo_assets.exists():
        return repo_assets
    # Candidate 2: relative to current working directory
    cwd_assets = Path.cwd() / "assets"
    if cwd_assets.exists():
        return cwd_assets
    return repo_assets


def get_music_dir() -> Path:
    """Finds the directory containing music tracks (checks assets/music and assets/Audio/music)."""
    assets = get_assets_dir()
    for candidate in [assets / "music", assets / "Audio" / "music", assets / "audio" / "music"]:
        if candidate.exists() and candidate.is_dir():
            return candidate
    return assets / "music"


def get_announcer_dir() -> Path:
    """Finds the directory containing DJ announcer clips (checks assets/announcer and assets/Audio/announcer)."""
    assets = get_assets_dir()
    for candidate in [assets / "announcer", assets / "Audio" / "announcer", assets / "audio" / "announcer"]:
        if candidate.exists() and candidate.is_dir():
            return candidate
    return assets / "announcer"


def apply_faery_good_theme() -> None:
    """Applies the custom Faery Good color theme to CustomTkinter."""
    theme_file = get_assets_dir() / "faery_good_theme.json"
    if theme_file.exists():
        try:
            ctk.set_default_color_theme(str(theme_file))
            return
        except Exception:
            pass
    ctk.set_default_color_theme("blue")
