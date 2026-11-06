"""
Faery Good Transcriber - Application Facade & Backwards Compatibility Entry Point
Re-exports all public symbols from the modular faery_app package to ensure 100% compatibility
with external scripts, packaging configurations, and unit tests.
"""

from __future__ import annotations

import os
import sys

# Disable Hugging Face symlink warnings on Windows platforms
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
# Suppress pygame community banner
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
# Prevent Intel OpenMP threads (ctranslate2) from busy-waiting and burning CPU / heat between chunks
os.environ["KMP_BLOCKTIME"] = "0"
os.environ["OMP_WAIT_POLICY"] = "PASSIVE"

# Windows High-DPI awareness initialization
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

# Re-export Constants
from faery_app.constants import *

# Re-export Config & Lifecycle
from faery_app.config.config_manager import ConfigManager
from faery_app.lifecycle.scratch import ScratchLifecycleManager
from faery_app.lifecycle.updater import AutoUpdater

# Re-export Models & Formatting
from faery_app.models.metadata import (
    MediaMetadata,
    TranscriptSegment,
    OnlineClipInfo,
    format_seconds_mm_ss,
)
from faery_app.models.formatter import TranscriptFormatter

# Re-export Media & Extraction
from faery_app.media.processor import MediaProcessor
from faery_app.media.online_fetcher import OnlineMediaFetcher
from faery_app.media.recorder import MicrophoneRecorder

# Re-export Speech Recognition Engine
from faery_app.transcription.engine import TranscriptionEngine

# Re-export Radio Subsystem
from faery_app.radio.types import RadioTrackType
from faery_app.radio.art import extract_embedded_art
from faery_app.radio.controller import RadioStationController

# Re-export History Subsystem
from faery_app.history.history_manager import HistoryRecord, HistoryManager, SearchResult

# Re-export System & Platform Utils
from faery_app.utils.system import (
    get_verified_ffmpeg_exe,
    check_free_disk_space,
    open_system_folder,
    open_system_file,
    play_completion_sound,
    is_directory_writable,
)
from faery_app.utils.macos import (
    ensure_macos_app_installed,
    prevent_app_nap,
    _create_macos_app_bundle,
    _register_macos_app_bundle,
)

# Re-export UI & Main Controller
from faery_app.ui.assets import BrandAssets
from faery_app.ui.components.segmented_button import FaerySegmentedButton
from faery_app.ui.dialogs.quick_guide import QuickGuideDialog
from faery_app.ui.dialogs.about import AboutDialog
from faery_app.ui.dialogs.overwrite_prompt import OverwritePromptDialog
from faery_app.ui.dialogs.cookie_permission import CookiePermissionDialog
from faery_app.ui.views.transcribe_view import TranscribeStudioView
from faery_app.ui.views.history_view import HistoryLibraryView
from faery_app.ui.views.radio_dock import RadioPlayerDock
from faery_app.ui.menus import MenuBuilder
from faery_app.ui.main_window import FaeryTranscriberApp


def main() -> None:
    """Bootstrap application entry point."""
    try:
        ensure_macos_app_installed()
    except Exception as exc:
        print(f"[FaeryTranscriber] Notice during startup app check: {exc}")
    app = FaeryTranscriberApp()
    app.mainloop()


if __name__ == "__main__":
    main()
