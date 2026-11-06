"""
Faery Good Transcriber Package
Whimsy is Power • On-Device Desktop Transcription for Reels & YouTube
https://faerygood.com/
"""

from __future__ import annotations

# Constants and Configuration
from faery_app.constants import *
from faery_app.config.config_manager import ConfigManager
from faery_app.lifecycle.scratch import ScratchLifecycleManager
from faery_app.lifecycle.updater import AutoUpdater

# Domain Models & Formatting
from faery_app.models.metadata import (
    MediaMetadata,
    TranscriptSegment,
    OnlineClipInfo,
    format_seconds_mm_ss,
)
from faery_app.models.formatter import TranscriptFormatter

# Audio Processing & Online Fetcher
from faery_app.media.processor import MediaProcessor
from faery_app.media.online_fetcher import OnlineMediaFetcher
from faery_app.media.recorder import MicrophoneRecorder

# Speech Recognition Engine
from faery_app.transcription.engine import TranscriptionEngine

# Radio Engine
from faery_app.radio.types import RadioTrackType
from faery_app.radio.art import extract_embedded_art
from faery_app.radio.controller import RadioStationController

# History Subsystem
from faery_app.history.history_manager import HistoryRecord, HistoryManager, SearchResult

# System & OS Integration Utils
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
    _create_macos_app_bundle,
    _register_macos_app_bundle,
)

# User Interface
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

__all__ = [
    # Constants
    "APP_NAME",
    "APP_VERSION",
    "FAERY_GOOD_TAGLINE",
    "FAERY_GOOD_SUBTITLE",
    "FAERY_GOOD_URL",
    "BRAND_TAGLINE",
    "BRAND_SUBTITLE",
    "BRAND_WEBSITE",
    "CONFIG_FILE_NAME",
    "CONFIG_PATH",
    "HISTORY_FILE_NAME",
    "HISTORY_PATH",
    "DB_FILE_NAME",
    "DB_PATH",
    "DEFAULT_OUTPUT_DIR",
    "SUPPORTED_MEDIA_EXTENSIONS",
    "MODEL_DISPLAY_NAMES",
    "DEFAULT_MODEL_DISPLAY",
    "COOKIE_BROWSER_OPTIONS",
    "DEFAULT_COOKIE_BROWSER",
    "MIN_DISK_SPACE_MB",
    "FAERY_PURPLE",
    "FAERY_PURPLE_HOVER",
    "FAERY_LAVENDER_BG",
    "FAERY_BG",
    "FAERY_CREAM_CARD",
    "FAERY_ROSE_CARD",
    "FAERY_CARD_BORDER",
    "FAERY_DIVIDER",
    "FAERY_ACTIVE_BORDER",
    "FAERY_SEGMENT_TRACK",
    "FAERY_SEGMENT_HOVER",
    "FAERY_SECONDARY_BTN",
    "FAERY_SECONDARY_HOVER",
    "FAERY_SECONDARY_TEXT",
    "FAERY_SECONDARY_DISABLED_TEXT",
    "FAERY_TEXT_PRIMARY",
    "FAERY_TEXT_MUTED",
    "FAERY_SAGE_GREEN",
    "FAERY_BERRY_RED",
    "FAERY_BERRY_HOVER",
    "FAERY_BERRY_TEXT",
    "get_assets_dir",
    "get_music_dir",
    "get_announcer_dir",
    "apply_faery_good_theme",
    # Config & Lifecycle
    "ConfigManager",
    "ScratchLifecycleManager",
    "AutoUpdater",
    # Models & Formatting
    "MediaMetadata",
    "TranscriptSegment",
    "OnlineClipInfo",
    "format_seconds_mm_ss",
    "TranscriptFormatter",
    # Media
    "MediaProcessor",
    "OnlineMediaFetcher",
    "MicrophoneRecorder",
    # Transcription
    "TranscriptionEngine",
    # Radio
    "RadioTrackType",
    "extract_embedded_art",
    "RadioStationController",
    # History
    "HistoryRecord",
    "HistoryManager",
    "SearchResult",
    # Utils
    "get_verified_ffmpeg_exe",
    "check_free_disk_space",
    "open_system_folder",
    "open_system_file",
    "play_completion_sound",
    "is_directory_writable",
    "ensure_macos_app_installed",
    "_create_macos_app_bundle",
    "_register_macos_app_bundle",
    # UI
    "BrandAssets",
    "FaerySegmentedButton",
    "QuickGuideDialog",
    "AboutDialog",
    "OverwritePromptDialog",
    "CookiePermissionDialog",
    "TranscribeStudioView",
    "HistoryLibraryView",
    "RadioPlayerDock",
    "MenuBuilder",
    "FaeryTranscriberApp",
]
