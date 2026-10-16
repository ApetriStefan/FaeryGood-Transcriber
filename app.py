"""
Faery Transcriber - Production-Ready Desktop Transcription Application
=====================================================================
Target Environments:
- Development & Testing: Windows 11
- Production Runtime: macOS Sonoma (Intel x86_64, 4-core i7, 32GB RAM) / Cross-platform

Architectural Highlights:
1. GUI: customtkinter (High-DPI aware, accessible modern Dark/Light theme).
2. Audio Engine: Bundled static FFmpeg via `imageio-ffmpeg` (zero system dependencies).
3. Transcription Engine: `faster-whisper` (CTranslate2) strictly on CPU (`device="cpu"`,
   `compute_type="int8"`, `cpu_threads=4`).
4. File Hygiene: Pure temporary conversion inside `tempfile.TemporaryDirectory()`.
   Context manager guarantees 100% purge of temporary WAV files on success, error, or cancel.
5. Threading & Responsiveness: Heavy I/O and ML inference executed on background worker
   threads with thread-safe UI dispatches to prevent UI freezes and macOS beachballs.
6. Persistent Preferences & History: Output directory remembered via ~/.faery_transcriber_config.json,
   full transcript library and CRUD history in ~/.faery_transcriptions_history.json.
7. Acoustic Formatting: Detects audio pauses and sentence boundaries for natural paragraphs,
   with instant real-time live preview and dual-view timecoding (YouTube format).
8. Overwrite Protection: Prompts the user when transcribing the same clip to either overwrite
   or create a new numbered version.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Callable, List, Optional, Tuple

# Disable Hugging Face symlink warnings on Windows platforms
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

# Windows High-DPI awareness initialization
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

import customtkinter as ctk
import imageio_ffmpeg
from faster_whisper import WhisperModel

# ---------------------------------------------------------------------------
# Constants, Brand Palette & Enums (Tailored for Faery Good - faerygood.com)
# ---------------------------------------------------------------------------
APP_NAME = "Faery Good Transcriber"
APP_VERSION = "1.3.0"
FAERY_GOOD_TAGLINE = "Whimsy is Power"
FAERY_GOOD_SUBTITLE = "Small Batch, Whimsical Apothecary for the Tender Hearted"
FAERY_GOOD_URL = "https://faerygood.com/"
BRAND_TAGLINE = "Whimsy is Power  •  Small-Batch Audio & Video Transcription for Reels & YouTube"
BRAND_SUBTITLE = "Crafted with love for Ericka Mabrie & Faery Good Apothecary"
BRAND_WEBSITE = FAERY_GOOD_URL

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

# Official Faery Good (https://faerygood.com/) CSS Color Schemes — Refined for macOS Sonoma HIG
# Scheme 1: Lavender + Royal Faery Purple (#7A2DB4) + Warm Porcelain Cream
# Scheme 2: Petal Rose + Orchid (#C07EF2)
# Scheme 4: Apothecary Herbal Sage Green (#7EA156)
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


def get_assets_dir() -> Path:
    """Resolves the bundled or local assets directory across source and PyInstaller runs."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "assets"
    return Path(__file__).resolve().parent / "assets"


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


class BrandAssets:
    """Loads and caches official Faery Good (faerygood.com) artwork, wordmark logos, and icons."""

    def __init__(self):
        self.assets_dir = get_assets_dir()
        self.mascot_header: Optional[ctk.CTkImage] = None
        self.mascot_dialog: Optional[ctk.CTkImage] = None
        self.logo_header: Optional[ctk.CTkImage] = None
        self.logo_dialog: Optional[ctk.CTkImage] = None
        self.icon_butterfly: Optional[ctk.CTkImage] = None
        self.icon_mortar: Optional[ctk.CTkImage] = None
        self.icon_sprig: Optional[ctk.CTkImage] = None
        self._load_all()

    def _load_all(self) -> None:
        try:
            from PIL import Image

            mascot_p = self.assets_dir / "faery_mascot.png"
            if mascot_p.exists():
                m_img = Image.open(mascot_p)
                self.mascot_header = ctk.CTkImage(light_image=m_img, dark_image=m_img, size=(38, 43))
                self.mascot_dialog = ctk.CTkImage(light_image=m_img, dark_image=m_img, size=(58, 65))

            logo_l = self.assets_dir / "faery_logo_light.png"
            logo_d = self.assets_dir / "faery_logo_dark.png"
            if logo_l.exists():
                l_img = Image.open(logo_l)
                d_img = Image.open(logo_d) if logo_d.exists() else l_img
                self.logo_header = ctk.CTkImage(light_image=l_img, dark_image=d_img, size=(138, 40))
                self.logo_dialog = ctk.CTkImage(light_image=l_img, dark_image=d_img, size=(138, 40))

            bf_l = self.assets_dir / "faery_butterfly_light.png"
            bf_d = self.assets_dir / "faery_butterfly_dark.png"
            if bf_l.exists():
                self.icon_butterfly = ctk.CTkImage(
                    light_image=Image.open(bf_l),
                    dark_image=Image.open(bf_d) if bf_d.exists() else Image.open(bf_l),
                    size=(20, 20),
                )

            mt_l = self.assets_dir / "faery_mortar_light.png"
            mt_d = self.assets_dir / "faery_mortar_dark.png"
            if mt_l.exists():
                self.icon_mortar = ctk.CTkImage(
                    light_image=Image.open(mt_l),
                    dark_image=Image.open(mt_d) if mt_d.exists() else Image.open(mt_l),
                    size=(18, 18),
                )

            sp_l = self.assets_dir / "faery_sprig_light.png"
            sp_d = self.assets_dir / "faery_sprig_dark.png"
            if sp_l.exists():
                self.icon_sprig = ctk.CTkImage(
                    light_image=Image.open(sp_l),
                    dark_image=Image.open(sp_d) if sp_d.exists() else Image.open(sp_l),
                    size=(18, 18),
                )
        except Exception:
            pass

    def apply_window_icon(self, window: tk.Misc) -> None:
        """Applies the Faery Good watercolor fairy icon to the window titlebar and macOS Dock."""
        try:
            ico_path = self.assets_dir / "faery_icon.ico"
            png_path = self.assets_dir / "faery_icon.png"
            if sys.platform == "win32" and ico_path.exists():
                window.iconbitmap(default=str(ico_path))
            if png_path.exists():
                from PIL import Image, ImageTk
                pil_img = Image.open(png_path).resize((256, 256), Image.Resampling.LANCZOS)
                tk_icon = ImageTk.PhotoImage(pil_img, master=window)
                setattr(window, "_faery_tk_icon", tk_icon)
                window.iconphoto(True, tk_icon)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Data Models & Utilities
# ---------------------------------------------------------------------------
@dataclass
class MediaMetadata:
    """Represents probed metadata for a selected media file."""
    path: Path
    file_size_bytes: int
    duration_seconds: float
    has_audio: bool
    format_name: str

    @property
    def formatted_duration(self) -> str:
        """Returns human-readable duration (MM:SS or HH:MM:SS)."""
        total = int(self.duration_seconds)
        hours = total // 3600
        minutes = (total % 3600) // 60
        secs = total % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    @property
    def formatted_size(self) -> str:
        """Returns human-readable file size."""
        size_mb = self.file_size_bytes / (1024 * 1024)
        if size_mb >= 1000:
            return f"{size_mb / 1024:.2f} GB"
        return f"{size_mb:.1f} MB"


@dataclass
class TranscriptSegment:
    """Represents a single timestamped transcription segment."""
    start: float
    end: float
    text: str

    @property
    def formatted_timestamp(self) -> str:
        total = int(self.start)
        hours = total // 3600
        minutes = (total % 3600) // 60
        secs = total % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"


class TranscriptFormatter:
    """Utilities to format raw Whisper segments into clean paragraphs, timecodes, or raw text."""

    @staticmethod
    def to_paragraphs(
        segments: List[TranscriptSegment],
        pause_threshold_sec: float = 1.0,
        sentence_pause_threshold_sec: float = 0.6,
        max_sentences_per_para: int = 4,
        max_words_per_para: int = 70,
    ) -> str:
        """
        Organizes segments into clean, publication-ready paragraphs using:
        1. Acoustic silence between segments (pauses >= pause_threshold_sec).
        2. Sentence-ending punctuation followed by pause (>= sentence_pause_threshold_sec).
        3. Pacing limits (max sentences or words per paragraph) to prevent unbroken walls of text.
        """
        if not segments:
            return ""

        paragraphs: List[str] = []
        current_para_parts: List[str] = []
        sentence_count = 0
        word_count = 0
        prev_end: Optional[float] = None

        for seg in segments:
            text = seg.text.strip()
            if not text:
                continue

            gap = (seg.start - prev_end) if prev_end is not None else 0.0

            prev_ended_sentence = (
                current_para_parts
                and current_para_parts[-1].rstrip().endswith((".", "!", "?", '."', '!"', '?"', "”"))
            )
            is_long_pause = prev_end is not None and gap >= pause_threshold_sec
            is_sentence_pause = prev_ended_sentence and gap >= sentence_pause_threshold_sec
            is_para_limit = (
                prev_ended_sentence
                and (sentence_count >= max_sentences_per_para or word_count >= max_words_per_para)
            )

            if (is_long_pause or is_sentence_pause or is_para_limit) and current_para_parts:
                paragraphs.append(" ".join(current_para_parts))
                current_para_parts = []
                sentence_count = 0
                word_count = 0

            current_para_parts.append(text)
            prev_end = seg.end
            word_count += len(text.split())
            if text.endswith((".", "!", "?", '."', '!"', '?"', "”")):
                sentence_count += 1

        if current_para_parts:
            paragraphs.append(" ".join(current_para_parts))

        return "\n\n".join(paragraphs)

    @staticmethod
    def to_timecoded(segments: List[TranscriptSegment]) -> str:
        """Formats each segment with its timestamp [MM:SS] on separate lines (YouTube format)."""
        if not segments:
            return ""
        return "\n".join(f"[{seg.formatted_timestamp}] {seg.text}" for seg in segments)

    @staticmethod
    def to_raw(segments: List[TranscriptSegment]) -> str:
        """Formats segments into a single continuous stream of text."""
        if not segments:
            return ""
        return " ".join(seg.text.strip() for seg in segments if seg.text.strip())


class FaerySegmentedButton(ctk.CTkSegmentedButton):
    """
    Apple macOS Sonoma-style Segmented Control:
    - Selected segment displays crisp cream/white text on the primary purple pill.
    - Unselected segments display high-contrast deep violet text (Light Mode) or luminous lavender (Dark Mode).
    """

    def __init__(self, *args, **kwargs):
        self._selected_text_color = kwargs.pop("selected_text_color", ("#FCF4ED", "#FCF4ED"))
        self._unselected_text_color = kwargs.pop("unselected_text_color", FAERY_SECONDARY_TEXT)
        super().__init__(*args, **kwargs)
        self._apply_segment_text_contrast()

    def _create_buttons_from_values(self):
        super()._create_buttons_from_values()
        self._apply_segment_text_contrast()

    def _select_button_by_value(self, value: str):
        super()._select_button_by_value(value)
        if hasattr(self, "_buttons_dict") and value in self._buttons_dict:
            self._buttons_dict[value].configure(text_color=self._selected_text_color)

    def _unselect_button_by_value(self, value: str):
        super()._unselect_button_by_value(value)
        if hasattr(self, "_buttons_dict") and value in self._buttons_dict:
            self._buttons_dict[value].configure(text_color=self._unselected_text_color)

    def _apply_segment_text_contrast(self):
        if not hasattr(self, "_buttons_dict"):
            return
        for val, btn in self._buttons_dict.items():
            if val == self._current_value:
                btn.configure(text_color=self._selected_text_color)
            else:
                btn.configure(text_color=self._unselected_text_color)

    def set(self, value: str, from_variable_callback: bool = False, from_button_callback: bool = False):
        super().set(value, from_variable_callback=from_variable_callback, from_button_callback=from_button_callback)
        self._apply_segment_text_contrast()


def get_verified_ffmpeg_exe() -> str:
    """
    Retrieves the bundled static FFmpeg binary path from imageio-ffmpeg.
    Ensures execution permissions are granted on Unix/macOS environments.
    """
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    if not exe or not os.path.exists(exe):
        raise FileNotFoundError(
            "The bundled FFmpeg binary could not be located via imageio-ffmpeg. "
            "Please ensure imageio-ffmpeg is installed properly."
        )
    # Ensure executable permission on macOS/Linux
    if sys.platform != "win32":
        try:
            current_perms = os.stat(exe).st_mode
            os.chmod(exe, current_perms | 0o755)
        except Exception:
            pass
    return exe


def check_free_disk_space(target_path: Path, min_mb: int = MIN_DISK_SPACE_MB) -> bool:
    """Verifies that the target path or its parent volume has at least min_mb free space."""
    try:
        check_dir = target_path if target_path.exists() else target_path.parent
        usage = shutil.disk_usage(check_dir)
        free_mb = usage.free / (1024 * 1024)
        return free_mb >= min_mb
    except Exception:
        return True


def open_system_folder(folder_path: Path) -> None:
    """Opens a directory in the native file manager across Windows, macOS, and Linux."""
    folder_path.mkdir(parents=True, exist_ok=True)
    abs_path = str(folder_path.resolve())

    if sys.platform == "win32":
        os.startfile(abs_path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", abs_path])
    else:
        subprocess.Popen(["xdg-open", abs_path])


def open_system_file(file_path: Path) -> None:
    """Opens a file in the default system viewer/editor across OSes."""
    if not file_path.exists():
        return
    abs_path = str(file_path.resolve())
    if sys.platform == "win32":
        os.startfile(abs_path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", abs_path])
    else:
        subprocess.Popen(["xdg-open", abs_path])


def play_completion_sound() -> None:
    """Plays a native, non-intrusive completion chime on macOS, Windows, and Linux."""
    try:
        if sys.platform == "darwin":
            sound_candidates = [
                "/System/Library/Sounds/Glass.aiff",
                "/System/Library/Sounds/Ping.aiff",
                "/System/Library/Sounds/Hero.aiff",
            ]
            for sound in sound_candidates:
                if os.path.exists(sound):
                    subprocess.Popen(
                        ["afplay", sound],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    break
        elif sys.platform == "win32":
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        else:
            if shutil.which("paplay"):
                sound_p = "/usr/share/sounds/freedesktop/stereo/complete.oga"
                if os.path.exists(sound_p):
                    subprocess.Popen(
                        ["paplay", sound_p],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Configuration Persistence
# ---------------------------------------------------------------------------
class ConfigManager:
    """Manages application settings stored in ~/.faery_transcriber_config.json."""

    def __init__(self, config_path: Path = CONFIG_PATH):
        self.config_path = config_path
        self.data = {
            "output_directory": str(DEFAULT_OUTPUT_DIR),
            "model_selection": DEFAULT_MODEL_DISPLAY,
            "appearance_mode": "Light",
            "last_media_directory": "",
            "cookie_browser": DEFAULT_COOKIE_BROWSER,
        }
        self.load()

    def load(self) -> None:
        """Loads configuration from disk, creating defaults if missing or corrupted."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        self.data.update(loaded)
            except Exception as err:
                print(f"[Warning] Failed to read config file, restoring defaults: {err}", file=sys.stderr)

        # Validate that the configured output directory is usable
        out_dir = Path(self.data.get("output_directory", str(DEFAULT_OUTPUT_DIR)))
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            self.data["output_directory"] = str(DEFAULT_OUTPUT_DIR)
            DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def save(self) -> None:
        """Persists current configuration to disk."""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception as err:
            print(f"[Warning] Failed to write config file: {err}", file=sys.stderr)

    @property
    def output_directory(self) -> Path:
        return Path(self.data["output_directory"])

    @output_directory.setter
    def output_directory(self, new_dir: Path) -> None:
        self.data["output_directory"] = str(new_dir)
        self.save()

    @property
    def model_selection(self) -> str:
        return self.data.get("model_selection", DEFAULT_MODEL_DISPLAY)

    @model_selection.setter
    def model_selection(self, model_name: str) -> None:
        self.data["model_selection"] = model_name
        self.save()

    @property
    def appearance_mode(self) -> str:
        return self.data.get("appearance_mode", "Light")

    @appearance_mode.setter
    def appearance_mode(self, mode: str) -> None:
        self.data["appearance_mode"] = mode
        self.save()

    @property
    def cookie_browser(self) -> str:
        val = self.data.get("cookie_browser", DEFAULT_COOKIE_BROWSER)
        return val if val in COOKIE_BROWSER_OPTIONS else DEFAULT_COOKIE_BROWSER

    @cookie_browser.setter
    def cookie_browser(self, browser_label: str) -> None:
        self.data["cookie_browser"] = browser_label
        self.save()

    def get_initial_media_dir(self) -> Path:
        """Returns the user's previously browsed media directory or a smart OS default."""
        last_dir = self.data.get("last_media_directory")
        if last_dir and Path(last_dir).exists():
            return Path(last_dir)
        home = Path.home()
        for candidate in [home / "Movies", home / "Downloads", home / "Desktop", home / "Videos"]:
            if candidate.exists():
                return candidate
        return home


# ---------------------------------------------------------------------------
# Historical Transcripts Management (CRUD)
# ---------------------------------------------------------------------------
@dataclass
class HistoryRecord:
    """Represents an archived transcription session."""
    id: str
    title: str
    source_filename: str
    duration_str: str
    created_at: str
    model: str
    paragraphs_file: str
    timecoded_file: str
    markdown_file: str
    word_count: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "source_filename": self.source_filename,
            "duration_str": self.duration_str,
            "created_at": self.created_at,
            "model": self.model,
            "paragraphs_file": self.paragraphs_file,
            "timecoded_file": self.timecoded_file,
            "markdown_file": self.markdown_file,
            "word_count": self.word_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> HistoryRecord:
        return cls(
            id=data.get("id", ""),
            title=data.get("title", "Untitled"),
            source_filename=data.get("source_filename", ""),
            duration_str=data.get("duration_str", "--:--"),
            created_at=data.get("created_at", ""),
            model=data.get("model", ""),
            paragraphs_file=data.get("paragraphs_file", ""),
            timecoded_file=data.get("timecoded_file", ""),
            markdown_file=data.get("markdown_file", ""),
            word_count=data.get("word_count", 0),
        )

    def matches_query(self, query: str) -> Tuple[bool, Optional[str]]:
        """
        Performs multi-token search across title, filename, date, model,
        and full spoken transcript content.
        Returns (is_match, optional_content_snippet).
        """
        clean_q = (query or "").strip()
        if not clean_q:
            return True, None

        terms = [t.lower() for t in clean_q.split() if t]
        if not terms:
            return True, None

        title_raw = self.title.lower()
        title_norm = self.title.lower().replace("_", " ").replace("-", " ")
        source_raw = self.source_filename.lower()
        source_norm = self.source_filename.lower().replace("_", " ").replace("-", " ")
        date_str = self.created_at.lower()
        model_str = self.model.lower()

        # Read transcript text for content search (paragraphs preferred, markdown fallback)
        content_text = ""
        for f_path in [self.paragraphs_file, self.markdown_file]:
            if f_path and os.path.exists(f_path):
                try:
                    with open(f_path, "r", encoding="utf-8", errors="ignore") as f:
                        content_text = f.read()
                    break
                except Exception:
                    pass

        content_lower = content_text.lower()
        snippet = None

        for term in terms:
            in_meta = (
                term in title_raw
                or term in title_norm
                or term in source_raw
                or term in source_norm
                or term in date_str
                or term in model_str
            )
            in_content = term in content_lower
            if not (in_meta or in_content):
                return False, None

            # Extract a contextual snippet if matched in transcript body
            if in_content and not in_meta and snippet is None:
                pos = content_lower.find(term)
                if pos != -1:
                    start = max(0, pos - 25)
                    end = min(len(content_text), pos + len(term) + 35)
                    snip = content_text[start:end].replace("\n", " ").strip()
                    snippet = f"...{snip}..."

        return True, snippet


class HistoryManager:
    """Manages persistent transcription library and synchronization with disk."""

    def __init__(self, history_path: Path = HISTORY_PATH):
        self.history_path = history_path
        self.records: List[HistoryRecord] = []
        self.load()

    def load(self) -> None:
        self.records.clear()
        if self.history_path.exists():
            try:
                with open(self.history_path, "r", encoding="utf-8") as f:
                    raw_list = json.load(f)
                    if isinstance(raw_list, list):
                        self.records = [HistoryRecord.from_dict(item) for item in raw_list]
            except Exception as err:
                print(f"[Warning] Failed to load history: {err}", file=sys.stderr)

    def save(self) -> None:
        try:
            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump([r.to_dict() for r in self.records], f, indent=2)
        except Exception as err:
            print(f"[Warning] Failed to save history: {err}", file=sys.stderr)

    def add_or_update(self, record: HistoryRecord) -> None:
        """Inserts a new record or replaces an existing one with identical paths/title."""
        for idx, r in enumerate(self.records):
            if (
                r.id == record.id
                or r.markdown_file == record.markdown_file
                or (r.title == record.title and r.paragraphs_file == record.paragraphs_file)
            ):
                self.records[idx] = record
                self.save()
                return
        self.records.insert(0, record)
        self.save()

    def sync_with_directory(self, output_dir: Path) -> List[HistoryRecord]:
        """Scans output_dir, auto-discovers external or older transcripts and purges missing files."""
        if not output_dir.exists():
            return self.records

        discovered_stems = set()
        for f in output_dir.glob("*_transcript.md"):
            stem = f.name[:-14]  # strip "_transcript.md"
            discovered_stems.add(stem)
        for f in output_dir.glob("*_paragraphs.txt"):
            stem = f.name[:-15]  # strip "_paragraphs.txt"
            discovered_stems.add(stem)

        known_titles = {r.title for r in self.records}
        known_files = {r.markdown_file for r in self.records}

        for stem in discovered_stems:
            para_f = output_dir / f"{stem}_paragraphs.txt"
            time_f = output_dir / f"{stem}_timecoded.txt"
            md_f = output_dir / f"{stem}_transcript.md"

            if str(md_f) not in known_files and stem not in known_titles:
                wcount = 0
                if para_f.exists():
                    try:
                        wcount = len(para_f.read_text(encoding="utf-8", errors="ignore").split())
                    except Exception:
                        pass
                mtime_str = datetime.fromtimestamp(
                    (md_f if md_f.exists() else para_f).stat().st_mtime
                ).strftime("%Y-%m-%d %H:%M")

                new_rec = HistoryRecord(
                    id=f"{stem}_{int(time.time())}",
                    title=stem,
                    source_filename=f"{stem}.mp4",
                    duration_str="--:--",
                    created_at=mtime_str,
                    model="Whisper",
                    paragraphs_file=str(para_f) if para_f.exists() else "",
                    timecoded_file=str(time_f) if time_f.exists() else "",
                    markdown_file=str(md_f) if md_f.exists() else "",
                    word_count=wcount,
                )
                self.records.append(new_rec)

        # Remove records where all associated files no longer exist on disk
        valid_records = []
        for r in self.records:
            has_p = r.paragraphs_file and os.path.exists(r.paragraphs_file)
            has_t = r.timecoded_file and os.path.exists(r.timecoded_file)
            has_m = r.markdown_file and os.path.exists(r.markdown_file)
            if has_p or has_t or has_m:
                valid_records.append(r)
        self.records = valid_records
        self.save()
        return self.records

    def rename_record(self, record_id: str, new_title: str) -> Optional[HistoryRecord]:
        """Renames a transcript and updates associated files on disk."""
        new_title = re.sub(r'[\\/*?:"<>|]', "", new_title).strip()
        if not new_title:
            return None

        for r in self.records:
            if r.id == record_id:
                old_p = Path(r.paragraphs_file) if r.paragraphs_file else None
                old_t = Path(r.timecoded_file) if r.timecoded_file else None
                old_m = Path(r.markdown_file) if r.markdown_file else None

                parent_dir = None
                for p in [old_p, old_t, old_m]:
                    if p and p.parent.exists():
                        parent_dir = p.parent
                        break
                if not parent_dir:
                    return None

                new_p = parent_dir / f"{new_title}_paragraphs.txt"
                new_t = parent_dir / f"{new_title}_timecoded.txt"
                new_m = parent_dir / f"{new_title}_transcript.md"

                try:
                    if old_p and old_p.exists():
                        old_p.rename(new_p)
                        r.paragraphs_file = str(new_p)
                    if old_t and old_t.exists():
                        old_t.rename(new_t)
                        r.timecoded_file = str(new_t)
                    if old_m and old_m.exists():
                        old_m.rename(new_m)
                        r.markdown_file = str(new_m)

                    r.title = new_title
                    self.save()
                    return r
                except Exception as err:
                    raise IOError(f"Could not rename files: {err}")
        return None

    def delete_record(self, record_id: str) -> bool:
        """Deletes files from disk and removes the record from library."""
        for idx, r in enumerate(self.records):
            if r.id == record_id:
                for path_str in [r.paragraphs_file, r.timecoded_file, r.markdown_file]:
                    if path_str and os.path.exists(path_str):
                        try:
                            os.remove(path_str)
                        except Exception:
                            pass
                self.records.pop(idx)
                self.save()
                return True
        return False


# ---------------------------------------------------------------------------
# Media Inspector & Extraction Subsystem
# ---------------------------------------------------------------------------
class MediaProcessor:
    """Handles audio track detection, duration probing, and 16kHz WAV extraction."""

    @staticmethod
    def probe_file(file_path: Path) -> MediaMetadata:
        """
        Inspects the input file using the bundled static FFmpeg binary.
        Raises descriptive exceptions if the file is invalid, corrupt, or lacks audio.
        """
        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(f"Selected file does not exist: {file_path}")

        file_size = file_path.stat().st_size
        if file_size == 0:
            raise ValueError("The selected file is empty (0 bytes).")

        ffmpeg_exe = get_verified_ffmpeg_exe()
        cmd = [ffmpeg_exe, "-hide_banner", "-i", str(file_path)]

        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creation_flags,
                timeout=15,
            )
        except subprocess.TimeoutExpired:
            raise TimeoutError("Probing the media file timed out.")
        except Exception as err:
            raise RuntimeError(f"Failed to probe media file with FFmpeg: {err}")

        stderr = proc.stderr or ""

        if "Invalid data found when processing input" in stderr:
            raise ValueError(
                "The selected file is corrupted or is not a recognized media file."
            )

        # Audio stream detection
        has_audio = bool(re.search(r"Stream #\d+:\d+.*Audio:", stderr))
        if not has_audio:
            raise ValueError(
                "No audio track was detected in this file.\n\n"
                "Please select a video or audio file that contains recorded sound."
            )

        # Parse duration
        duration_sec = 0.0
        dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", stderr)
        if dur_match:
            hours = int(dur_match.group(1))
            minutes = int(dur_match.group(2))
            seconds = float(dur_match.group(3))
            duration_sec = hours * 3600 + minutes * 60 + seconds

        format_match = re.search(r"Input #0,\s*([^,]+),", stderr)
        format_name = format_match.group(1) if format_match else file_path.suffix.lstrip(".")

        return MediaMetadata(
            path=file_path,
            file_size_bytes=file_size,
            duration_seconds=duration_sec,
            has_audio=has_audio,
            format_name=format_name,
        )

    @staticmethod
    def extract_16k_mono_wav(
        input_path: Path,
        output_wav_path: Path,
        cancel_event: threading.Event,
    ) -> None:
        """
        Extracts and converts any video or audio stream into a 16kHz mono 16-bit PCM WAV.
        Supports instantaneous cancellation by terminating the running FFmpeg process.
        """
        ffmpeg_exe = get_verified_ffmpeg_exe()
        cmd = [
            ffmpeg_exe,
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-i", str(input_path),
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            str(output_wav_path),
        ]

        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creation_flags,
        )

        while proc.poll() is None:
            if cancel_event.is_set():
                proc.kill()
                proc.wait()
                if proc.stdout:
                    proc.stdout.close()
                if proc.stderr:
                    proc.stderr.close()
                raise InterruptedError("Audio extraction was cancelled by the user.")
            time.sleep(0.05)

        stdout, stderr = proc.communicate()
        if proc.stdout:
            proc.stdout.close()
        if proc.stderr:
            proc.stderr.close()

        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg audio extraction failed:\n{(stderr or '').strip()}")


@dataclass
class OnlineClipInfo:
    """Represents metadata and temporary local audio path for a downloaded online clip."""
    url: str
    platform: str
    title: str
    sanitized_title: str
    video_id: str
    duration_seconds: float
    temp_media_path: Path


class OnlineMediaFetcher:
    """
    Fetches temporary audio streams from Instagram, YouTube, TikTok, Facebook, and 1,000+ sites
    using yt-dlp and the bundled static FFmpeg binary. Strictly writes into a caller-managed
    TemporaryDirectory so zero media files remain after transcription.
    """

    ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    @staticmethod
    def is_valid_url(url_str: str) -> bool:
        """Returns True if url_str is a well-formed HTTP/HTTPS URL."""
        cleaned = (url_str or "").strip()
        if not cleaned:
            return False
        try:
            parsed = urllib.parse.urlparse(cleaned)
            return parsed.scheme in ("http", "https") and bool(parsed.netloc) and "." in parsed.netloc
        except Exception:
            return False

    @staticmethod
    def detect_platform(url_str: str) -> str:
        """Returns a human-friendly platform name for UI badges and status messages."""
        try:
            host = urllib.parse.urlparse((url_str or "").strip()).netloc.lower()
        except Exception:
            host = ""
        if "instagram.com" in host or "instagr.am" in host:
            return "Instagram"
        if "youtube.com" in host or "youtu.be" in host:
            return "YouTube"
        if "tiktok.com" in host:
            return "TikTok"
        if "facebook.com" in host or "fb.watch" in host or "fb.com" in host:
            return "Facebook"
        return "Web Video"

    @staticmethod
    def sanitize_title(raw_title: str, fallback: str = "Online_Clip") -> str:
        """Cleans an online video title into a safe, readable cross-platform filename stem."""
        if not raw_title:
            return fallback
        # Strip filesystem-unsafe characters and control characters
        cleaned = re.sub(r'[\\/*?:"<>|\r\n\t]+', " ", raw_title)
        cleaned = "".join(ch for ch in cleaned if ch.isprintable())
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" .-_")
        if len(cleaned) > 80:
            cleaned = cleaned[:80].rstrip(" .-_")
        return cleaned if cleaned else fallback

    @classmethod
    def clean_error_message(cls, raw_err: str, platform: str) -> str:
        """Strips ANSI escape sequences and formats a friendly error message for creators."""
        clean = cls.ANSI_ESCAPE_RE.sub("", str(raw_err or "")).strip()
        clean = re.sub(r"^ERROR:\s*", "", clean, flags=re.IGNORECASE)
        lower = clean.lower()
        if any(k in lower for k in ("login required", "sign in", "cookies", "rate-limit", "private", "not available")):
            return (
                f"{platform} requires you to be logged in to access this clip (or the post is private).\n\n"
                "💡 Tip: In the 'Social Login' dropdown under Studio Preferences, select the browser "
                "where you are logged into your account (e.g. Safari or Chrome) and click Generate again!\n\n"
                f"Technical details: {clean}"
            )
        return f"Could not download audio from {platform} link:\n\n{clean}"

    @classmethod
    def download_audio_to_temp(
        cls,
        url: str,
        temp_dir: Path,
        cancel_event: threading.Event,
        status_cb: Callable[[str], None],
        progress_cb: Callable[[float], None],
        cookie_browser_label: str = DEFAULT_COOKIE_BROWSER,
    ) -> OnlineClipInfo:
        """
        Downloads only the best audio stream for the given URL into `temp_dir`.
        Aborts immediately if `cancel_event` is set.
        """
        import yt_dlp

        if not cls.is_valid_url(url):
            raise ValueError("Please enter a valid link starting with https:// or http://")

        if cancel_event.is_set():
            raise InterruptedError("Download was cancelled by the user.")

        platform = cls.detect_platform(url)
        status_cb(f"🌐 Connecting to {platform} and inspecting link...")

        def _progress_hook(d: dict) -> None:
            if cancel_event.is_set():
                raise InterruptedError("Download was cancelled by the user.")
            st = d.get("status")
            if st == "downloading":
                downloaded = d.get("downloaded_bytes") or 0
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                if total > 0:
                    pct = min(0.99, max(0.01, downloaded / total))
                    progress_cb(pct)
                    status_cb(f"📥 Downloading temporary audio from {platform} ({int(pct * 100)}%)...")
                else:
                    status_cb(f"📥 Downloading temporary audio from {platform}...")
            elif st == "finished":
                status_cb(f"✨ {platform} audio fetched! Preparing 16kHz mono stream...")

        outtmpl = str(temp_dir / "online_source_%(id)s.%(ext)s")
        base_opts = {
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "ffmpeg_location": get_verified_ffmpeg_exe(),
            "progress_hooks": [_progress_hook],
            "socket_timeout": 20,
            "retries": 2,
        }

        chosen_browser = COOKIE_BROWSER_OPTIONS.get(cookie_browser_label)
        attempts: List[Optional[str]] = []
        if chosen_browser:
            attempts.append(chosen_browser)
        else:
            # First try public (no cookies); if auth fails, automatically try installed browsers
            attempts.append(None)
            if sys.platform == "darwin":
                attempts.extend(["safari", "chrome", "firefox"])
            else:
                attempts.extend(["chrome", "edge", "firefox"])

        info_dict: Optional[dict] = None
        last_error: Optional[Exception] = None

        for idx, browser_name in enumerate(attempts):
            if cancel_event.is_set():
                raise InterruptedError("Download was cancelled by the user.")

            # Clean any partial files from previous attempt inside temp_dir
            for part_f in temp_dir.glob("online_source_*"):
                try:
                    part_f.unlink()
                except Exception:
                    pass

            opts = dict(base_opts)
            if browser_name:
                opts["cookiesfrombrowser"] = (browser_name,)
                if idx > 0:
                    status_cb(f"🔐 {platform} requested login — trying {browser_name.title()} cookies...")

            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info_dict = ydl.extract_info(url.strip(), download=True)
                if info_dict is not None:
                    break
            except InterruptedError:
                raise
            except Exception as err:
                err_str = str(err)
                if cancel_event.is_set() or "cancelled by the user" in err_str.lower():
                    raise InterruptedError("Download was cancelled by the user.")
                if idx == 0:
                    last_error = err
                    # Only auto-retry with browser cookies if it looks like an auth/login/cookie issue
                    lower_err = err_str.lower()
                    needs_auth = any(
                        w in lower_err
                        for w in ("login", "cookie", "sign in", "private", "rate-limit", "403", "forbidden", "instagram", "facebook")
                    )
                    if not needs_auth:
                        break
                else:
                    continue

        if info_dict is None:
            raise RuntimeError(cls.clean_error_message(str(last_error or "Unknown download error"), platform))

        # Locate the downloaded media file inside temp_dir
        downloaded_files = [
            p for p in temp_dir.glob("online_source_*")
            if p.is_file() and not p.name.endswith((".part", ".ytdl", ".json"))
        ]
        if not downloaded_files:
            raise RuntimeError(f"Failed to locate downloaded audio stream from {platform}.")

        temp_media_path = max(downloaded_files, key=lambda p: p.stat().st_size)
        video_id = str(info_dict.get("id") or "clip")
        raw_title = str(info_dict.get("title") or "").strip()
        if not raw_title or raw_title.lower() in ("video", "reel", "post"):
            raw_title = f"{platform}_{video_id}"
        sanitized_title = cls.sanitize_title(raw_title, fallback=f"{platform}_{video_id}")
        duration_sec = float(info_dict.get("duration") or 0.0)

        return OnlineClipInfo(
            url=url.strip(),
            platform=platform,
            title=raw_title,
            sanitized_title=sanitized_title,
            video_id=video_id,
            duration_seconds=duration_sec,
            temp_media_path=temp_media_path,
        )


# ---------------------------------------------------------------------------
# Background Transcription Worker & Hygiene Context Manager
# ---------------------------------------------------------------------------
class TranscriptionEngine:
    """
    Manages Whisper model loading (cached in memory) and executes transcription
    strictly inside a tempfile.TemporaryDirectory context manager to guarantee zero
    scratch files remain on disk.
    """

    def __init__(self):
        self._cached_model: Optional[WhisperModel] = None
        self._cached_model_name: Optional[str] = None
        self._lock = threading.Lock()

    @staticmethod
    def is_model_cached(model_size_or_path: str) -> bool:
        """Checks if the model weights are already downloaded locally."""
        try:
            from faster_whisper.utils import download_model
            download_model(model_size_or_path, local_files_only=True)
            return True
        except Exception:
            return False

    def get_model(self, model_size_or_path: str, status_cb: Callable[[str], None]) -> WhisperModel:
        """Retrieves or loads the requested faster-whisper model strictly configured for CPU."""
        with self._lock:
            if self._cached_model is not None and self._cached_model_name == model_size_or_path:
                return self._cached_model

            if self.is_model_cached(model_size_or_path):
                status_cb(f"⚡ Loading Whisper model ({model_size_or_path}) into memory...")
            else:
                status_cb(
                    f"📥 First-time setup: Downloading {model_size_or_path} model (~460MB)... "
                    "(One-time download. Future runs will be 100% offline!)"
                )

            model = WhisperModel(
                model_size_or_path,
                device="cpu",
                compute_type="int8",
                cpu_threads=4,
            )
            self._cached_model = model
            self._cached_model_name = model_size_or_path
            return model

    def run_transcription(
        self,
        media_file: Path,
        media_meta: MediaMetadata,
        model_name: str,
        output_dir: Path,
        cancel_event: threading.Event,
        status_cb: Callable[[str], None],
        progress_cb: Callable[[float], None],
        segment_cb: Callable[[TranscriptSegment], None],
        overwrite: bool = False,
    ) -> tuple[str, str, str, List[TranscriptSegment]]:
        """
        Executes the full pipeline:
        1. Validates disk space.
        2. Enters TemporaryDirectory context manager.
        3. Extracts 16kHz mono WAV scratch file.
        4. Transcribes audio with faster-whisper.
        5. Writes output transcripts to output_dir (overwriting or creating numbered copy based on user choice).
        6. Purges TemporaryDirectory upon exit under ALL conditions.
        """
        if not check_free_disk_space(output_dir, min_mb=MIN_DISK_SPACE_MB):
            raise IOError(
                f"Low disk space: The output drive has less than {MIN_DISK_SPACE_MB} MB free. "
                "Please free up disk space before proceeding."
            )

        temp_dir_path: Optional[Path] = None
        segments_collected: List[TranscriptSegment] = []

        with tempfile.TemporaryDirectory(prefix="faery_transcribe_") as temp_dir_str:
            temp_dir_path = Path(temp_dir_str)
            scratch_wav = temp_dir_path / "audio_16k_mono.wav"

            if cancel_event.is_set():
                raise InterruptedError("Transcription cancelled.")

            status_cb("Extracting audio to 16kHz mono WAV format...")
            MediaProcessor.extract_16k_mono_wav(media_file, scratch_wav, cancel_event)

            if cancel_event.is_set():
                raise InterruptedError("Transcription cancelled.")

            whisper_model = self.get_model(model_name, status_cb)

            if cancel_event.is_set():
                raise InterruptedError("Transcription cancelled.")

            status_cb("Transcribing (this may take 1-2 minutes for YouTube videos)...")

            segments_gen, info = whisper_model.transcribe(
                str(scratch_wav),
                language="en",
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
            )

            total_duration = media_meta.duration_seconds if media_meta.duration_seconds > 0 else (info.duration or 1.0)

            for segment in segments_gen:
                if cancel_event.is_set():
                    raise InterruptedError("Transcription cancelled.")

                seg_obj = TranscriptSegment(
                    start=segment.start,
                    end=segment.end,
                    text=segment.text.strip(),
                )
                segments_collected.append(seg_obj)
                segment_cb(seg_obj)

                if total_duration > 0:
                    pct = min(0.99, max(0.01, segment.end / total_duration))
                    progress_cb(pct)
                    status_cb(
                        f"Transcribing: [{seg_obj.formatted_timestamp} / {media_meta.formatted_duration}] "
                        f"({int(pct * 100)}%)..."
                    )

        if temp_dir_path and temp_dir_path.exists():
            shutil.rmtree(temp_dir_path, ignore_errors=True)

        if cancel_event.is_set():
            raise InterruptedError("Transcription cancelled.")

        # Build clean plain text, timecoded text, raw text, and Markdown representations
        paragraphs_text = TranscriptFormatter.to_paragraphs(segments_collected)
        timecoded_text = TranscriptFormatter.to_timecoded(segments_collected)
        markdown_text = self._build_markdown(media_meta, model_name, paragraphs_text, segments_collected)

        base_name = media_file.stem
        if overwrite:
            clean_txt_path = output_dir / f"{base_name}_paragraphs.txt"
            timecoded_txt_path = output_dir / f"{base_name}_timecoded.txt"
            md_path = output_dir / f"{base_name}_transcript.md"
        else:
            clean_txt_path = self._get_unique_path(output_dir / f"{base_name}_paragraphs.txt")
            timecoded_txt_path = self._get_unique_path(output_dir / f"{base_name}_timecoded.txt")
            md_path = self._get_unique_path(output_dir / f"{base_name}_transcript.md")

        with open(clean_txt_path, "w", encoding="utf-8") as f:
            f.write(paragraphs_text + "\n")

        with open(timecoded_txt_path, "w", encoding="utf-8") as f:
            f.write(timecoded_text + "\n")

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(markdown_text + "\n")

        return str(clean_txt_path), str(timecoded_txt_path), str(md_path), segments_collected

    def run_online_transcription(
        self,
        url: str,
        model_name: str,
        output_dir: Path,
        cancel_event: threading.Event,
        status_cb: Callable[[str], None],
        progress_cb: Callable[[float], None],
        segment_cb: Callable[[TranscriptSegment], None],
        cookie_browser_label: str = DEFAULT_COOKIE_BROWSER,
        overwrite: Optional[bool] = None,
        overwrite_prompt_cb: Optional[Callable[[str, Path], Optional[bool]]] = None,
    ) -> tuple[str, str, str, List[TranscriptSegment], str, str]:
        """
        Executes the full online link pipeline with 100% scratch file hygiene:
        1. Validates disk space.
        2. Enters TemporaryDirectory context manager.
        3. Downloads temporary audio stream via yt-dlp directly into TemporaryDirectory.
        4. Converts audio to 16kHz mono WAV and immediately purges the downloaded stream.
        5. Transcribes audio with faster-whisper on CPU.
        6. Purges TemporaryDirectory upon exit under ALL conditions (success, error, cancel).
        7. Saves output transcripts named after the video's title.
        """
        if not check_free_disk_space(output_dir, min_mb=MIN_DISK_SPACE_MB):
            raise IOError(
                f"Low disk space: The output drive has less than {MIN_DISK_SPACE_MB} MB free. "
                "Please free up disk space before proceeding."
            )

        temp_dir_path: Optional[Path] = None
        segments_collected: List[TranscriptSegment] = []
        clip_info: Optional[OnlineClipInfo] = None
        probed_meta: Optional[MediaMetadata] = None

        with tempfile.TemporaryDirectory(prefix="faery_transcribe_") as temp_dir_str:
            temp_dir_path = Path(temp_dir_str)
            scratch_wav = temp_dir_path / "audio_16k_mono.wav"

            # 1. Download temporary audio into temp_dir_path
            clip_info = OnlineMediaFetcher.download_audio_to_temp(
                url=url,
                temp_dir=temp_dir_path,
                cancel_event=cancel_event,
                status_cb=status_cb,
                progress_cb=progress_cb,
                cookie_browser_label=cookie_browser_label,
            )

            if cancel_event.is_set():
                raise InterruptedError("Transcription cancelled.")

            # 2. Convert to 16kHz mono WAV inside temp_dir_path
            status_cb(f"🎵 Extracting 16kHz mono audio for '{clip_info.sanitized_title}'...")
            MediaProcessor.extract_16k_mono_wav(clip_info.temp_media_path, scratch_wav, cancel_event)

            # Immediately purge the raw downloaded audio stream
            try:
                if clip_info.temp_media_path.exists():
                    clip_info.temp_media_path.unlink()
            except Exception:
                pass

            if cancel_event.is_set():
                raise InterruptedError("Transcription cancelled.")

            # Probe the converted WAV for exact duration
            wav_meta = MediaProcessor.probe_file(scratch_wav)
            eff_duration = wav_meta.duration_seconds if wav_meta.duration_seconds > 0 else clip_info.duration_seconds
            probed_meta = MediaMetadata(
                path=Path(f"{clip_info.sanitized_title}.mp4"),
                file_size_bytes=wav_meta.file_size_bytes,
                duration_seconds=eff_duration,
                has_audio=True,
                format_name=clip_info.platform,
            )

            # 3. Load Whisper model & transcribe
            whisper_model = self.get_model(model_name, status_cb)

            if cancel_event.is_set():
                raise InterruptedError("Transcription cancelled.")

            status_cb(f"🎙️ Transcribing '{clip_info.sanitized_title}'...")

            segments_gen, info = whisper_model.transcribe(
                str(scratch_wav),
                language="en",
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
            )

            total_duration = probed_meta.duration_seconds if probed_meta.duration_seconds > 0 else (info.duration or 1.0)

            for segment in segments_gen:
                if cancel_event.is_set():
                    raise InterruptedError("Transcription cancelled.")

                seg_obj = TranscriptSegment(
                    start=segment.start,
                    end=segment.end,
                    text=segment.text.strip(),
                )
                segments_collected.append(seg_obj)
                segment_cb(seg_obj)

                if total_duration > 0:
                    pct = min(0.99, max(0.01, segment.end / total_duration))
                    progress_cb(pct)
                    status_cb(
                        f"Transcribing: [{seg_obj.formatted_timestamp} / {probed_meta.formatted_duration}] "
                        f"({int(pct * 100)}%)..."
                    )

        # Guarantee temp directory is completely removed from disk
        if temp_dir_path and temp_dir_path.exists():
            shutil.rmtree(temp_dir_path, ignore_errors=True)

        if cancel_event.is_set() or clip_info is None or probed_meta is None:
            raise InterruptedError("Transcription cancelled.")

        base_name = clip_info.sanitized_title
        existing_p = output_dir / f"{base_name}_paragraphs.txt"
        existing_m = output_dir / f"{base_name}_transcript.md"

        if overwrite is None:
            if (existing_p.exists() or existing_m.exists()) and overwrite_prompt_cb is not None:
                ans = overwrite_prompt_cb(base_name, existing_p if existing_p.exists() else existing_m)
                if ans is None:
                    raise InterruptedError("Transcription cancelled.")
                overwrite = ans
            else:
                overwrite = False

        paragraphs_text = TranscriptFormatter.to_paragraphs(segments_collected)
        timecoded_text = TranscriptFormatter.to_timecoded(segments_collected)
        markdown_text = self._build_markdown(
            probed_meta,
            model_name,
            paragraphs_text,
            segments_collected,
            source_url=clip_info.url,
            platform=clip_info.platform,
        )

        if overwrite:
            clean_txt_path = output_dir / f"{base_name}_paragraphs.txt"
            timecoded_txt_path = output_dir / f"{base_name}_timecoded.txt"
            md_path = output_dir / f"{base_name}_transcript.md"
        else:
            clean_txt_path = self._get_unique_path(output_dir / f"{base_name}_paragraphs.txt")
            timecoded_txt_path = self._get_unique_path(output_dir / f"{base_name}_timecoded.txt")
            md_path = self._get_unique_path(output_dir / f"{base_name}_transcript.md")

        with open(clean_txt_path, "w", encoding="utf-8") as f:
            f.write(paragraphs_text + "\n")

        with open(timecoded_txt_path, "w", encoding="utf-8") as f:
            f.write(timecoded_text + "\n")

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(markdown_text + "\n")

        return (
            str(clean_txt_path),
            str(timecoded_txt_path),
            str(md_path),
            segments_collected,
            base_name,
            probed_meta.formatted_duration,
        )

    @staticmethod
    def _get_unique_path(target_path: Path) -> Path:
        """Appends a numeric index if target_path already exists."""
        if not target_path.exists():
            return target_path
        parent = target_path.parent
        stem = target_path.stem
        suffix = target_path.suffix
        counter = 1
        while True:
            candidate = parent / f"{stem}_{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1

    @staticmethod
    def _build_markdown(
        meta: MediaMetadata,
        model_name: str,
        paragraphs_text: str,
        segments: List[TranscriptSegment],
        source_url: Optional[str] = None,
        platform: Optional[str] = None,
    ) -> str:
        """Constructs a clean, production-grade Markdown document with YouTube timestamps."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        title_str = meta.path.stem if source_url else meta.path.name
        lines = [
            f"# Transcription: {title_str}",
            "",
            "### Metadata",
        ]
        if source_url:
            lines.append(f"- **Source Link:** {source_url} ({platform or 'Online Clip'})")
        else:
            lines.append(f"- **Source File:** `{meta.path.name}`")
            lines.append(f"- **File Size:** {meta.formatted_size}")
        lines.extend([
            f"- **Audio Duration:** {meta.formatted_duration}",
            f"- **Engine Model:** `{model_name}` (CPU int8)",
            f"- **Generated On:** {now_str}",
            "",
            "---",
            "",
            "## Formatted Transcript (Clean Paragraphs)",
            paragraphs_text if paragraphs_text else "*(No speech detected)*",
            "",
            "---",
            "",
            "## YouTube Chapters & Timestamps",
        ])
        if segments:
            for seg in segments:
                lines.append(f"- **[{seg.formatted_timestamp}]** {seg.text}")
        else:
            lines.append("*(No timestamped segments)*")

        lines.append("")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Modern CustomTkinter User Interface with Tabs & CRUD Library
# ---------------------------------------------------------------------------
class FaeryTranscriberApp(ctk.CTk):
    """
    Main Application Window built with CustomTkinter.
    Features:
    - High-DPI modern aesthetic with tabbed layout (Transcribe & History Library).
    - Non-blocking multithreading to eliminate beachballs/freezes.
    - Real-time live formatted preview with automatic pause detection.
    - Overwrite prompt handling for re-transcribed media clips.
    - Historical Transcripts Manager with complete CRUD operations (Create, Read, Update/Rename, Delete).
    - Instant clipboard copy with animated visual feedback.
    - Direct export and cross-platform output folder navigation.
    """

    def __init__(self):
        # Apply Faery Good theme before initializing CTk root
        apply_faery_good_theme()
        super().__init__()

        # Configuration, Brand Assets, and Engine instances
        self.config = ConfigManager()
        self.history = HistoryManager()
        self.engine = TranscriptionEngine()
        self.brand = BrandAssets()

        # State tracking
        self.selected_file: Optional[Path] = None
        self.selected_metadata: Optional[MediaMetadata] = None
        self.selected_url: Optional[str] = None
        self.worker_thread: Optional[threading.Thread] = None
        self.cancel_event = threading.Event()
        self.is_transcribing = False
        self.last_saved_clean_path: Optional[str] = None
        self.last_saved_timecoded_path: Optional[str] = None
        self.last_saved_md_path: Optional[str] = None
        self.current_segments: List[TranscriptSegment] = []

        # History view tracking
        self.selected_history_id: Optional[str] = None

        # Window configuration & Faery Good Icon
        self.title(f"{APP_NAME}  —  Whimsy is Power")
        self.geometry("1040x820")
        self.minsize(900, 700)
        self.configure(fg_color=FAERY_LAVENDER_BG)
        self.brand.apply_window_icon(self)

        ctk.set_appearance_mode(self.config.appearance_mode)

        # Apple-style Typography + Faery Good Editorial Serif
        sys_sans = ".AppleSystemUIFont" if sys.platform == "darwin" else "Segoe UI"
        self.font_serif_title = ctk.CTkFont(family="Georgia", size=17, weight="bold")
        self.font_serif_card = ctk.CTkFont(family="Georgia", size=13, weight="bold")
        self.font_serif_italic = ctk.CTkFont(family="Georgia", size=12, slant="italic")
        self.font_body = ctk.CTkFont(family=sys_sans, size=12)
        self.font_body_bold = ctk.CTkFont(family=sys_sans, size=12, weight="bold")
        self.font_small = ctk.CTkFont(family=sys_sans, size=11)
        self.font_section_caps = ctk.CTkFont(family=sys_sans, size=10, weight="bold")
        self.font_editor = ctk.CTkFont(family=sys_sans, size=13)

        # Intercept window close to clean up gracefully
        self.protocol("WM_DELETE_WINDOW", self._on_window_close)

        # Build GUI
        self._build_ui()
        self._build_menu_bar()
        self._setup_shortcuts()

        # Initial data sync
        self._update_output_dir_label()
        self._refresh_history_list()

    def _build_ui(self) -> None:
        """Constructs an Apple Sonoma-inspired Unified Toolbar and Bento workspace with Faery Good whimsy."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # -------------------------------------------------------------------
        # Apple Unified Top Toolbar (Brand Left | Segmented Nav Center | Pills Right)
        # -------------------------------------------------------------------
        header_frame = ctk.CTkFrame(
            self,
            corner_radius=16,
            fg_color=FAERY_CREAM_CARD,
            border_width=1,
            border_color=FAERY_CARD_BORDER,
        )
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(14, 10))
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_columnconfigure(1, weight=0)
        header_frame.grid_columnconfigure(2, weight=1)

        # Left: Faery Good Watercolor Mascot + Cursive Wordmark + Subtle Tagline
        brand_cluster = ctk.CTkFrame(header_frame, fg_color="transparent")
        brand_cluster.grid(row=0, column=0, sticky="w", padx=16, pady=8)

        if self.brand.mascot_header is not None:
            mascot_lbl = ctk.CTkLabel(brand_cluster, text="", image=self.brand.mascot_header)
            mascot_lbl.pack(side="left", padx=(0, 10))

        brand_text_col = ctk.CTkFrame(brand_cluster, fg_color="transparent")
        brand_text_col.pack(side="left")

        logo_row = ctk.CTkFrame(brand_text_col, fg_color="transparent")
        logo_row.pack(anchor="w")

        if self.brand.logo_header is not None:
            logo_lbl = ctk.CTkLabel(logo_row, text="", image=self.brand.logo_header)
            logo_lbl.pack(side="left", padx=(0, 8))
        else:
            title_label = ctk.CTkLabel(
                logo_row,
                text="Faery Good",
                font=ctk.CTkFont(family="Georgia", size=20, weight="bold"),
                text_color=FAERY_PURPLE,
            )
            title_label.pack(side="left", padx=(0, 8))

        studio_badge = ctk.CTkLabel(
            logo_row,
            text="STUDIO",
            font=self.font_section_caps,
            fg_color=FAERY_SECONDARY_BTN,
            text_color=FAERY_SECONDARY_TEXT,
            corner_radius=8,
            padx=8,
            pady=1,
        )
        studio_badge.pack(side="left", pady=(2, 0))

        subtitle_label = ctk.CTkLabel(
            brand_text_col,
            text="Whimsy is Power  ·  On-Device Reels & YouTube Transcriber",
            font=self.font_small,
            text_color=FAERY_TEXT_MUTED,
        )
        subtitle_label.pack(anchor="w")

        # Center: Native macOS Sonoma-Style Segmented Mode Switcher
        nav_container = ctk.CTkFrame(header_frame, fg_color="transparent")
        nav_container.grid(row=0, column=1, padx=12, pady=8)

        # Workspace Container (Holds Tab Views without an ugly outer Tabview border box)
        self.workspace_container = ctk.CTkFrame(self, fg_color="transparent")
        self.workspace_container.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 16))
        self.workspace_container.grid_columnconfigure(0, weight=1)
        self.workspace_container.grid_rowconfigure(0, weight=1)

        self.tab_transcribe = ctk.CTkFrame(self.workspace_container, fg_color="transparent")
        self.tab_history = ctk.CTkFrame(self.workspace_container, fg_color="transparent")

        class _UnifiedTabController:
            """Apple-style unified toolbar tab controller compatible with CTkTabview API."""
            def __init__(self, parent_app: FaeryTranscriberApp, seg_parent: ctk.CTkFrame):
                self._app = parent_app
                self._tabs = {
                    "🎙️ Transcribe": parent_app.tab_transcribe,
                    "📜 History": parent_app.tab_history,
                }
                self._current = "🎙️ Transcribe"
                self.segmented = FaerySegmentedButton(
                    seg_parent,
                    values=["🎙️ Transcribe", "📜 History"],
                    command=self.set,
                    height=34,
                    corner_radius=17,
                    font=parent_app.font_body_bold,
                    fg_color=FAERY_SEGMENT_TRACK,
                    selected_color=FAERY_PURPLE,
                    selected_hover_color=FAERY_PURPLE_HOVER,
                    unselected_color=FAERY_SEGMENT_TRACK,
                    unselected_hover_color=FAERY_SEGMENT_HOVER,
                    selected_text_color=("#FCF4ED", "#FCF4ED"),
                    unselected_text_color=FAERY_SECONDARY_TEXT,
                    text_color_disabled=FAERY_TEXT_MUTED,
                )
                self.segmented.set("🎙️ Transcribe")
                self.segmented.pack()
                parent_app.tab_transcribe.grid(row=0, column=0, sticky="nsew")

            def set(self, name: str) -> None:
                if name not in self._tabs:
                    return
                self._current = name
                if self.segmented.get() != name:
                    self.segmented.set(name)
                for k, frame in self._tabs.items():
                    if k == name:
                        frame.grid(row=0, column=0, sticky="nsew")
                    else:
                        frame.grid_forget()
                if "History" in name:
                    self._app._refresh_history_list(filter_text=None, resync=True)

            def get(self) -> str:
                return self._current

        self.tabview = _UnifiedTabController(self, nav_container)

        # Right: Minimal Borderless Apple Tinted Toolbar Pills
        toolbar_right = ctk.CTkFrame(header_frame, fg_color="transparent")
        toolbar_right.grid(row=0, column=2, sticky="e", padx=16, pady=8)

        site_btn = ctk.CTkButton(
            toolbar_right,
            text="🦋 FaeryGood.com",
            width=126,
            height=30,
            corner_radius=15,
            fg_color=FAERY_ROSE_CARD,
            hover_color=FAERY_SECONDARY_HOVER,
            text_color=FAERY_SECONDARY_TEXT,
            border_width=0,
            font=self.font_body_bold,
            command=lambda: webbrowser.open(BRAND_WEBSITE),
        )
        site_btn.pack(side="left", padx=(0, 6))

        guide_btn = ctk.CTkButton(
            toolbar_right,
            text="✨ Guide",
            width=76,
            height=30,
            corner_radius=15,
            fg_color=FAERY_SECONDARY_BTN,
            hover_color=FAERY_SECONDARY_HOVER,
            text_color=FAERY_SECONDARY_TEXT,
            border_width=0,
            font=self.font_body_bold,
            command=self._show_quick_guide,
        )
        guide_btn.pack(side="left", padx=(0, 6))

        self.theme_menu = ctk.CTkOptionMenu(
            toolbar_right,
            values=["Light", "Dark", "System"],
            command=self._on_theme_changed,
            width=92,
            height=30,
            corner_radius=15,
            font=self.font_body_bold,
            fg_color=FAERY_SECONDARY_BTN,
            button_color=FAERY_SECONDARY_HOVER,
            button_hover_color=FAERY_CARD_BORDER,
            text_color=FAERY_SECONDARY_TEXT,
        )
        self.theme_menu.set(self.config.appearance_mode)
        self.theme_menu.pack(side="left")

        self._build_transcribe_tab()
        self._build_history_tab()

    # -----------------------------------------------------------------------
    # Tab 1: Transcribe Studio Layout (Apple Bento Inspector + Notes Canvas)
    # -----------------------------------------------------------------------
    def _build_transcribe_tab(self) -> None:
        tab = self.tab_transcribe
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)  # Row 1 (Editor Canvas) expands maximally

        # -------------------------------------------------------------------
        # Row 0: 2-Column Apple Bento Inspector (Media Source | Studio Settings)
        # -------------------------------------------------------------------
        bento_row = ctk.CTkFrame(tab, fg_color="transparent")
        bento_row.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        bento_row.grid_columnconfigure(0, weight=5)
        bento_row.grid_columnconfigure(1, weight=6)

        # Left Bento Card: Source Media (Local Files + Online Social Links)
        file_card = ctk.CTkFrame(
            bento_row,
            corner_radius=16,
            fg_color=FAERY_CREAM_CARD,
            border_width=1,
            border_color=FAERY_CARD_BORDER,
        )
        file_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        file_card.grid_columnconfigure(0, weight=1)

        file_top_bar = ctk.CTkFrame(file_card, fg_color="transparent")
        file_top_bar.grid(row=0, column=0, sticky="ew", padx=16, pady=(10, 2))
        file_top_bar.grid_columnconfigure(0, weight=1)

        source_badge = ctk.CTkLabel(
            file_top_bar,
            text="  SOURCE MEDIA" if self.brand.icon_butterfly else "🦋 SOURCE MEDIA",
            image=self.brand.icon_butterfly,
            compound="left",
            font=self.font_section_caps,
            text_color=FAERY_TEXT_MUTED,
            anchor="w",
        )
        source_badge.grid(row=0, column=0, sticky="w")

        self.select_file_btn = ctk.CTkButton(
            file_top_bar,
            text="📁 Select Local File…",
            font=self.font_body_bold,
            fg_color=FAERY_PURPLE,
            hover_color=FAERY_PURPLE_HOVER,
            text_color=("#FCF4ED", "#FCF4ED"),
            text_color_disabled=("#E8DCF7", "#D4C2EB"),
            corner_radius=14,
            command=self._on_select_file_clicked,
            width=158,
            height=28,
        )
        self.select_file_btn.grid(row=0, column=1, sticky="e")

        self.file_name_label = ctk.CTkLabel(
            file_card,
            text="No clip or link selected yet",
            font=self.font_serif_card,
            text_color=FAERY_TEXT_PRIMARY,
            anchor="w",
        )
        self.file_name_label.grid(row=1, column=0, sticky="ew", padx=16, pady=(1, 0))

        self.file_meta_label = ctk.CTkLabel(
            file_card,
            text="Select a local file or paste an Instagram, YouTube, TikTok, or Facebook link below",
            font=self.font_small,
            text_color=FAERY_TEXT_MUTED,
            anchor="w",
        )
        self.file_meta_label.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 6))

        # Online Link Input Row (Instagram / YouTube / TikTok / Facebook)
        url_bar_frame = ctk.CTkFrame(file_card, fg_color="transparent")
        url_bar_frame.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 11))
        url_bar_frame.grid_columnconfigure(0, weight=1)

        self.url_entry = ctk.CTkEntry(
            url_bar_frame,
            placeholder_text="🔗 Paste Instagram, YouTube, TikTok, or Facebook link…",
            height=28,
            corner_radius=10,
            border_width=1,
            border_color=FAERY_DIVIDER,
            fg_color=FAERY_LAVENDER_BG,
            text_color=FAERY_TEXT_PRIMARY,
            font=self.font_small,
        )
        self.url_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.url_entry.bind("<KeyRelease>", self._on_url_entry_changed)
        self.url_entry.bind("<Return>", lambda e: self._on_generate_clicked())

        self.paste_url_btn = ctk.CTkButton(
            url_bar_frame,
            text="📋 Paste Link",
            width=102,
            height=28,
            corner_radius=14,
            fg_color=FAERY_SECONDARY_BTN,
            hover_color=FAERY_SECONDARY_HOVER,
            text_color=FAERY_SECONDARY_TEXT,
            text_color_disabled=FAERY_SECONDARY_DISABLED_TEXT,
            border_width=0,
            font=self.font_body_bold,
            command=self._on_paste_url_clicked,
        )
        self.paste_url_btn.grid(row=0, column=1, sticky="e")

        # Right Bento Card: Studio Preferences (Apple Settings Group Style)
        settings_card = ctk.CTkFrame(
            bento_row,
            corner_radius=16,
            fg_color=FAERY_CREAM_CARD,
            border_width=1,
            border_color=FAERY_CARD_BORDER,
        )
        settings_card.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        settings_card.grid_columnconfigure(1, weight=1)

        # Row 0: Transcription Engine
        model_label = ctk.CTkLabel(
            settings_card,
            text="  Transcription Engine" if self.brand.icon_mortar else "🌿 Transcription Engine",
            image=self.brand.icon_mortar,
            compound="left",
            font=self.font_body_bold,
            text_color=FAERY_TEXT_PRIMARY,
        )
        model_label.grid(row=0, column=0, padx=(16, 12), pady=(10, 6), sticky="w")

        self.model_dropdown = ctk.CTkOptionMenu(
            settings_card,
            values=list(MODEL_DISPLAY_NAMES.keys()),
            command=self._on_model_changed,
            height=26,
            width=255,
            corner_radius=13,
            font=self.font_small,
            fg_color=FAERY_SECONDARY_BTN,
            button_color=FAERY_SECONDARY_HOVER,
            button_hover_color=FAERY_CARD_BORDER,
            text_color=FAERY_SECONDARY_TEXT,
        )
        self.model_dropdown.set(self.config.model_selection)
        self.model_dropdown.grid(row=0, column=1, padx=(0, 16), pady=(10, 6), sticky="e")

        # 1px Apple Settings Divider
        divider = ctk.CTkFrame(settings_card, height=1, fg_color=FAERY_DIVIDER)
        divider.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16)

        # Row 2: Output Folder
        out_label = ctk.CTkLabel(
            settings_card,
            text="  Output Folder" if self.brand.icon_sprig else "🌸 Output Folder",
            image=self.brand.icon_sprig,
            compound="left",
            font=self.font_body_bold,
            text_color=FAERY_TEXT_PRIMARY,
        )
        out_label.grid(row=2, column=0, padx=(16, 12), pady=(6, 6), sticky="w")

        out_path_subframe = ctk.CTkFrame(settings_card, fg_color="transparent")
        out_path_subframe.grid(row=2, column=1, padx=(0, 16), pady=(6, 6), sticky="ew")
        out_path_subframe.grid_columnconfigure(0, weight=1)

        self.out_path_entry = ctk.CTkEntry(
            out_path_subframe,
            height=26,
            corner_radius=10,
            border_width=1,
            border_color=FAERY_DIVIDER,
            fg_color=FAERY_LAVENDER_BG,
            text_color=FAERY_TEXT_PRIMARY,
            font=self.font_small,
        )
        self.out_path_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.out_path_entry.configure(state="readonly")

        self.change_folder_btn = ctk.CTkButton(
            out_path_subframe,
            text="Change…",
            width=80,
            height=26,
            corner_radius=13,
            fg_color=FAERY_SECONDARY_BTN,
            hover_color=FAERY_SECONDARY_HOVER,
            text_color=FAERY_SECONDARY_TEXT,
            text_color_disabled=FAERY_SECONDARY_DISABLED_TEXT,
            border_width=0,
            font=self.font_body_bold,
            command=self._on_change_folder_clicked,
        )
        self.change_folder_btn.grid(row=0, column=1, sticky="e")

        # 1px Apple Settings Divider
        divider2 = ctk.CTkFrame(settings_card, height=1, fg_color=FAERY_DIVIDER)
        divider2.grid(row=3, column=0, columnspan=2, sticky="ew", padx=16)

        # Row 4: Social Login (Browser Cookies for Instagram/Facebook Reels)
        cookie_label = ctk.CTkLabel(
            settings_card,
            text="  Social Login" if self.brand.icon_butterfly else "🔐 Social Login",
            image=self.brand.icon_butterfly,
            compound="left",
            font=self.font_body_bold,
            text_color=FAERY_TEXT_PRIMARY,
        )
        cookie_label.grid(row=4, column=0, padx=(16, 12), pady=(6, 10), sticky="w")

        self.cookie_dropdown = ctk.CTkOptionMenu(
            settings_card,
            values=list(COOKIE_BROWSER_OPTIONS.keys()),
            command=self._on_cookie_browser_changed,
            height=26,
            width=255,
            corner_radius=13,
            font=self.font_small,
            fg_color=FAERY_SECONDARY_BTN,
            button_color=FAERY_SECONDARY_HOVER,
            button_hover_color=FAERY_CARD_BORDER,
            text_color=FAERY_SECONDARY_TEXT,
        )
        self.cookie_dropdown.set(self.config.cookie_browser)
        self.cookie_dropdown.grid(row=4, column=1, padx=(0, 16), pady=(6, 10), sticky="e")

        # -------------------------------------------------------------------
        # Row 1: Distraction-Free Document Canvas (Apple Notes / Pages Style)
        # -------------------------------------------------------------------
        result_card = ctk.CTkFrame(
            tab,
            corner_radius=16,
            fg_color=FAERY_CREAM_CARD,
            border_width=1,
            border_color=FAERY_CARD_BORDER,
        )
        result_card.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        result_card.grid_columnconfigure(0, weight=1)
        result_card.grid_rowconfigure(2, weight=1)

        result_header = ctk.CTkFrame(result_card, fg_color="transparent")
        result_header.grid(row=0, column=0, sticky="ew", padx=18, pady=(12, 8))
        result_header.grid_columnconfigure(0, weight=0)
        result_header.grid_columnconfigure(1, weight=1)
        result_header.grid_columnconfigure(2, weight=0)

        title_left = ctk.CTkFrame(result_header, fg_color="transparent")
        title_left.grid(row=0, column=0, sticky="w")

        result_title = ctk.CTkLabel(
            title_left,
            text="✨ Transcript Canvas",
            font=self.font_serif_card,
            text_color=FAERY_TEXT_PRIMARY,
        )
        result_title.pack(side="left", padx=(0, 10))

        self.stats_badge = ctk.CTkLabel(
            title_left,
            text="0 words  |  0 characters",
            font=self.font_small,
            fg_color=FAERY_ROSE_CARD,
            text_color=FAERY_SECONDARY_TEXT,
            corner_radius=10,
            padx=10,
            pady=2,
        )
        self.stats_badge.pack(side="left")

        self.view_selector = FaerySegmentedButton(
            result_header,
            values=["📄 Clean Paragraphs", "⏱️ Timecoded (YouTube)", "📝 Raw Text"],
            command=self._on_view_mode_changed,
            height=30,
            corner_radius=15,
            font=self.font_small,
            fg_color=FAERY_SEGMENT_TRACK,
            selected_color=FAERY_PURPLE,
            selected_hover_color=FAERY_PURPLE_HOVER,
            unselected_color=FAERY_SEGMENT_TRACK,
            unselected_hover_color=FAERY_SEGMENT_HOVER,
            selected_text_color=("#FCF4ED", "#FCF4ED"),
            unselected_text_color=FAERY_SECONDARY_TEXT,
        )
        self.view_selector.set("📄 Clean Paragraphs")
        self.view_selector.grid(row=0, column=2, sticky="e")

        canvas_divider = ctk.CTkFrame(result_card, height=1, fg_color=FAERY_DIVIDER)
        canvas_divider.grid(row=1, column=0, sticky="ew", padx=18)

        self.textbox = ctk.CTkTextbox(
            result_card,
            wrap="word",
            font=self.font_editor,
            corner_radius=12,
            border_width=0,
            fg_color=FAERY_CREAM_CARD,
            text_color=FAERY_TEXT_PRIMARY,
        )
        self.textbox.grid(row=2, column=0, sticky="nsew", padx=14, pady=(6, 12))
        self.textbox.bind("<KeyRelease>", self._update_stats)

        # -------------------------------------------------------------------
        # Row 2: Unified Floating Dock Bar (Primary Action + Status + Exports)
        # -------------------------------------------------------------------
        action_card = ctk.CTkFrame(
            tab,
            corner_radius=16,
            fg_color=FAERY_CREAM_CARD,
            border_width=1,
            border_color=FAERY_CARD_BORDER,
        )
        action_card.grid(row=2, column=0, sticky="ew")
        action_card.grid_columnconfigure(1, weight=1)

        # Left Dock: Primary Generate + Cancel
        left_dock = ctk.CTkFrame(action_card, fg_color="transparent")
        left_dock.grid(row=0, column=0, padx=(14, 10), pady=12, sticky="w")

        self.generate_btn = ctk.CTkButton(
            left_dock,
            text="✨ Generate Transcript",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=FAERY_PURPLE,
            hover_color=FAERY_PURPLE_HOVER,
            text_color=("#FCF4ED", "#FCF4ED"),
            text_color_disabled=("#E8DCF7", "#D4C2EB"),
            corner_radius=19,
            command=self._on_generate_clicked,
            width=192,
            height=38,
        )
        self.generate_btn.pack(side="left", padx=(0, 6))

        self.cancel_btn = ctk.CTkButton(
            left_dock,
            text="Cancel",
            font=self.font_body_bold,
            fg_color=FAERY_SEGMENT_TRACK,
            hover_color=FAERY_SEGMENT_HOVER,
            text_color=FAERY_TEXT_MUTED,
            text_color_disabled=FAERY_SECONDARY_DISABLED_TEXT,
            corner_radius=19,
            command=self._on_cancel_clicked,
            width=74,
            height=38,
            state="disabled",
        )
        self.cancel_btn.pack(side="left")

        # Center Dock: Live Status & Sleek 6px Apple Progress Bar
        center_dock = ctk.CTkFrame(action_card, fg_color="transparent")
        center_dock.grid(row=0, column=1, padx=8, pady=10, sticky="ew")
        center_dock.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            center_dock,
            text="✨ Ready — Select a video or audio clip to begin.",
            font=self.font_small,
            text_color=FAERY_TEXT_MUTED,
            anchor="w",
        )
        self.status_label.grid(row=0, column=0, sticky="ew", pady=(0, 4))

        self.progress_bar = ctk.CTkProgressBar(
            center_dock,
            height=6,
            corner_radius=3,
            fg_color=FAERY_SEGMENT_TRACK,
            progress_color=FAERY_PURPLE,
        )
        self.progress_bar.grid(row=1, column=0, sticky="ew")
        self.progress_bar.set(0.0)

        # Right Dock: Borderless Apple-Tinted Export Pills
        right_dock = ctk.CTkFrame(action_card, fg_color="transparent")
        right_dock.grid(row=0, column=2, padx=(10, 14), pady=12, sticky="e")

        self.copy_btn = ctk.CTkButton(
            right_dock,
            text="📋 Copy to Clipboard",
            width=142,
            height=34,
            corner_radius=17,
            fg_color=FAERY_SECONDARY_BTN,
            hover_color=FAERY_SECONDARY_HOVER,
            text_color=FAERY_SECONDARY_TEXT,
            border_width=0,
            font=self.font_body_bold,
            command=self._on_copy_clicked,
        )
        self.copy_btn.pack(side="left", padx=(0, 6))
        self.default_btn_fg = self.copy_btn.cget("fg_color")

        self.save_txt_btn = ctk.CTkButton(
            right_dock,
            text="💾 .txt",
            width=72,
            height=34,
            corner_radius=17,
            fg_color=FAERY_SECONDARY_BTN,
            hover_color=FAERY_SECONDARY_HOVER,
            text_color=FAERY_SECONDARY_TEXT,
            border_width=0,
            font=self.font_body_bold,
            command=self._on_save_txt_clicked,
        )
        self.save_txt_btn.pack(side="left", padx=(0, 6))

        self.save_md_btn = ctk.CTkButton(
            right_dock,
            text="📝 .md",
            width=72,
            height=34,
            corner_radius=17,
            fg_color=FAERY_SECONDARY_BTN,
            hover_color=FAERY_SECONDARY_HOVER,
            text_color=FAERY_SECONDARY_TEXT,
            border_width=0,
            font=self.font_body_bold,
            command=self._on_save_md_clicked,
        )
        self.save_md_btn.pack(side="left", padx=(0, 6))

        self.open_folder_btn = ctk.CTkButton(
            right_dock,
            text="📂 Folder",
            width=88,
            height=34,
            corner_radius=17,
            fg_color=FAERY_ROSE_CARD,
            hover_color=FAERY_SECONDARY_HOVER,
            text_color=FAERY_SECONDARY_TEXT,
            border_width=0,
            font=self.font_body_bold,
            command=self._on_open_folder_clicked,
        )
        self.open_folder_btn.pack(side="left")

    # -----------------------------------------------------------------------
    # Tab 2: Historical Transcripts Manager (Apple Split-View Sidebar + Canvas)
    # -----------------------------------------------------------------------
    def _build_history_tab(self) -> None:
        tab = self.tab_history
        tab.grid_columnconfigure(0, weight=0)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        # Left Column: Apple Sidebar for Search & Transcript List
        left_panel = ctk.CTkFrame(
            tab,
            width=320,
            corner_radius=16,
            fg_color=FAERY_CREAM_CARD,
            border_width=1,
            border_color=FAERY_CARD_BORDER,
        )
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left_panel.grid_columnconfigure(0, weight=1)
        left_panel.grid_rowconfigure(2, weight=1)

        # Spotlight-style Rounded Search Input Container with integrated Clear (✕) pill
        search_box_frame = ctk.CTkFrame(
            left_panel,
            fg_color="transparent",
            height=36,
        )
        search_box_frame.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))
        search_box_frame.grid_columnconfigure(0, weight=1)

        self.history_search_entry = ctk.CTkEntry(
            search_box_frame,
            placeholder_text="🔍 Search transcripts & spoken content…",
            height=34,
            corner_radius=17,
            border_width=1,
            border_color=FAERY_DIVIDER,
            fg_color=FAERY_LAVENDER_BG,
            font=self.font_body,
        )
        self.history_search_entry.grid(row=0, column=0, sticky="ew")

        # Apple-style Clear Button (✕) positioned on the right
        self.history_search_clear_btn = ctk.CTkButton(
            search_box_frame,
            text="✕",
            width=26,
            height=26,
            corner_radius=13,
            fg_color="transparent",
            hover_color=FAERY_SEGMENT_HOVER,
            text_color=FAERY_TEXT_MUTED,
            border_width=0,
            font=self.font_small,
            command=self._on_clear_search_clicked,
            cursor="hand2",
        )
        # Event bindings for real-time keystrokes, return, paste, and escape
        self.history_search_entry.bind("<KeyRelease>", self._on_history_search_changed)
        self.history_search_entry.bind("<Return>", self._on_history_search_enter)
        self.history_search_entry.bind("<KP_Enter>", self._on_history_search_enter)
        self.history_search_entry.bind("<Escape>", lambda e: self._on_clear_search_clicked())
        self.history_search_entry.bind("<<Paste>>", lambda e: self.after(20, self._on_history_search_changed))

        # Subheader with count & borderless refresh pill
        subhead = ctk.CTkFrame(left_panel, fg_color="transparent")
        subhead.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 6))
        subhead.grid_columnconfigure(0, weight=1)

        self.history_count_label = ctk.CTkLabel(
            subhead,
            text="0 Transcripts",
            font=self.font_section_caps,
            text_color=FAERY_TEXT_MUTED,
        )
        self.history_count_label.grid(row=0, column=0, sticky="w")

        self.history_refresh_btn = ctk.CTkButton(
            subhead,
            text="↻ Refresh",
            width=74,
            height=24,
            corner_radius=12,
            fg_color=FAERY_SECONDARY_BTN,
            hover_color=FAERY_SECONDARY_HOVER,
            text_color=FAERY_SECONDARY_TEXT,
            border_width=0,
            font=self.font_small,
            command=lambda: self._refresh_history_list(filter_text=None, resync=True),
        )
        self.history_refresh_btn.grid(row=0, column=1, sticky="e")

        # Scrollable list for records
        self.history_list_frame = ctk.CTkScrollableFrame(
            left_panel,
            corner_radius=12,
            fg_color=FAERY_LAVENDER_BG,
        )
        self.history_list_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.history_list_frame.grid_columnconfigure(0, weight=1)

        # Right Column: Document Reader, Inspector & CRUD Actions
        right_panel = ctk.CTkFrame(
            tab,
            corner_radius=16,
            fg_color=FAERY_CREAM_CARD,
            border_width=1,
            border_color=FAERY_CARD_BORDER,
        )
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(3, weight=1)

        # Details Header
        self.history_detail_header = ctk.CTkFrame(right_panel, fg_color="transparent")
        self.history_detail_header.grid(row=0, column=0, sticky="ew", padx=20, pady=(14, 6))
        self.history_detail_header.grid_columnconfigure(0, weight=1)

        self.history_title_label = ctk.CTkLabel(
            self.history_detail_header,
            text="✨ Select a transcript from your library",
            font=self.font_serif_title,
            text_color=FAERY_TEXT_PRIMARY,
            anchor="w",
        )
        self.history_title_label.grid(row=0, column=0, sticky="w")

        self.history_meta_label = ctk.CTkLabel(
            self.history_detail_header,
            text="Choose any archived Faery Good transcript to view, edit, rename, or export.",
            font=self.font_small,
            text_color=FAERY_TEXT_MUTED,
            anchor="w",
        )
        self.history_meta_label.grid(row=1, column=0, sticky="w", pady=(2, 0))

        # Action Toolbar (CRUD Operations)
        crud_toolbar = ctk.CTkFrame(right_panel, fg_color="transparent")
        crud_toolbar.grid(row=1, column=0, sticky="ew", padx=20, pady=(4, 10))
        crud_toolbar.grid_columnconfigure(1, weight=1)

        left_crud = ctk.CTkFrame(crud_toolbar, fg_color="transparent")
        left_crud.grid(row=0, column=0, sticky="w")

        self.history_view_selector = FaerySegmentedButton(
            left_crud,
            values=["📄 Clean Paragraphs", "⏱️ Timecoded", "📝 Markdown"],
            command=self._on_history_view_mode_changed,
            height=30,
            corner_radius=15,
            font=self.font_small,
            fg_color=FAERY_SEGMENT_TRACK,
            selected_color=FAERY_PURPLE,
            selected_hover_color=FAERY_PURPLE_HOVER,
            unselected_color=FAERY_SEGMENT_TRACK,
            unselected_hover_color=FAERY_SEGMENT_HOVER,
            selected_text_color=("#FCF4ED", "#FCF4ED"),
            unselected_text_color=FAERY_SECONDARY_TEXT,
        )
        self.history_view_selector.set("📄 Clean Paragraphs")
        self.history_view_selector.pack(side="left", padx=(0, 10))

        right_crud = ctk.CTkFrame(crud_toolbar, fg_color="transparent")
        right_crud.grid(row=0, column=1, sticky="e")

        self.h_rename_btn = ctk.CTkButton(
            right_crud,
            text="✏️ Rename",
            width=84,
            height=30,
            corner_radius=15,
            fg_color=FAERY_SECONDARY_BTN,
            hover_color=FAERY_SECONDARY_HOVER,
            text_color=FAERY_SECONDARY_TEXT,
            text_color_disabled=FAERY_SECONDARY_DISABLED_TEXT,
            border_width=0,
            font=self.font_body_bold,
            command=self._on_history_rename_clicked,
            state="disabled",
        )
        self.h_rename_btn.pack(side="left", padx=(0, 6))

        self.h_save_btn = ctk.CTkButton(
            right_crud,
            text="💾 Save Edits",
            width=94,
            height=30,
            corner_radius=15,
            fg_color=FAERY_SECONDARY_BTN,
            hover_color=FAERY_SECONDARY_HOVER,
            text_color=FAERY_SECONDARY_TEXT,
            text_color_disabled=FAERY_SECONDARY_DISABLED_TEXT,
            border_width=0,
            font=self.font_body_bold,
            command=self._on_history_save_edits_clicked,
            state="disabled",
        )
        self.h_save_btn.pack(side="left", padx=(0, 6))

        self.h_copy_btn = ctk.CTkButton(
            right_crud,
            text="📋 Copy",
            width=72,
            height=30,
            corner_radius=15,
            fg_color=FAERY_SECONDARY_BTN,
            hover_color=FAERY_SECONDARY_HOVER,
            text_color=FAERY_SECONDARY_TEXT,
            text_color_disabled=FAERY_SECONDARY_DISABLED_TEXT,
            border_width=0,
            font=self.font_body_bold,
            command=self._on_history_copy_clicked,
            state="disabled",
        )
        self.h_copy_btn.pack(side="left", padx=(0, 6))

        self.h_open_file_btn = ctk.CTkButton(
            right_crud,
            text="↗️ Open",
            width=76,
            height=30,
            corner_radius=15,
            fg_color=FAERY_SECONDARY_BTN,
            hover_color=FAERY_SECONDARY_HOVER,
            text_color=FAERY_SECONDARY_TEXT,
            text_color_disabled=FAERY_SECONDARY_DISABLED_TEXT,
            border_width=0,
            font=self.font_body_bold,
            command=self._on_history_open_file_clicked,
            state="disabled",
        )
        self.h_open_file_btn.pack(side="left", padx=(0, 6))

        self.h_delete_btn = ctk.CTkButton(
            right_crud,
            text="🗑️ Delete",
            width=78,
            height=30,
            corner_radius=15,
            fg_color=FAERY_BERRY_RED,
            hover_color=FAERY_BERRY_HOVER,
            text_color=FAERY_BERRY_TEXT,
            text_color_disabled=FAERY_SECONDARY_DISABLED_TEXT,
            border_width=0,
            font=self.font_body_bold,
            command=self._on_history_delete_clicked,
            state="disabled",
        )
        self.h_delete_btn.pack(side="left")

        h_divider = ctk.CTkFrame(right_panel, height=1, fg_color=FAERY_DIVIDER)
        h_divider.grid(row=2, column=0, sticky="ew", padx=20)

        # Preview & Edit Textbox (Borderless Apple Document Canvas)
        self.history_textbox = ctk.CTkTextbox(
            right_panel,
            wrap="word",
            font=self.font_editor,
            corner_radius=12,
            border_width=0,
            fg_color=FAERY_CREAM_CARD,
            text_color=FAERY_TEXT_PRIMARY,
        )
        self.history_textbox.grid(row=3, column=0, sticky="nsew", padx=16, pady=(6, 14))

    # -----------------------------------------------------------------------
    # GUI Event Handlers (Transcribe Tab)
    # -----------------------------------------------------------------------
    def _on_theme_changed(self, choice: str) -> None:
        ctk.set_appearance_mode(choice)
        self.config.appearance_mode = choice

    def _on_model_changed(self, choice: str) -> None:
        self.config.model_selection = choice

    def _on_cookie_browser_changed(self, choice: str) -> None:
        self.config.cookie_browser = choice

    def _update_output_dir_label(self) -> None:
        self.out_path_entry.configure(state="normal")
        self.out_path_entry.delete(0, "end")
        self.out_path_entry.insert(0, str(self.config.output_directory))
        self.out_path_entry.configure(state="readonly")

    def _on_change_folder_clicked(self) -> None:
        chosen = filedialog.askdirectory(
            initialdir=str(self.config.output_directory),
            title="Select Output Directory for Transcripts",
        )
        if chosen:
            chosen_path = Path(chosen)
            try:
                chosen_path.mkdir(parents=True, exist_ok=True)
                self.config.output_directory = chosen_path
                self._update_output_dir_label()
                self._refresh_history_list()
            except Exception as err:
                messagebox.showerror(
                    "Cannot Use Folder",
                    f"The selected folder cannot be written to:\n{err}",
                )

    def _activate_online_url(self, url: str) -> None:
        """Sets an online social media URL as the active transcription source."""
        clean_url = url.strip()
        self.selected_url = clean_url
        self.selected_file = None
        self.selected_metadata = None

        platform = OnlineMediaFetcher.detect_platform(clean_url)
        short_url = clean_url if len(clean_url) <= 46 else clean_url[:43] + "..."
        self.file_name_label.configure(text=f"🌐 {platform} Clip Ready")
        self.file_meta_label.configure(
            text=f"🔗 {short_url}   |   🧹 Temp audio auto-purged"
        )
        mod_key = "⌘Return" if sys.platform == "darwin" else "Ctrl+Enter"
        self.status_label.configure(
            text=f"✨ Ready to fetch & transcribe {platform} clip. Click 'Generate Transcript' or press {mod_key}."
        )

    def _on_url_entry_changed(self, event=None) -> None:
        """Detects when a valid URL is typed or pasted into the URL box."""
        raw = self.url_entry.get().strip()
        if OnlineMediaFetcher.is_valid_url(raw):
            self._activate_online_url(raw)
        elif not raw and self.selected_url is not None:
            self.selected_url = None
            if not self.selected_file:
                self.file_name_label.configure(text="No clip or link selected yet")
                self.file_meta_label.configure(
                    text="Select a local file or paste an Instagram, YouTube, TikTok, or Facebook link below"
                )
                self.status_label.configure(text="✨ Ready — Select a video/audio clip or paste a link to begin.")

    def _on_paste_url_clicked(self) -> None:
        """Grabs a URL from the system clipboard (or existing entry) and prepares it for transcription."""
        if self.is_transcribing:
            return

        clip_text = ""
        try:
            clip_text = (self.clipboard_get() or "").strip()
        except Exception:
            clip_text = ""

        if OnlineMediaFetcher.is_valid_url(clip_text):
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, clip_text)
            self._activate_online_url(clip_text)
            return

        entry_text = self.url_entry.get().strip()
        if OnlineMediaFetcher.is_valid_url(entry_text):
            self._activate_online_url(entry_text)
            return

        messagebox.showinfo(
            "Paste a Video Link",
            "Copy any video or reel link from Instagram, YouTube, TikTok, or Facebook "
            "(starting with https://), then click '📋 Paste Link' or paste it directly into the link box!",
        )
        self.url_entry.focus_set()

    def _on_select_file_clicked(self) -> None:
        """Opens native file picker filtered to supported video & audio containers."""
        ext_patterns = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_MEDIA_EXTENSIONS))
        chosen = filedialog.askopenfilename(
            initialdir=str(self.config.get_initial_media_dir()),
            title="Select Video or Audio File",
            filetypes=[
                ("All Supported Media", ext_patterns),
                ("Video Files (*.mp4, *.mov, *.mkv)", "*.mp4 *.mov *.mkv *.MP4 *.MOV *.MKV"),
                ("Audio Files (*.m4a, *.mp3, *.wav)", "*.m4a *.mp3 *.wav *.M4A *.MP3 *.WAV"),
                ("All Files", "*.*"),
            ],
        )
        if not chosen:
            return

        file_path = Path(chosen)
        self.status_label.configure(text=f"Probing {file_path.name}...")
        self.update_idletasks()

        try:
            metadata = MediaProcessor.probe_file(file_path)
            self.selected_file = file_path
            self.selected_metadata = metadata
            self.selected_url = None
            self.url_entry.delete(0, "end")

            # Remember chosen directory for next time
            self.config.data["last_media_directory"] = str(file_path.parent)
            self.config.save()

            self.file_name_label.configure(text=f"🎬 {file_path.name}")
            self.file_meta_label.configure(
                text=f"⏱ Duration: {metadata.formatted_duration}   |   "
                     f"📦 Size: {metadata.formatted_size}   |   "
                     f"🎵 Audio: Valid track detected"
            )
            mod_key = "⌘Return" if sys.platform == "darwin" else "Ctrl+Enter"
            self.status_label.configure(
                text=f"Ready to transcribe '{file_path.name}' ({metadata.formatted_duration}). Click 'Generate Transcript' or press {mod_key}."
            )
        except ValueError as val_err:
            messagebox.showerror("Unsupported / Invalid File", str(val_err))
            self.status_label.configure(text="Selected file could not be read.")
        except Exception as err:
            messagebox.showerror("File Error", f"Failed to inspect file:\n{err}")
            self.status_label.configure(text="Inspection failed.")

    def _prompt_overwrite_dialog(self, base_stem: str, existing_file: Path) -> Optional[bool]:
        """Displays a Yes/No/Cancel dialog asking whether to overwrite or create a numbered copy."""
        return messagebox.askyesnocancel(
            title="Transcript Already Exists",
            message=(
                f"A transcript for '{base_stem}' already exists in your output folder:\n\n"
                f"• {existing_file.name}\n\n"
                "Would you like to overwrite the existing transcript files?\n\n"
                "• Click 'Yes' to OVERWRITE the existing files.\n"
                f"• Click 'No' to create a new numbered version (e.g. '{base_stem}_1').\n"
                "• Click 'Cancel' to abort."
            ),
        )

    def _threadsafe_prompt_overwrite(self, base_stem: str, existing_file: Path) -> Optional[bool]:
        """Synchronously dispatches an overwrite dialog onto the main Tkinter thread from a worker thread."""
        done_evt = threading.Event()
        result_box: List[Optional[bool]] = [False]

        def _ask_on_main():
            try:
                result_box[0] = self._prompt_overwrite_dialog(base_stem, existing_file)
            finally:
                done_evt.set()

        self.after(0, _ask_on_main)
        done_evt.wait()
        return result_box[0]

    def _on_generate_clicked(self) -> None:
        """Validates prerequisites, prompts for overwrite if file exists, and launches worker."""
        if self.is_transcribing:
            return

        # Check if a URL was typed/pasted into the entry box
        typed_url = self.url_entry.get().strip()
        if typed_url:
            if OnlineMediaFetcher.is_valid_url(typed_url):
                self._activate_online_url(typed_url)
            elif not self.selected_file:
                messagebox.showwarning(
                    "Invalid Link",
                    "The link entered does not look like a valid web address.\n\n"
                    "Please paste a complete link starting with https:// (from Instagram, YouTube, TikTok, or Facebook).",
                )
                return

        has_local = bool(self.selected_file and self.selected_metadata)
        has_online = bool(self.selected_url)

        if not has_local and not has_online:
            messagebox.showwarning(
                "No Clip or Link Selected",
                "Please select a local video/audio file or paste an Instagram, YouTube, TikTok, or Facebook link first.",
            )
            return

        output_dir = self.config.output_directory
        overwrite: Optional[bool] = None

        if has_local and self.selected_file:
            base_stem = self.selected_file.stem
            existing_p = output_dir / f"{base_stem}_paragraphs.txt"
            existing_m = output_dir / f"{base_stem}_transcript.md"
            if existing_p.exists() or existing_m.exists():
                ans = self._prompt_overwrite_dialog(base_stem, existing_p if existing_p.exists() else existing_m)
                if ans is None:
                    return
                overwrite = ans
            else:
                overwrite = False
        elif has_online and self.selected_url:
            # Check if this exact URL was already transcribed in History
            for rec in self.history.records:
                if rec.source_filename == self.selected_url:
                    existing_p = output_dir / f"{rec.title}_paragraphs.txt"
                    existing_m = output_dir / f"{rec.title}_transcript.md"
                    if existing_p.exists() or existing_m.exists():
                        ans = self._prompt_overwrite_dialog(
                            rec.title, existing_p if existing_p.exists() else existing_m
                        )
                        if ans is None:
                            return
                        overwrite = ans
                    break

        model_display = self.model_dropdown.get()
        model_id = MODEL_DISPLAY_NAMES.get(model_display, "small.en")
        cookie_browser_label = self.cookie_dropdown.get()

        # Reset states
        self.cancel_event.clear()
        self.is_transcribing = True
        self.current_segments.clear()
        self.textbox.delete("1.0", "end")
        self._update_stats()

        # Update controls
        self.select_file_btn.configure(state="disabled")
        self.url_entry.configure(state="disabled")
        self.paste_url_btn.configure(state="disabled")
        self.generate_btn.configure(
            state="disabled",
            text="⏳ Transcribing…",
            fg_color=("#8B62B8", "#442168"),
            text_color_disabled=("#F0E6FA", "#DDD0F0"),
        )
        self.model_dropdown.configure(state="disabled")
        self.cookie_dropdown.configure(state="disabled")
        self.change_folder_btn.configure(state="disabled")
        self.cancel_btn.configure(
            state="normal",
            fg_color=FAERY_BERRY_RED,
            hover_color=FAERY_BERRY_HOVER,
            text_color=FAERY_BERRY_TEXT,
        )

        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start()

        # Spawn worker thread (macOS beachball prevention guarantee)
        if has_online and self.selected_url:
            platform = OnlineMediaFetcher.detect_platform(self.selected_url)
            self.status_label.configure(text=f"🌐 Connecting to {platform} to fetch temporary audio...")
            self.worker_thread = threading.Thread(
                target=self._run_online_transcription_worker,
                args=(self.selected_url, model_id, output_dir, cookie_browser_label, overwrite),
                daemon=True,
            )
        else:
            self.status_label.configure(text="Starting transcription pipeline...")
            self.worker_thread = threading.Thread(
                target=self._run_transcription_worker,
                args=(self.selected_file, self.selected_metadata, model_id, output_dir, bool(overwrite)),
                daemon=True,
            )
        self.worker_thread.start()

    def _run_transcription_worker(
        self,
        media_file: Path,
        media_meta: MediaMetadata,
        model_id: str,
        output_dir: Path,
        overwrite: bool,
    ) -> None:
        """Background thread executing local file extraction and inference."""
        start_time = time.time()
        try:
            clean_txt, timecoded_txt, md_path, segments = self.engine.run_transcription(
                media_file=media_file,
                media_meta=media_meta,
                model_name=model_id,
                output_dir=output_dir,
                cancel_event=self.cancel_event,
                status_cb=self._async_update_status,
                progress_cb=self._async_update_progress,
                segment_cb=self._async_append_segment,
                overwrite=overwrite,
            )
            elapsed_sec = int(time.time() - start_time)
            minutes = elapsed_sec // 60
            secs = elapsed_sec % 60
            elapsed_str = f"{minutes}m {secs}s" if minutes > 0 else f"{secs}s"

            self.after(
                0,
                self._on_transcription_success,
                clean_txt,
                timecoded_txt,
                md_path,
                media_meta.formatted_duration,
                elapsed_str,
                media_file.name,
            )
        except InterruptedError:
            self.after(0, self._on_transcription_cancelled)
        except Exception as err:
            self.after(0, self._on_transcription_failed, err)

    def _run_online_transcription_worker(
        self,
        url: str,
        model_id: str,
        output_dir: Path,
        cookie_browser_label: str,
        overwrite: Optional[bool],
    ) -> None:
        """Background thread executing temporary online audio download, WAV extraction, and inference."""
        start_time = time.time()
        try:
            clean_txt, timecoded_txt, md_path, segments, clip_title, duration_str = (
                self.engine.run_online_transcription(
                    url=url,
                    model_name=model_id,
                    output_dir=output_dir,
                    cancel_event=self.cancel_event,
                    status_cb=self._async_update_status,
                    progress_cb=self._async_update_progress,
                    segment_cb=self._async_append_segment,
                    cookie_browser_label=cookie_browser_label,
                    overwrite=overwrite,
                    overwrite_prompt_cb=self._threadsafe_prompt_overwrite,
                )
            )
            elapsed_sec = int(time.time() - start_time)
            minutes = elapsed_sec // 60
            secs = elapsed_sec % 60
            elapsed_str = f"{minutes}m {secs}s" if minutes > 0 else f"{secs}s"

            self.after(
                0,
                self._on_transcription_success,
                clean_txt,
                timecoded_txt,
                md_path,
                duration_str,
                elapsed_str,
                url,
                clip_title,
            )
        except InterruptedError:
            self.after(0, self._on_transcription_cancelled)
        except Exception as err:
            self.after(0, self._on_transcription_failed, err)

    def _async_update_status(self, text: str) -> None:
        """Thread-safe UI status update."""
        self.after(0, lambda: self.status_label.configure(text=text))

    def _async_update_progress(self, progress_float: float) -> None:
        """Switches progress bar to determinate and advances progress."""
        def update():
            try:
                self.progress_bar.stop()
                self.progress_bar.configure(mode="determinate")
                self.progress_bar.set(progress_float)
            except Exception:
                pass
        self.after(0, update)

    def _async_append_segment(self, segment: TranscriptSegment) -> None:
        """
        Streams transcribed text live into the textbox as segments yield.
        Re-renders active view so clean paragraphs with pauses are displayed immediately in real-time.
        """
        def update():
            self.current_segments.append(segment)
            self._render_current_view()
            self.textbox.see("end")
        self.after(0, update)

    def _on_transcription_success(
        self,
        clean_txt_path: str,
        timecoded_txt_path: str,
        md_path: str,
        duration_str: str,
        elapsed_str: str,
        source_identifier: str = "",
        online_clip_title: Optional[str] = None,
    ) -> None:
        """Called on main thread when transcription completes successfully."""
        self.last_saved_clean_path = clean_txt_path
        self.last_saved_timecoded_path = timecoded_txt_path
        self.last_saved_md_path = md_path
        self._reset_controls()

        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(1.0)

        if online_clip_title:
            platform = OnlineMediaFetcher.detect_platform(source_identifier)
            self.file_name_label.configure(text=f"🌐 {online_clip_title}")
            self.file_meta_label.configure(
                text=f"⏱ Duration: {duration_str}   |   🌍 Source: {platform}   |   🧹 Temp audio purged"
            )

        # Re-render active view
        self._render_current_view()

        filename_clean = Path(clean_txt_path).name
        self.status_label.configure(
            text=f"Done! Transcribed {duration_str} in {elapsed_str}. Saved to {filename_clean}"
        )
        self._update_stats()

        # Update History Library
        base_title = Path(clean_txt_path).stem.replace("_paragraphs", "")
        word_count = len(self.textbox.get("1.0", "end-1c").split())
        eff_source = (
            source_identifier
            if source_identifier
            else (self.selected_file.name if self.selected_file else f"{base_title}.mp4")
        )
        rec = HistoryRecord(
            id=f"{base_title}_{int(time.time())}",
            title=base_title,
            source_filename=eff_source,
            duration_str=duration_str,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            model=self.model_dropdown.get(),
            paragraphs_file=clean_txt_path,
            timecoded_file=timecoded_txt_path,
            markdown_file=md_path,
            word_count=word_count,
        )
        self.history.add_or_update(rec)
        self._refresh_history_list()

        # Play completion chime for creator feedback
        play_completion_sound()

    def _on_transcription_cancelled(self) -> None:
        self._reset_controls()
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(0.0)
        self.status_label.configure(text="Transcription was cancelled. Scratch files purged.")

    def _on_transcription_failed(self, error: Exception) -> None:
        self._reset_controls()
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(0.0)
        self.status_label.configure(text="Error occurred during transcription.")

        err_msg = str(error)
        lower_msg = err_msg.lower()
        if "disk space" in lower_msg:
            messagebox.showerror("Low Disk Space", err_msg)
        elif "could not download audio from" in lower_msg or "requires you to be logged in" in lower_msg:
            messagebox.showerror("Online Link Download Error", err_msg)
        elif "hugging face" in lower_msg or ("download" in lower_msg and "model" in lower_msg):
            messagebox.showerror(
                "Model Download Error",
                "Failed to download Whisper model from Hugging Face.\n\n"
                "Please verify your internet connection. Once downloaded, the model "
                "runs completely offline without an internet connection.\n\n"
                f"Details: {err_msg}",
            )
        else:
            messagebox.showerror(
                "Transcription Error",
                f"An error occurred while processing the clip:\n\n{err_msg}",
            )

    def _reset_controls(self) -> None:
        self.is_transcribing = False
        self.select_file_btn.configure(state="normal")
        self.url_entry.configure(state="normal")
        self.paste_url_btn.configure(state="normal")
        self.generate_btn.configure(
            state="normal",
            text="✨ Generate Transcript",
            fg_color=FAERY_PURPLE,
            text_color=("#FCF4ED", "#FCF4ED"),
        )
        self.model_dropdown.configure(state="normal")
        self.cookie_dropdown.configure(state="normal")
        self.change_folder_btn.configure(state="normal")
        self.cancel_btn.configure(
            state="disabled",
            fg_color=FAERY_SEGMENT_TRACK,
            hover_color=FAERY_SEGMENT_HOVER,
            text_color=FAERY_TEXT_MUTED,
            text_color_disabled=FAERY_SECONDARY_DISABLED_TEXT,
        )

    def _on_cancel_clicked(self) -> None:
        if self.is_transcribing:
            self.cancel_event.set()
            self.status_label.configure(text="Cancelling and purging scratch files...")
            self.cancel_btn.configure(state="disabled")

    def _on_view_mode_changed(self, choice: str) -> None:
        self._render_current_view()

    def _render_current_view(self) -> None:
        """Renders the segments in the selected format into the editable text area."""
        if not self.current_segments:
            return

        choice = self.view_selector.get()
        if choice == "⏱️ Timecoded (YouTube)":
            text_to_show = TranscriptFormatter.to_timecoded(self.current_segments)
        elif choice == "📝 Raw Text":
            text_to_show = TranscriptFormatter.to_raw(self.current_segments)
        else:  # "📄 Clean Paragraphs"
            text_to_show = TranscriptFormatter.to_paragraphs(self.current_segments)

        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", text_to_show)
        self._update_stats()

    def _on_copy_clicked(self) -> None:
        content = self.textbox.get("1.0", "end-1c").strip()
        if not content:
            return

        self.clipboard_clear()
        self.clipboard_append(content)
        self.copy_btn.configure(text="✓ Copied!", fg_color=FAERY_SAGE_GREEN, text_color="#FCF4ED")
        self.after(
            2500,
            lambda: self.copy_btn.configure(
                text="📋 Copy to Clipboard",
                fg_color=FAERY_SECONDARY_BTN,
                text_color=FAERY_SECONDARY_TEXT,
            ),
        )

    def _on_save_txt_clicked(self) -> None:
        content = self.textbox.get("1.0", "end-1c").strip()
        if not content:
            messagebox.showinfo("Empty Transcript", "There is no text to save.")
            return

        mode = self.view_selector.get()
        suffix = "_timecoded.txt" if "Timecoded" in mode else ("_raw.txt" if "Raw" in mode else "_paragraphs.txt")
        initial_name = f"{self.selected_file.stem}{suffix}" if self.selected_file else f"transcript{suffix}"

        dest = filedialog.asksaveasfilename(
            initialdir=str(self.config.output_directory),
            initialfile=initial_name,
            defaultextension=".txt",
            filetypes=[("Text File", "*.txt"), ("All Files", "*.*")],
        )
        if dest:
            try:
                with open(dest, "w", encoding="utf-8") as f:
                    f.write(content + "\n")
                self.status_label.configure(text=f"Saved text transcript to: {Path(dest).name}")
            except Exception as err:
                messagebox.showerror("Save Error", f"Could not save file:\n{err}")

    def _on_save_md_clicked(self) -> None:
        content = self.textbox.get("1.0", "end-1c").strip()
        if not content:
            messagebox.showinfo("Empty Transcript", "There is no text to save.")
            return

        initial_name = f"{self.selected_file.stem}_transcript.md" if self.selected_file else "transcript.md"
        dest = filedialog.asksaveasfilename(
            initialdir=str(self.config.output_directory),
            initialfile=initial_name,
            defaultextension=".md",
            filetypes=[("Markdown File", "*.md"), ("All Files", "*.*")],
        )
        if dest:
            try:
                model_name = self.model_dropdown.get()
                paragraphs_content = (
                    content
                    if self.view_selector.get() == "📄 Clean Paragraphs"
                    else TranscriptFormatter.to_paragraphs(self.current_segments)
                )
                md_content = self.engine._build_markdown(
                    meta=self.selected_metadata
                    if self.selected_metadata
                    else MediaMetadata(
                        path=Path(initial_name),
                        file_size_bytes=len(content.encode("utf-8")),
                        duration_seconds=0.0,
                        has_audio=True,
                        format_name="text",
                    ),
                    model_name=model_name,
                    paragraphs_text=paragraphs_content,
                    segments=self.current_segments,
                )
                with open(dest, "w", encoding="utf-8") as f:
                    f.write(md_content + "\n")
                self.status_label.configure(text=f"Saved Markdown transcript to: {Path(dest).name}")
            except Exception as err:
                messagebox.showerror("Save Error", f"Could not save Markdown file:\n{err}")

    def _on_open_folder_clicked(self) -> None:
        target = self.config.output_directory
        try:
            open_system_folder(target)
        except Exception as err:
            messagebox.showerror("Open Folder Error", f"Could not open directory:\n{err}")

    def _update_stats(self, event=None) -> None:
        content = self.textbox.get("1.0", "end-1c").strip()
        if not content:
            self.stats_badge.configure(text="0 words  |  0 characters")
            return

        words = len(content.split())
        chars = len(content)
        self.stats_badge.configure(text=f"{words:,} words  |  {chars:,} characters")

    # -----------------------------------------------------------------------
    # GUI Event Handlers (History Tab & CRUD Operations)
    # -----------------------------------------------------------------------
    def _on_history_search_changed(self, event=None) -> None:
        """Handles real-time search typing and toggles the clear pill button."""
        query = self.history_search_entry.get().strip()
        if query:
            self.history_search_clear_btn.grid(row=0, column=1, padx=(6, 0))
        else:
            self.history_search_clear_btn.grid_forget()
        self._refresh_history_list(filter_text=query, resync=False)

    def _on_clear_search_clicked(self) -> None:
        """Clears the history search box and restores the complete transcript list."""
        self.history_search_entry.delete(0, "end")
        self.history_search_clear_btn.grid_forget()
        self._refresh_history_list(filter_text="", resync=False)
        self.history_search_entry.focus_set()

    def _on_history_search_enter(self, event=None) -> None:
        """Selects the first matching transcript when the user presses Enter in search."""
        query = self.history_search_entry.get().strip()
        self._on_history_search_changed()
        records = self.history.records
        for r in records:
            matched, _ = r.matches_query(query)
            if matched:
                self._select_history_item(r.id)
                break

    def _refresh_history_list(self, filter_text: Optional[str] = None, resync: bool = False) -> None:
        """Populates the left-hand scrollable library list using instant smart search."""
        if resync:
            records = self.history.sync_with_directory(self.config.output_directory)
        else:
            records = self.history.records

        # If filter_text is not explicitly provided, read the current text from the search box
        if filter_text is None:
            filter_text = self.history_search_entry.get().strip() if hasattr(self, "history_search_entry") else ""

        # Clear existing card widgets
        for widget in self.history_list_frame.winfo_children():
            widget.destroy()

        query = filter_text.strip()
        matching_results: List[Tuple[HistoryRecord, Optional[str]]] = []
        for r in records:
            matched, snippet = r.matches_query(query)
            if matched:
                matching_results.append((r, snippet))

        total_count = len(records)
        match_count = len(matching_results)
        if query:
            self.history_count_label.configure(text=f"{match_count} of {total_count} Transcripts")
        else:
            self.history_count_label.configure(text=f"{total_count} Transcripts")

        if not matching_results:
            empty_lbl = ctk.CTkLabel(
                self.history_list_frame,
                text="No saved transcripts found." if not query else f"No transcripts matching '{query}'.",
                font=self.font_body,
                text_color=FAERY_TEXT_MUTED,
            )
            empty_lbl.pack(pady=30)
            return

        for record, snippet in matching_results:
            is_selected = (record.id == self.selected_history_id)
            card = ctk.CTkFrame(
                self.history_list_frame,
                corner_radius=12,
                fg_color=FAERY_ROSE_CARD if is_selected else FAERY_CREAM_CARD,
                border_width=2 if is_selected else 1,
                border_color=FAERY_ACTIVE_BORDER if is_selected else FAERY_CARD_BORDER,
                cursor="hand2",
            )
            card.pack(fill="x", pady=4, padx=2)

            # Title
            title_lbl = ctk.CTkLabel(
                card,
                text=f"🦋 {record.title}" if is_selected else record.title,
                font=self.font_serif_card,
                text_color=FAERY_TEXT_PRIMARY,
                anchor="w",
            )
            title_lbl.pack(fill="x", padx=12, pady=(8, 2))

            # If matched inside spoken transcript content, show the matching speech snippet!
            snippet_lbl = None
            if snippet:
                snippet_lbl = ctk.CTkLabel(
                    card,
                    text=f"💬 {snippet}",
                    font=self.font_small,
                    text_color=FAERY_PURPLE[0],
                    anchor="w",
                    justify="left",
                )
                snippet_lbl.pack(fill="x", padx=12, pady=(0, 2))

            # Subtitle (Date & Duration)
            meta_str = f"📅 {record.created_at}   •   ⏱ {record.duration_str}"
            meta_lbl = ctk.CTkLabel(
                card,
                text=meta_str,
                font=self.font_small,
                text_color=FAERY_TEXT_MUTED,
                anchor="w",
            )
            meta_lbl.pack(fill="x", padx=12, pady=(0, 2))

            # Word count badge
            w_str = f"✨ {record.word_count} words" if record.word_count > 0 else "✨ Transcript ready"
            w_lbl = ctk.CTkLabel(
                card,
                text=w_str,
                font=self.font_small,
                text_color=FAERY_TEXT_MUTED,
                anchor="w",
            )
            w_lbl.pack(fill="x", padx=12, pady=(0, 8))

            # Bind clicks
            elements = [card, title_lbl, meta_lbl, w_lbl]
            if snippet_lbl is not None:
                elements.append(snippet_lbl)
            for elem in elements:
                elem.bind("<Button-1>", lambda e, r_id=record.id: self._select_history_item(r_id))

    def _select_history_item(self, record_id: str) -> None:
        """Selects a transcript from the list and loads its details and preview."""
        self.selected_history_id = record_id
        record = next((r for r in self.history.records if r.id == record_id), None)
        if not record:
            return

        # Re-render list highlighting preserving active search
        self._refresh_history_list(filter_text=None, resync=False)

        # Update details header
        self.history_title_label.configure(text=record.title)
        self.history_meta_label.configure(
            text=f"Created: {record.created_at}   |   Duration: {record.duration_str}   |   Words: {record.word_count}"
        )

        # Enable CRUD buttons
        self.h_rename_btn.configure(state="normal")
        self.h_save_btn.configure(state="normal")
        self.h_copy_btn.configure(state="normal")
        self.h_open_file_btn.configure(state="normal")
        self.h_delete_btn.configure(state="normal")

        # Load text into preview
        self._load_history_preview(record)

    def _on_history_view_mode_changed(self, choice: str) -> None:
        if self.selected_history_id:
            record = next((r for r in self.history.records if r.id == self.selected_history_id), None)
            if record:
                self._load_history_preview(record)

    def _load_history_preview(self, record: HistoryRecord) -> None:
        choice = self.history_view_selector.get()
        target_path = None
        if choice == "⏱️ Timecoded":
            target_path = record.timecoded_file or record.paragraphs_file
        elif choice == "📝 Markdown":
            target_path = record.markdown_file or record.paragraphs_file
        else:
            target_path = record.paragraphs_file or record.markdown_file

        self.history_textbox.delete("1.0", "end")
        if target_path and os.path.exists(target_path):
            try:
                with open(target_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                self.history_textbox.insert("1.0", content)
            except Exception as err:
                self.history_textbox.insert("1.0", f"Error loading file content: {err}")
        else:
            self.history_textbox.insert("1.0", "(File content not available on disk)")

    def _on_history_rename_clicked(self) -> None:
        if not self.selected_history_id:
            return

        record = next((r for r in self.history.records if r.id == self.selected_history_id), None)
        if not record:
            return

        dialog = ctk.CTkInputDialog(
            text="Enter new title for this transcript:",
            title="Rename Transcript",
        )
        new_title = dialog.get_input()
        if new_title and new_title.strip():
            try:
                updated = self.history.rename_record(self.selected_history_id, new_title.strip())
                if updated:
                    self.history_title_label.configure(text=updated.title)
                    self._refresh_history_list(filter_text=None, resync=False)
                    self._load_history_preview(updated)
            except Exception as err:
                messagebox.showerror("Rename Error", f"Could not rename files:\n{err}")

    def _on_history_save_edits_clicked(self) -> None:
        """Saves current edits from the history textbox directly to the active file."""
        if not self.selected_history_id:
            return

        record = next((r for r in self.history.records if r.id == self.selected_history_id), None)
        if not record:
            return

        choice = self.history_view_selector.get()
        target_path = None
        if choice == "⏱️ Timecoded":
            target_path = record.timecoded_file
        elif choice == "📝 Markdown":
            target_path = record.markdown_file
        else:
            target_path = record.paragraphs_file

        if not target_path:
            messagebox.showwarning("No File", "No file path is associated with this format.")
            return

        content = self.history_textbox.get("1.0", "end-1c")
        try:
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)
            record.word_count = len(content.split())
            self.history.save()
            self._refresh_history_list(filter_text=None, resync=False)
            self.h_save_btn.configure(text="✓ Saved!", fg_color=FAERY_SAGE_GREEN, text_color="#FCF4ED")
            self.after(
                2000,
                lambda: self.h_save_btn.configure(
                    text="💾 Save Edits",
                    fg_color=FAERY_SECONDARY_BTN,
                    text_color=FAERY_SECONDARY_TEXT,
                ),
            )
        except Exception as err:
            messagebox.showerror("Save Error", f"Could not save changes to file:\n{err}")

    def _on_history_copy_clicked(self) -> None:
        content = self.history_textbox.get("1.0", "end-1c").strip()
        if not content:
            return

        self.clipboard_clear()
        self.clipboard_append(content)
        self.h_copy_btn.configure(text="✓ Copied!", fg_color=FAERY_SAGE_GREEN, text_color="#FCF4ED")
        self.after(
            2000,
            lambda: self.h_copy_btn.configure(
                text="📋 Copy",
                fg_color=FAERY_SECONDARY_BTN,
                text_color=FAERY_SECONDARY_TEXT,
            ),
        )

    def _on_history_open_file_clicked(self) -> None:
        if not self.selected_history_id:
            return

        record = next((r for r in self.history.records if r.id == self.selected_history_id), None)
        if not record:
            return

        choice = self.history_view_selector.get()
        target_path = (
            record.timecoded_file if choice == "⏱️ Timecoded"
            else (record.markdown_file if choice == "📝 Markdown" else record.paragraphs_file)
        )
        if target_path and os.path.exists(target_path):
            open_system_file(Path(target_path))
        else:
            messagebox.showinfo("File Missing", "File does not exist on disk.")

    def _on_history_reveal_folder_clicked(self) -> None:
        open_system_folder(self.config.output_directory)

    def _on_history_delete_clicked(self) -> None:
        if not self.selected_history_id:
            return

        record = next((r for r in self.history.records if r.id == self.selected_history_id), None)
        if not record:
            return

        if messagebox.askyesno(
            "Delete Transcript",
            f"Are you sure you want to permanently delete '{record.title}' and its associated files from disk?",
        ):
            self.history.delete_record(self.selected_history_id)
            self.selected_history_id = None
            self.history_title_label.configure(text="✨ Select a transcript from your library")
            self.history_meta_label.configure(text="Choose any archived transcript to view, edit, rename, or export.")
            self.history_textbox.delete("1.0", "end")

            self.h_rename_btn.configure(state="disabled")
            self.h_save_btn.configure(state="disabled")
            self.h_copy_btn.configure(state="disabled")
            self.h_open_file_btn.configure(state="disabled")
            self.h_delete_btn.configure(state="disabled")

            self._refresh_history_list(filter_text=None, resync=False)

    def _on_window_close(self) -> None:
        """Handles graceful application shutdown, guaranteeing scratch purge."""
        if self.is_transcribing:
            if messagebox.askyesno(
                "Transcription in Progress",
                "A transcription is currently running. Do you want to cancel and exit?",
            ):
                self.cancel_event.set()
                self.destroy()
        else:
            self.destroy()

    # -----------------------------------------------------------------------
    # macOS & System Polish: Menu Bar, Global Shortcuts, and Creator Dialogs
    # -----------------------------------------------------------------------
    def _build_menu_bar(self) -> None:
        """Constructs native system menu bar (mounted to macOS top bar or Windows title bar)."""
        is_mac = sys.platform == "darwin"
        mod_sym = "Cmd" if is_mac else "Ctrl"

        menu_bar = tk.Menu(self)

        # File Menu
        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(
            label="Select Local Media File...",
            accelerator=f"{mod_sym}+O",
            command=self._on_select_file_clicked,
        )
        file_menu.add_command(
            label="Paste Online Video / Reel Link",
            accelerator=f"{mod_sym}+L",
            command=self._on_paste_url_clicked,
        )
        file_menu.add_command(
            label="Open Output Folder",
            accelerator=f"Shift+{mod_sym}+O",
            command=self._on_open_folder_clicked,
        )
        file_menu.add_separator()
        file_menu.add_command(
            label="Save Clean Text (.txt)...",
            accelerator=f"{mod_sym}+S",
            command=self._on_save_txt_clicked,
        )
        file_menu.add_command(
            label="Save Markdown (.md)...",
            command=self._on_save_md_clicked,
        )
        file_menu.add_separator()
        file_menu.add_command(
            label="Exit",
            accelerator=f"{mod_sym}+Q" if is_mac else "Alt+F4",
            command=self._on_window_close,
        )
        menu_bar.add_cascade(label="File", menu=file_menu)

        # Edit Menu
        edit_menu = tk.Menu(menu_bar, tearoff=0)
        edit_menu.add_command(
            label="Copy Active Transcript",
            accelerator=f"{mod_sym}+C",
            command=self._on_copy_clicked,
        )
        edit_menu.add_command(
            label="Select All in Textbox",
            accelerator=f"{mod_sym}+A",
            command=self._select_all_active_text,
        )
        menu_bar.add_cascade(label="Edit", menu=edit_menu)

        # View Menu
        view_menu = tk.Menu(menu_bar, tearoff=0)
        view_menu.add_command(
            label="🎙️ Transcribe Studio",
            accelerator=f"{mod_sym}+1",
            command=lambda: self.tabview.set("🎙️ Transcribe"),
        )
        view_menu.add_command(
            label="📜 History Library",
            accelerator=f"{mod_sym}+2",
            command=lambda: self.tabview.set("📜 History"),
        )
        view_menu.add_separator()
        view_menu.add_command(
            label="Toggle Dark / Light Theme",
            command=self._cycle_theme,
        )
        menu_bar.add_cascade(label="View", menu=view_menu)

        # Help Menu
        help_menu = tk.Menu(menu_bar, tearoff=0)
        help_menu.add_command(
            label="Quick Start Guide for Creators",
            command=self._show_quick_guide,
        )
        help_menu.add_command(
            label="Visit FaeryGood.com 🦋",
            command=lambda: webbrowser.open(FAERY_GOOD_URL),
        )
        help_menu.add_separator()
        help_menu.add_command(
            label=f"About {APP_NAME}",
            command=self._show_about_dialog,
        )
        menu_bar.add_cascade(label="Help", menu=help_menu)

        self.configure(menu=menu_bar)

    def _setup_shortcuts(self) -> None:
        """Binds macOS Command and Windows Control keyboard shortcuts for fluid navigation."""
        def select_all_text(event):
            try:
                event.widget.tag_add("sel", "1.0", "end-1c")
            except Exception:
                pass
            return "break"

        def select_all_entry(event):
            try:
                event.widget.select_range(0, "end")
                event.widget.icursor("end")
            except Exception:
                pass
            return "break"

        is_mac = sys.platform == "darwin"
        mods = ["Command"] if is_mac else ["Control"]

        for mod in mods:
            # Text editing bindings across all text and entry widgets
            self.bind_class("Text", f"<{mod}-Key-a>", select_all_text)
            self.bind_class("Entry", f"<{mod}-Key-a>", select_all_entry)

            # Application actions
            self.bind(f"<{mod}-Key-o>", lambda e: self._on_select_file_clicked())
            self.bind(f"<{mod}-Key-l>", lambda e: self._on_paste_url_clicked())
            self.bind(f"<{mod}-Key-O>", lambda e: self._on_open_folder_clicked())
            self.bind(f"<{mod}-Key-s>", lambda e: self._on_quick_save())
            self.bind(f"<{mod}-Key-Return>", lambda e: self._on_generate_clicked())
            self.bind(f"<{mod}-Key-1>", lambda e: self.tabview.set("🎙️ Transcribe"))
            self.bind(f"<{mod}-Key-2>", lambda e: self.tabview.set("📜 History"))
            self.bind(f"<{mod}-Key-q>", lambda e: self._on_window_close())

    def _on_quick_save(self) -> None:
        """Handles Command+S / Ctrl+S intelligently based on the active tab."""
        active_tab = self.tabview.get()
        if "History" in active_tab:
            if self.h_save_btn.cget("state") == "normal":
                self._on_history_save_edits_clicked()
        else:
            self._on_save_txt_clicked()

    def _select_all_active_text(self) -> None:
        """Focuses the active tab's textbox and selects all text."""
        active_tab = self.tabview.get()
        if "History" in active_tab:
            self.history_textbox.focus_set()
            try:
                self.history_textbox._textbox.tag_add("sel", "1.0", "end-1c")
            except Exception:
                pass
        else:
            self.textbox.focus_set()
            try:
                self.textbox._textbox.tag_add("sel", "1.0", "end-1c")
            except Exception:
                pass

    def _cycle_theme(self) -> None:
        """Cycles between Light -> Dark -> System -> Light."""
        current = self.config.appearance_mode
        cycle_map = {"Light": "Dark", "Dark": "System", "System": "Light"}
        next_mode = cycle_map.get(current, "Light")
        self.theme_menu.set(next_mode)
        self._on_theme_changed(next_mode)

    def _show_quick_guide(self) -> None:
        """Displays an accessible, Faery Good styled walkthrough for Ericka."""
        guide_win = ctk.CTkToplevel(self)
        guide_win.title("Faery Good — Creator Quick Start Guide")
        guide_win.geometry("580x560")
        guide_win.resizable(False, False)
        guide_win.attributes("-topmost", True)
        guide_win.configure(fg_color=FAERY_BG)
        self.brand.apply_window_icon(guide_win)

        content_frame = ctk.CTkFrame(
            guide_win,
            corner_radius=16,
            fg_color=FAERY_CREAM_CARD,
            border_width=1,
            border_color=FAERY_CARD_BORDER,
        )
        content_frame.pack(fill="both", expand=True, padx=16, pady=16)

        header_row = ctk.CTkFrame(content_frame, fg_color="transparent")
        header_row.pack(fill="x", padx=16, pady=(14, 8))

        if self.brand.mascot_dialog is not None:
            m_lbl = ctk.CTkLabel(header_row, text="", image=self.brand.mascot_dialog)
            m_lbl.pack(side="left", padx=(0, 12))

        title_stack = ctk.CTkFrame(header_row, fg_color="transparent")
        title_stack.pack(side="left", fill="x", expand=True)

        title = ctk.CTkLabel(
            title_stack,
            text="✨ Faery Good Creator Guide",
            font=self.font_serif_title,
            text_color=FAERY_TEXT_PRIMARY,
            anchor="w",
        )
        title.pack(anchor="w")

        sub = ctk.CTkLabel(
            title_stack,
            text=f"“{FAERY_GOOD_TAGLINE}” — Effortless Instagram Reels & YouTube Transcripts",
            font=self.font_serif_italic,
            text_color=FAERY_TEXT_MUTED,
            anchor="w",
        )
        sub.pack(anchor="w")

        guide_text = (
            "Welcome to your custom Faery Good Transcriber Studio! Crafted specifically for "
            "Instagram Reels, YouTube videos, TikToks, and Facebook clips.\n\n"
            "1. PICK A LOCAL FILE OR PASTE A SOCIAL LINK\n"
            "   • Local File (⌘O / Ctrl+O): Choose any video (.mp4, .mov) or audio (.m4a, .mp3, .wav) file.\n"
            "   • Online Link (⌘L / Ctrl+L): Paste any link from Instagram, YouTube, TikTok, or Facebook "
            "(or click '📋 Paste Link'). Only the audio stream is fetched into a temporary folder.\n\n"
            "2. GENERATE TRANSCRIPT (⌘Return / Ctrl+Enter)\n"
            "   Click '✨ Generate Transcript'. Watch your words stream in live, and listen for "
            "a gentle chime when your transcript is ready!\n\n"
            "3. CHOOSE YOUR OUTPUT FORMAT\n"
            "   • 📄 Clean Paragraphs: Natural sentences grouped by spoken pauses — ready for "
            "Instagram captions, herbalism notes, newsletters, and blog posts.\n"
            "   • ⏱️ Timecoded: [MM:SS] timestamps ready to paste directly into your "
            "YouTube description for automatic video chapters.\n"
            "   • 📝 Raw Text: Continuous unsegmented text.\n\n"
            "4. 100% PRIVATE & ZERO LEFTOVER AUDIO FILES\n"
            "   All transcription runs locally on your Mac's CPU. Downloaded and converted "
            "audio files are strictly temporary and purged immediately after transcription.\n\n"
            "5. HISTORY LIBRARY (⌘2 / Ctrl+2)\n"
            "   Every transcript is saved to your output folder. Search, rename, edit, and "
            "export any past transcript in the History tab!"
        )

        tb = ctk.CTkTextbox(
            content_frame,
            wrap="word",
            font=self.font_body,
            fg_color=FAERY_ROSE_CARD,
            text_color=FAERY_TEXT_PRIMARY,
            border_width=1,
            border_color=FAERY_CARD_BORDER,
            corner_radius=12,
        )
        tb.pack(fill="both", expand=True, padx=16, pady=(4, 12))
        tb.insert("1.0", guide_text)
        tb.configure(state="disabled")

        close_btn = ctk.CTkButton(
            content_frame,
            text="✨ Got it!",
            width=120,
            height=34,
            corner_radius=17,
            font=self.font_body_bold,
            fg_color=FAERY_PURPLE,
            hover_color=FAERY_PURPLE_HOVER,
            text_color="#FCF4ED",
            command=guide_win.destroy,
        )
        close_btn.pack(anchor="e", padx=16, pady=(0, 14))

    def _show_about_dialog(self) -> None:
        """Displays bespoke Faery Good application details and credits."""
        about_win = ctk.CTkToplevel(self)
        about_win.title(f"About {APP_NAME}")
        about_win.geometry("500x420")
        about_win.resizable(False, False)
        about_win.attributes("-topmost", True)
        about_win.configure(fg_color=FAERY_BG)
        self.brand.apply_window_icon(about_win)

        content_frame = ctk.CTkFrame(
            about_win,
            corner_radius=16,
            fg_color=FAERY_CREAM_CARD,
            border_width=1,
            border_color=FAERY_CARD_BORDER,
        )
        content_frame.pack(fill="both", expand=True, padx=16, pady=16)

        brand_top = ctk.CTkFrame(content_frame, fg_color="transparent")
        brand_top.pack(fill="x", padx=16, pady=(14, 6))

        if self.brand.mascot_dialog is not None:
            m_lbl = ctk.CTkLabel(brand_top, text="", image=self.brand.mascot_dialog)
            m_lbl.pack(side="left", padx=(0, 12))

        title_col = ctk.CTkFrame(brand_top, fg_color="transparent")
        title_col.pack(side="left", fill="x", expand=True)

        if self.brand.logo_dialog is not None:
            l_lbl = ctk.CTkLabel(title_col, text="", image=self.brand.logo_dialog, anchor="w")
            l_lbl.pack(anchor="w")

        title = ctk.CTkLabel(
            title_col,
            text=f"{APP_NAME} v{APP_VERSION}",
            font=self.font_serif_card,
            text_color=FAERY_TEXT_PRIMARY,
            anchor="w",
        )
        title.pack(anchor="w", pady=(2, 0))

        sub = ctk.CTkLabel(
            title_col,
            text=f"{FAERY_GOOD_SUBTITLE} • “{FAERY_GOOD_TAGLINE}”",
            font=self.font_serif_italic,
            text_color=FAERY_TEXT_MUTED,
            anchor="w",
        )
        sub.pack(anchor="w")

        about_text = (
            "Custom-Crafted Desktop Video & Audio Transcriber for Ericka & Faery Good\n\n"
            "• Brand & Art Direction: Inspired by FaeryGood.com\n"
            "• AI Engine: faster-whisper (CTranslate2 int8 CPU, 4 threads)\n"
            "• Target Systems: macOS Sonoma (Intel x86_64) & Windows 11\n"
            "• Audio Extraction: Bundled static FFmpeg (Zero external setup)\n"
            "• Hygiene Guarantee: 100% scratch file purge via TemporaryDirectory\n"
            "• Privacy: 100% offline, on-device transcription\n\n"
            "Crafted with love & whimsy for effortless reels, stories, and video chapters."
        )

        lbl = ctk.CTkLabel(
            content_frame,
            text=about_text,
            font=self.font_body,
            text_color=FAERY_TEXT_PRIMARY,
            justify="left",
        )
        lbl.pack(anchor="w", padx=18, pady=8)

        btn_row = ctk.CTkFrame(content_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(8, 14))

        web_btn = ctk.CTkButton(
            btn_row,
            text="🦋 Visit FaeryGood.com",
            height=34,
            corner_radius=17,
            font=self.font_body_bold,
            fg_color=FAERY_SECONDARY_BTN,
            hover_color=FAERY_SECONDARY_HOVER,
            text_color=FAERY_SECONDARY_TEXT,
            command=lambda: webbrowser.open(FAERY_GOOD_URL),
        )
        web_btn.pack(side="left")

        close_btn = ctk.CTkButton(
            btn_row,
            text="✨ Close",
            width=110,
            height=34,
            corner_radius=17,
            font=self.font_body_bold,
            fg_color=FAERY_PURPLE,
            hover_color=FAERY_PURPLE_HOVER,
            text_color="#FCF4ED",
            command=about_win.destroy,
        )
        close_btn.pack(side="right")


# ---------------------------------------------------------------------------
# Application Entry Point
# ---------------------------------------------------------------------------
def main():
    """Main application bootstrap."""
    app = FaeryTranscriberApp()
    app.mainloop()


if __name__ == "__main__":
    main()
