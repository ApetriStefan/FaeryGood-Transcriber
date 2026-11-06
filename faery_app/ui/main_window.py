"""
Faery Transcriber App - Main UI Coordinator & Controller
"""

from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Dict, List, Optional, Tuple

import customtkinter as ctk

from faery_app.constants import (
    APP_NAME,
    BRAND_WEBSITE,
    FAERY_LAVENDER_BG,
    FAERY_CREAM_CARD,
    FAERY_CARD_BORDER,
    FAERY_PURPLE,
    FAERY_PURPLE_HOVER,
    FAERY_ROSE_CARD,
    FAERY_ACTIVE_BORDER,
    FAERY_SEGMENT_TRACK,
    FAERY_SEGMENT_HOVER,
    FAERY_SECONDARY_BTN,
    FAERY_SECONDARY_HOVER,
    FAERY_SECONDARY_TEXT,
    FAERY_SECONDARY_DISABLED_TEXT,
    FAERY_TEXT_PRIMARY,
    FAERY_TEXT_MUTED,
    FAERY_SAGE_GREEN,
    FAERY_BERRY_RED,
    FAERY_BERRY_HOVER,
    FAERY_BERRY_TEXT,
    SUPPORTED_MEDIA_EXTENSIONS,
    MODEL_DISPLAY_NAMES,
    apply_faery_good_theme,
)
from faery_app.config.config_manager import ConfigManager
from faery_app.history.history_manager import HistoryManager, HistoryRecord
from faery_app.lifecycle.scratch import ScratchLifecycleManager
from faery_app.lifecycle.updater import AutoUpdater
from faery_app.media.online_fetcher import OnlineMediaFetcher
from faery_app.media.processor import MediaProcessor
from faery_app.media.recorder import MicrophoneRecorder
from faery_app.models.formatter import TranscriptFormatter
from faery_app.models.metadata import MediaMetadata, TranscriptSegment, format_seconds_mm_ss
from faery_app.radio.art import extract_embedded_art
from faery_app.radio.controller import RadioStationController
from faery_app.radio.types import RadioTrackType
from faery_app.transcription.engine import TranscriptionEngine
from faery_app.ui.assets import BrandAssets
from faery_app.ui.components.segmented_button import FaerySegmentedButton
from faery_app.ui.dialogs.about import AboutDialog
from faery_app.ui.dialogs.cookie_permission import CookiePermissionDialog
from faery_app.ui.dialogs.overwrite_prompt import OverwritePromptDialog
from faery_app.ui.dialogs.quick_guide import QuickGuideDialog
from faery_app.ui.menus import MenuBuilder
from faery_app.ui.views.history_view import HistoryLibraryView
from faery_app.ui.views.radio_dock import RadioPlayerDock
from faery_app.ui.views.transcribe_view import TranscribeStudioView
from faery_app.utils.macos import _get_repo_dir
from faery_app.utils.system import open_system_file, open_system_folder, play_completion_sound


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
        # Initialize fail-safe temporary scratch lifecycle hooks and background orphan sweep
        ScratchLifecycleManager.initialize_lifecycle()

        # Apply Faery Good theme before initializing CTk root
        apply_faery_good_theme()
        super().__init__()

        # Configuration, Brand Assets, and Engine instances
        self.config = ConfigManager()
        self.history = HistoryManager()
        self.engine = TranscriptionEngine()
        self.recorder = MicrophoneRecorder()
        self.brand = BrandAssets()
        self.radio_controller = RadioStationController(self.config)

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

        # History view & UI event loop tracking
        self.selected_history_id: Optional[str] = None
        self._radio_after_id: Optional[str] = None
        self._mic_timer_after_id: Optional[str] = None
        self._stream_render_after_id: Optional[str] = None
        self._search_debounce_after_id: Optional[str] = None
        self._vol_save_after_id: Optional[str] = None
        self._history_card_widgets: Dict[str, Tuple[ctk.CTkFrame, ctk.CTkLabel, ctk.CTkLabel, str]] = {}
        self._last_search_results: List[HistoryRecord] = []

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

        # Check and pull updates once a week if internet is available (non-blocking)
        self._trigger_background_update_check()

        # Start periodic radio state & playback ticker (250ms) only when radio is active
        self.config.data["radio_enabled"] = False
        if self.radio_toggle.get() == 1 or self.radio_controller.is_playing:
            self._radio_after_id = self.after(250, self._radio_tick)

    def _trigger_background_update_check(self, force: bool = False) -> None:
        """Launches a non-blocking background daemon thread to check and pull GitHub updates."""
        if not force:
            # Standalone packages and non-git environments never run background git checks
            if AutoUpdater.is_standalone_bundle() or not AutoUpdater.is_git_available():
                return
            project_dir = _get_repo_dir()
            if not (project_dir / ".git").exists():
                return

        def _worker():
            project_dir = _get_repo_dir()
            updated, msg = AutoUpdater.run_update_check_and_pull(
                config=self.config,
                project_dir=project_dir,
                force=force,
            )
            if updated:
                # Notify user gently in status label and chime
                def _notify():
                    self.status_label.configure(
                        text="✨ Faery Good Transcriber updated to the latest version from GitHub!"
                    )
                    play_completion_sound()
                self.after(0, _notify)
            elif force:
                def _show_info():
                    messagebox.showinfo("Update Check ✨", msg)
                self.after(0, _show_info)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

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

        self.radio_toggle = ctk.CTkSwitch(
            toolbar_right,
            text="📻 Radio",
            command=self._on_radio_toggle_changed,
            font=self.font_body_bold,
            progress_color=FAERY_PURPLE,
            button_color=FAERY_PURPLE,
            button_hover_color=FAERY_PURPLE_HOVER,
            text_color=FAERY_SECONDARY_TEXT,
            width=88,
            height=30,
        )
        self.radio_toggle.pack(side="left", padx=(0, 6))

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
        self._build_radio_player()

    def _build_transcribe_tab(self) -> None:
        TranscribeStudioView.build(self)

    def _build_history_tab(self) -> None:
        HistoryLibraryView.build(self)

    def _build_radio_player(self) -> None:
        RadioPlayerDock.build(self)

    def _build_menu_bar(self) -> None:
        MenuBuilder.build_menu_bar(self)

    def _setup_shortcuts(self) -> None:
        MenuBuilder.setup_shortcuts(self)

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
            except Exception:
                messagebox.showerror(
                    "Folder Not Accessible 📂",
                    "We couldn't save to the selected folder.\n\n"
                    "Please make sure you have permission to save files here, or choose another folder (such as Documents or Desktop).",
                )

    def _cleanup_mic_recording(self) -> None:
        """Cancels any active microphone timer and cleans up temporary microphone audio."""
        try:
            if self._mic_timer_after_id:
                self.after_cancel(self._mic_timer_after_id)
                self._mic_timer_after_id = None
        except Exception:
            self._mic_timer_after_id = None
        try:
            if hasattr(self, "recorder"):
                self.recorder.cleanup()
        except Exception:
            pass

    def _on_record_mic_clicked(self) -> None:
        """Toggles live microphone voice recording on or off."""
        if self.is_transcribing:
            return
        if self.recorder.is_recording:
            self._stop_mic_recording()
            return

        self._cleanup_mic_recording()
        try:
            self.recorder.start_recording()
        except IOError as err:
            messagebox.showerror("Disk Space Needed 💾", str(err))
            return
        except Exception:
            messagebox.showerror(
                "Microphone Not Available 🎙️",
                "We couldn't access a microphone on your computer.\n\n"
                "Please make sure a microphone is connected and that microphone permissions are enabled in your system settings.",
            )
            return

        self.selected_url = None
        self.selected_file = None
        self.selected_metadata = None
        self.url_entry.delete(0, "end")

        self.record_mic_btn.configure(
            text="⏹ Stop Recording",
            fg_color=FAERY_BERRY_RED,
            hover_color=FAERY_BERRY_HOVER,
            text_color=FAERY_BERRY_TEXT,
        )
        self.select_file_btn.configure(state="disabled")
        self.url_entry.configure(state="disabled")
        self.paste_url_btn.configure(state="disabled")
        self.generate_btn.configure(state="disabled")

        self.file_name_label.configure(text="🎙️ Recording from Microphone...")
        self.file_meta_label.configure(
            text="🔴 Recording live audio (00:00)   |   🔒 Saved in temporary scratch space"
        )
        self.status_label.configure(
            text="🔴 Recording microphone (00:00)... Click '⏹ Stop Recording' when finished."
        )
        self._mic_timer_after_id = self.after(250, self._recording_tick)

    def _recording_tick(self) -> None:
        """Updates the live MM:SS microphone recording counter every 250ms."""
        try:
            if not self.winfo_exists() or not self.recorder.is_recording:
                return
        except Exception:
            return

        elapsed = self.recorder.get_elapsed_seconds()
        mm_ss = format_seconds_mm_ss(elapsed)
        self.file_meta_label.configure(
            text=f"🔴 Recording live audio ({mm_ss})   |   🔒 Saved in temporary scratch space"
        )
        self.status_label.configure(
            text=f"🔴 Recording microphone ({mm_ss})... Click '⏹ Stop Recording' when finished."
        )
        self._mic_timer_after_id = self.after(250, self._recording_tick)

    def _stop_mic_recording(self) -> None:
        """Stops the active microphone recording and prepares the captured WAV for transcription."""
        try:
            if self._mic_timer_after_id:
                self.after_cancel(self._mic_timer_after_id)
                self._mic_timer_after_id = None
        except Exception:
            self._mic_timer_after_id = None

        self.record_mic_btn.configure(
            text="🎙️ Record Mic",
            fg_color=FAERY_SECONDARY_BTN,
            hover_color=FAERY_SECONDARY_HOVER,
            text_color=FAERY_SECONDARY_TEXT,
        )
        self.select_file_btn.configure(state="normal")
        self.url_entry.configure(state="normal")
        self.paste_url_btn.configure(state="normal")
        self.generate_btn.configure(state="normal")

        try:
            wav_path, metadata = self.recorder.stop_recording()
        except Exception as err:
            self.file_name_label.configure(text="No clip or link selected yet")
            self.file_meta_label.configure(
                text="Select a local file, record your microphone, or paste an Instagram, YouTube, TikTok, or Facebook link"
            )
            self.status_label.configure(
                text="✨ Ready — Select a video/audio clip, record your mic, or paste a link to begin."
            )
            messagebox.showwarning("Recording Too Short 🎙️", str(err))
            return

        self.selected_file = wav_path
        self.selected_metadata = metadata
        self.selected_url = None

        self.file_name_label.configure(text=f"🎙️ {wav_path.name}")
        self.file_meta_label.configure(
            text=f"⏱ Duration: {metadata.formatted_duration}   |   📦 Size: {metadata.formatted_size}   |   🔒 Temp audio cleaned on exit"
        )
        mod_key = "⌘Return" if sys.platform == "darwin" else "Ctrl+Enter"
        self.status_label.configure(
            text=f"✨ Microphone recording ready ({metadata.formatted_duration}). Click 'Generate Transcript' or press {mod_key}."
        )

    def _activate_online_url(self, url: str) -> None:
        """Sets an online social media URL as the active transcription source."""
        self._cleanup_mic_recording()
        clean_url = url.strip()
        self.selected_url = clean_url
        self.selected_file = None
        self.selected_metadata = None

        platform = OnlineMediaFetcher.detect_platform(clean_url)
        short_url = clean_url if len(clean_url) <= 46 else clean_url[:43] + "..."
        self.file_name_label.configure(text=f"🌐 {platform} Clip Ready")
        self.file_meta_label.configure(
            text=f"🔗 {short_url}   |   🔒 Temp audio cleaned automatically"
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
                    text="Select a local file, record your microphone, or paste an Instagram, YouTube, TikTok, or Facebook link"
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
            "Paste a Video Link 🔗",
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
        self.status_label.configure(text=f"Reading {file_path.name}...")
        self.update_idletasks()

        try:
            metadata = MediaProcessor.probe_file(file_path)
            self._cleanup_mic_recording()
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
                     f"🎵 Audio: Sound track detected"
            )
            mod_key = "⌘Return" if sys.platform == "darwin" else "Ctrl+Enter"
            self.status_label.configure(
                text=f"Ready to transcribe '{file_path.name}' ({metadata.formatted_duration}). Click 'Generate Transcript' or press {mod_key}."
            )
        except ValueError as val_err:
            messagebox.showerror("Cannot Read File 📁", str(val_err))
            self.status_label.configure(text="Selected file could not be read.")
        except Exception:
            messagebox.showerror(
                "Unable to Open File 📁",
                "We were unable to read this file. It may be in an unsupported format or currently open in another app.\n\n"
                "Tip: Try choosing an MP4, MOV, MP3, M4A, or WAV file.",
            )
            self.status_label.configure(text="✨ Ready — Select a video or audio clip to begin.")

    def _prompt_overwrite_dialog(self, base_stem: str, existing_file: Path) -> Optional[bool]:
        """Displays a Yes/No/Cancel dialog asking whether to overwrite or create a numbered copy."""
        return OverwritePromptDialog.prompt(base_stem, existing_file)

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

    def _prompt_cookie_permission_dialog(self, platform: str) -> bool:
        """Displays a Yes/No dialog asking permission to read browser cookies for a login-gated clip."""
        return CookiePermissionDialog.prompt(platform)

    def _threadsafe_prompt_cookie_permission(self, platform: str) -> bool:
        """Synchronously dispatches a cookie permission dialog onto the main Tkinter thread from a worker thread."""
        done_evt = threading.Event()
        result_box: List[bool] = [False]

        def _ask_on_main():
            try:
                result_box[0] = self._prompt_cookie_permission_dialog(platform)
            finally:
                done_evt.set()

        self.after(0, _ask_on_main)
        done_evt.wait()
        return result_box[0]

    def _on_generate_clicked(self) -> None:
        """Validates prerequisites, prompts for overwrite if file exists, and launches worker."""
        if self.is_transcribing:
            return
        if self.recorder.is_recording:
            self._stop_mic_recording()
            if not self.selected_file:
                return

        # Check if a URL was typed/pasted into the entry box
        typed_url = self.url_entry.get().strip()
        if typed_url:
            if OnlineMediaFetcher.is_valid_url(typed_url):
                self._activate_online_url(typed_url)
            elif not self.selected_file:
                messagebox.showwarning(
                    "Link Not Recognized 🔗",
                    "The link entered doesn't look quite right.\n\n"
                    "Please paste a complete web address starting with https:// (from Instagram, YouTube, TikTok, or Facebook).",
                )
                return

        has_local = bool(self.selected_file and self.selected_metadata)
        has_online = bool(self.selected_url)

        if not has_local and not has_online:
            messagebox.showwarning(
                "No Clip Selected 🎬",
                "Please choose a video or audio file from your computer or paste an Instagram, YouTube, TikTok, or Facebook link to get started.",
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
        self.record_mic_btn.configure(state="disabled")
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
                    cookie_permission_cb=self._threadsafe_prompt_cookie_permission,
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
        """Streams transcribed text live into the textbox, coalescing rapid segment bursts (60ms)."""
        def enqueue():
            self.current_segments.append(segment)
            if self._stream_render_after_id is None:
                self._stream_render_after_id = self.after(60, self._flush_stream_render)
        self.after(0, enqueue)

    def _flush_stream_render(self) -> None:
        """Renders coalesced live segments and scrolls to the bottom of the canvas."""
        self._stream_render_after_id = None
        if self.current_segments:
            self._render_current_view()
            self.textbox.see("end")

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
                text=f"⏱ Duration: {duration_str}   |   🌍 Source: {platform}   |   🔒 Temp audio cleaned automatically"
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
        self.status_label.configure(text="Transcription was cancelled. Temporary files safely cleaned up.")

    def _on_transcription_failed(self, error: Exception) -> None:
        self._reset_controls()
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(0.0)
        self.status_label.configure(text="Ready to transcribe.")

        err_msg = str(error)
        lower_msg = err_msg.lower()
        if "disk space" in lower_msg:
            messagebox.showerror(
                "Disk Space Needed 💾",
                "Your computer is running low on disk space to process this audio.\n\n"
                "Please free up a small amount of disk space (at least 500 MB) on your drive and try again.",
            )
        elif any(k in lower_msg for k in ("could not download", "requires you to be logged in", "requires you to be signed in", "requires sign-in", "login", "cookie", "private")):
            if "instagram" in lower_msg or "facebook" in lower_msg:
                messagebox.showerror(
                    "Instagram / Facebook Sign-In 🔐",
                    "This post requires you to be signed in to access it (or it may be set to private).\n\n"
                    "Helpful tips:\n"
                    "• Under Studio Preferences, select your web browser in '🔐 Social Login' so the transcriber can access your signed-in session.\n"
                    "• Check that the post is still available online.\n"
                    "• Make sure your computer is connected to the internet.",
                )
            else:
                messagebox.showerror(
                    "Video Link Notice 🌐",
                    "We couldn't download the audio from this link.\n\n"
                    "Helpful tips:\n"
                    "• Make sure the video is public and available to watch online.\n"
                    "• If this video requires sign-in, try selecting your browser in '🔐 Social Login' under Studio Preferences.\n"
                    "• Check that your internet connection is active.",
                )
        elif "hugging face" in lower_msg or ("download" in lower_msg and "model" in lower_msg) or "connection" in lower_msg or "offline" in lower_msg:
            messagebox.showerror(
                "Model Download Connection 🌐",
                "The speech engine needs to download the transcription model for your first use.\n\n"
                "Please check your internet connection and try again. Once downloaded once, it works completely offline!",
            )
        elif "timeout" in lower_msg or "timed out" in lower_msg:
            messagebox.showerror(
                "Connection Timed Out 🌐",
                "The connection took too long to complete.\n\n"
                "Please check your internet connection and click 'Generate Transcript' again.",
            )
        elif "no audio" in lower_msg or "empty audio" in lower_msg or "no speech" in lower_msg:
            messagebox.showinfo(
                "No Spoken Words Detected 🎙️",
                "We processed the audio, but no spoken speech was detected in this clip.\n\n"
                "If there is faint speech, you can try selecting the 'High Accuracy' model option and trying again.",
            )
        elif "ffmpeg" in lower_msg or "audio extraction failed" in lower_msg or "corrupt" in lower_msg:
            messagebox.showerror(
                "Audio File Notice 🎵",
                "We were unable to read the audio track from this media file.\n\n"
                "Helpful tips:\n"
                "• Check that the video or audio file plays normally in your media player.\n"
                "• Try converting or re-saving the file as an MP4, MOV, MP3, or WAV.",
            )
        elif "memory" in lower_msg:
            messagebox.showerror(
                "Memory Limit Reached ⚡",
                "Your computer ran low on temporary memory while transcribing.\n\n"
                "Helpful tips:\n"
                "• Try selecting the 'Standard / Fast' model option under Studio Preferences.\n"
                "• Close other memory-heavy applications and try again.",
            )
        elif "permission" in lower_msg or "access is denied" in lower_msg:
            messagebox.showerror(
                "Folder Access Needed 📁",
                "The transcriber doesn't have permission to write to your output folder.\n\n"
                "Please choose a different output folder (such as Documents or Desktop) under Studio Preferences.",
            )
        else:
            first_line = err_msg.strip().split("\n")[0]
            for prefix in ("RuntimeError:", "ValueError:", "IOError:", "OSError:", "Exception:", "Error:"):
                if first_line.startswith(prefix):
                    first_line = first_line[len(prefix):].strip()

            clean_err = first_line if len(first_line) <= 120 else first_line[:117] + "..."
            if not clean_err or any(token in clean_err.lower() for token in ("traceback", "file \"", "line ", "0x", "nonetype")):
                friendly_body = (
                    "We encountered a small hiccup while processing this clip.\n\n"
                    "Don't worry — no work was lost! Please try choosing the file or link again, "
                    "or try the 'Standard / Fast' model option."
                )
            else:
                friendly_body = (
                    f"We encountered an issue while processing this clip:\n\n{clean_err}\n\n"
                    "Tip: Try choosing another file or link, or try again in a moment."
                )

            messagebox.showerror(
                "Transcription Notice ✨",
                friendly_body,
            )

    def _reset_controls(self) -> None:
        if self._stream_render_after_id is not None:
            try:
                self.after_cancel(self._stream_render_after_id)
            except Exception:
                pass
            self._stream_render_after_id = None
        self.is_transcribing = False
        self.record_mic_btn.configure(state="normal")
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
            self.status_label.configure(text="Cancelling and cleaning up temporary files...")
            self.cancel_btn.configure(state="disabled")

    def _on_view_mode_changed(self, choice: str) -> None:
        self._render_current_view()

    def _render_current_view(self) -> None:
        """Renders the segments in the selected format into the editable text area."""
        if not self.current_segments:
            return

        choice = self.view_selector.get()
        if choice in ("⏱️ Timestamped", "⏱️ Timecoded (YouTube)", "⏱️ Timecoded"):
            text_to_show = TranscriptFormatter.to_timecoded(self.current_segments)
        elif choice == "📝 Raw Text":
            text_to_show = TranscriptFormatter.to_raw(self.current_segments)
        else:
            text_to_show = TranscriptFormatter.to_paragraphs(self.current_segments)

        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", text_to_show)
        self._update_stats(content_text=text_to_show)

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
            messagebox.showinfo(
                "No Transcript to Save 📝",
                "Your transcript is currently empty. Generate a transcript or enter some text before saving.",
            )
            return

        mode = self.view_selector.get()
        suffix = (
            "_timecoded.txt"
            if ("Timestamped" in mode or "Timecoded" in mode)
            else ("_raw.txt" if "Raw" in mode else "_paragraphs.txt")
        )
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
            except Exception:
                messagebox.showerror(
                    "Could Not Save File 💾",
                    "We couldn't save your text file.\n\nPlease check that you have permission to write to this folder and that the file isn't currently open in another app.",
                )

    def _on_save_md_clicked(self) -> None:
        content = self.textbox.get("1.0", "end-1c").strip()
        if not content:
            messagebox.showinfo(
                "No Transcript to Save 📝",
                "Your transcript is currently empty. Generate a transcript or enter some text before saving.",
            )
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
            except Exception:
                messagebox.showerror(
                    "Could Not Save File 💾",
                    "We couldn't save your Markdown transcript file.\n\nPlease check that you have permission to write to this folder and that the file isn't open in another app.",
                )

    def _on_open_folder_clicked(self) -> None:
        target = self.config.output_directory
        try:
            open_system_folder(target)
        except Exception:
            messagebox.showerror(
                "Cannot Open Folder 📂",
                "We couldn't open your output folder. It may have been moved or deleted.\n\nTip: You can select a new output folder under Studio Preferences.",
            )

    def _update_stats(self, event=None, content_text: Optional[str] = None) -> int:
        content = (
            self.textbox.get("1.0", "end-1c").strip()
            if content_text is None
            else content_text.strip()
        )
        if not content:
            self.stats_badge.configure(text="0 words  |  0 characters")
            return 0

        words = len(content.split())
        chars = len(content)
        self.stats_badge.configure(text=f"{words:,} words  |  {chars:,} characters")
        return words

    # -----------------------------------------------------------------------
    # GUI Event Handlers (History Tab & CRUD Operations)
    # -----------------------------------------------------------------------
    def _on_history_search_changed(self, event=None) -> None:
        """Handles real-time search typing (debounced 80ms for keystrokes) and toggles the clear pill button."""
        raw_val = self.history_search_entry.get()
        if raw_val:
            self.history_search_clear_btn.grid(row=0, column=1, padx=(6, 0))
        else:
            self.history_search_clear_btn.grid_forget()

        if self._search_debounce_after_id is not None:
            try:
                self.after_cancel(self._search_debounce_after_id)
            except Exception:
                pass
            self._search_debounce_after_id = None

        if event is None:
            self._refresh_history_list(filter_text=raw_val.strip(), resync=False)
        else:
            self._search_debounce_after_id = self.after(80, self._execute_debounced_search)

    def _execute_debounced_search(self) -> None:
        """Executes the debounced history search query."""
        self._search_debounce_after_id = None
        if hasattr(self, "history_search_entry"):
            self._refresh_history_list(filter_text=self.history_search_entry.get().strip(), resync=False)

    def _on_clear_search_clicked(self) -> None:
        """Clears the history search box and restores the complete transcript list."""
        if self._search_debounce_after_id is not None:
            try:
                self.after_cancel(self._search_debounce_after_id)
            except Exception:
                pass
            self._search_debounce_after_id = None
        self.history_search_entry.delete(0, "end")
        self.history_search_clear_btn.grid_forget()
        self._refresh_history_list(filter_text="", resync=False)
        self.history_search_entry.focus_set()

    def _on_history_search_enter(self, event=None) -> None:
        """Selects the first matching transcript when the user presses Enter in search."""
        if self._search_debounce_after_id is not None:
            try:
                self.after_cancel(self._search_debounce_after_id)
            except Exception:
                pass
            self._search_debounce_after_id = None
        query = self.history_search_entry.get().strip()
        self._refresh_history_list(filter_text=query, resync=False)
        if self._last_search_results:
            self._select_history_item(self._last_search_results[0].id)

    def _refresh_history_list(self, filter_text: Optional[str] = None, resync: bool = False) -> None:
        """Populates the left-hand scrollable library list using instant smart search."""
        if resync:
            records = self.history.sync_with_directory(self.config.output_directory)
        else:
            records = self.history.records

        if filter_text is None:
            filter_text = self.history_search_entry.get().strip() if hasattr(self, "history_search_entry") else ""

        self._history_card_widgets.clear()
        for widget in self.history_list_frame.winfo_children():
            widget.destroy()

        query = filter_text.strip()
        matching_results = self.history.search_with_snippets(query)
        self._last_search_results = [rec for rec, _ in matching_results]

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

            title_lbl = ctk.CTkLabel(
                card,
                text=f"🦋 {record.title}" if is_selected else record.title,
                font=self.font_serif_card,
                text_color=FAERY_TEXT_PRIMARY,
                anchor="w",
            )
            title_lbl.pack(fill="x", padx=12, pady=(8, 2))

            snippet_lbl = None
            if snippet:
                snippet_lbl = ctk.CTkLabel(
                    card,
                    text=f"💬 {snippet}",
                    font=self.font_small,
                    text_color=FAERY_PURPLE,
                    anchor="w",
                    justify="left",
                )
                snippet_lbl.pack(fill="x", padx=12, pady=(0, 2))

            meta_str = f"📅 {record.created_at}   •   ⏱ {record.duration_str}"
            meta_lbl = ctk.CTkLabel(
                card,
                text=meta_str,
                font=self.font_small,
                text_color=FAERY_TEXT_MUTED,
                anchor="w",
            )
            meta_lbl.pack(fill="x", padx=12, pady=(0, 2))

            w_str = f"✨ {record.word_count} words" if record.word_count > 0 else "✨ Transcript ready"
            w_lbl = ctk.CTkLabel(
                card,
                text=w_str,
                font=self.font_small,
                text_color=FAERY_TEXT_MUTED,
                anchor="w",
            )
            w_lbl.pack(fill="x", padx=12, pady=(0, 8))

            self._history_card_widgets[record.id] = (card, title_lbl, w_lbl, record.title)

            elements = [card, title_lbl, meta_lbl, w_lbl]
            if snippet_lbl is not None:
                elements.append(snippet_lbl)
            for elem in elements:
                elem.bind("<Button-1>", lambda e, r_id=record.id: self._select_history_item(r_id))

    def _update_history_selection_visuals(self, prev_id: Optional[str], new_id: Optional[str]) -> None:
        """Updates history card selection borders and butterfly badges in-place in O(1) time."""
        if prev_id and prev_id in self._history_card_widgets:
            card, title_lbl, _, clean_title = self._history_card_widgets[prev_id]
            try:
                card.configure(fg_color=FAERY_CREAM_CARD, border_width=1, border_color=FAERY_CARD_BORDER)
                title_lbl.configure(text=clean_title)
            except Exception:
                pass
        if new_id and new_id in self._history_card_widgets:
            card, title_lbl, _, clean_title = self._history_card_widgets[new_id]
            try:
                card.configure(fg_color=FAERY_ROSE_CARD, border_width=2, border_color=FAERY_ACTIVE_BORDER)
                title_lbl.configure(text=f"🦋 {clean_title}")
            except Exception:
                pass

    def _select_history_item(self, record_id: str) -> None:
        """Selects a transcript from the list and loads its details and preview."""
        prev_id = self.selected_history_id
        self.selected_history_id = record_id
        record = next((r for r in self.history.records if r.id == record_id), None)
        if not record:
            return

        if record_id in self._history_card_widgets:
            self._update_history_selection_visuals(prev_id, record_id)
        else:
            self._refresh_history_list(filter_text=None, resync=False)

        self.history_title_label.configure(text=record.title)
        self.history_meta_label.configure(
            text=f"Created: {record.created_at}   |   Duration: {record.duration_str}   |   Words: {record.word_count}"
        )

        self.h_rename_btn.configure(state="normal")
        self.h_save_btn.configure(state="normal")
        self.h_copy_btn.configure(state="normal")
        self.h_open_file_btn.configure(state="normal")
        self.h_delete_btn.configure(state="normal")

        self._load_history_preview(record)

    def _on_history_view_mode_changed(self, choice: str) -> None:
        if self.selected_history_id:
            record = next((r for r in self.history.records if r.id == self.selected_history_id), None)
            if record:
                self._load_history_preview(record)

    def _load_history_preview(self, record: HistoryRecord) -> None:
        choice = self.history_view_selector.get()
        target_path = None
        if choice in ("⏱️ Timestamped", "⏱️ Timecoded"):
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
            title="Rename Transcript ✏️",
        )
        new_title = dialog.get_input()
        if new_title and new_title.strip():
            try:
                updated = self.history.rename_record(self.selected_history_id, new_title.strip())
                if updated:
                    self.history_title_label.configure(text=updated.title)
                    self._refresh_history_list(filter_text=None, resync=False)
                    self._load_history_preview(updated)
            except Exception:
                messagebox.showerror(
                    "Could Not Rename ✏️",
                    "We couldn't rename this transcript.\n\nPlease make sure the file isn't currently open in another application and try again.",
                )

    def _on_history_save_edits_clicked(self) -> None:
        """Saves current edits from the history textbox directly to the active file."""
        if not self.selected_history_id:
            return

        record = next((r for r in self.history.records if r.id == self.selected_history_id), None)
        if not record:
            return

        choice = self.history_view_selector.get()
        target_path = None
        if choice in ("⏱️ Timestamped", "⏱️ Timecoded"):
            target_path = record.timecoded_file
        elif choice == "📝 Markdown":
            target_path = record.markdown_file
        else:
            target_path = record.paragraphs_file

        if not target_path:
            messagebox.showwarning(
                "File Not Found 📄",
                "There is no saved file on disk for this format yet.",
            )
            return

        content = self.history_textbox.get("1.0", "end-1c")
        try:
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)
            if hasattr(self.history, "update_record_content"):
                self.history.update_record_content(
                    self.selected_history_id,
                    content,
                    update_fts=(choice not in ("⏱️ Timestamped", "⏱️ Timecoded")),
                )
            else:
                record.word_count = len(content.split())
                self.history.save()
            self.history_meta_label.configure(
                text=f"Created: {record.created_at}   |   Duration: {record.duration_str}   |   Words: {record.word_count}"
            )
            if self.selected_history_id in self._history_card_widgets:
                _, _, w_lbl, _ = self._history_card_widgets[self.selected_history_id]
                w_str = f"✨ {record.word_count} words" if record.word_count > 0 else "✨ Transcript ready"
                w_lbl.configure(text=w_str)
            self.h_save_btn.configure(text="✓ Saved!", fg_color=FAERY_SAGE_GREEN, text_color="#FCF4ED")
            self.after(
                2000,
                lambda: self.h_save_btn.configure(
                    text="💾 Save Edits",
                    fg_color=FAERY_SECONDARY_BTN,
                    text_color=FAERY_SECONDARY_TEXT,
                ),
            )
        except Exception:
            messagebox.showerror(
                "Could Not Save Edits 💾",
                "We couldn't save your edits to disk.\n\nPlease check that the file isn't open or locked by another app.",
            )

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
            record.timecoded_file if choice in ("⏱️ Timestamped", "⏱️ Timecoded")
            else (record.markdown_file if choice == "📝 Markdown" else record.paragraphs_file)
        )
        if target_path and os.path.exists(target_path):
            open_system_file(Path(target_path))
        else:
            messagebox.showinfo(
                "File Moved or Missing 📂",
                "This file could not be found in your output folder. It may have been moved or deleted.",
            )

    def _on_history_reveal_folder_clicked(self) -> None:
        open_system_folder(self.config.output_directory)

    def _on_history_delete_clicked(self) -> None:
        if not self.selected_history_id:
            return

        record = next((r for r in self.history.records if r.id == self.selected_history_id), None)
        if not record:
            return

        if messagebox.askyesno(
            "Delete Transcript? 🗑️",
            f"Are you sure you want to delete '{record.title}' and its saved transcript files?\n\nThis cannot be undone.",
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

    # -----------------------------------------------------------------------
    # Faery Good Radio (104.9 The Grift FM) - Ambient Bottom Bar Controller
    # -----------------------------------------------------------------------
    def _on_radio_toggle_changed(self) -> None:
        """Called when the 📻 Radio toggle switch in the header is flipped."""
        is_on = self.radio_toggle.get() == 1
        if is_on:
            self.radio_player_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 14))
            self.config.radio_enabled = True
            if not self.radio_controller.is_playing:
                self.radio_controller.start()
            if self._radio_after_id is None:
                self._radio_after_id = self.after(250, self._radio_tick)
        else:
            if self._radio_after_id is not None:
                try:
                    self.after_cancel(self._radio_after_id)
                except Exception:
                    pass
                self._radio_after_id = None
            self.radio_controller.stop()
            self.radio_player_frame.grid_forget()
            self.config.radio_enabled = False

    def _toggle_radio(self) -> None:
        """Toggles the radio switch via keyboard shortcut (⌘R / Ctrl+R) or View menu."""
        if self.radio_toggle.get() == 1:
            self.radio_toggle.deselect()
        else:
            self.radio_toggle.select()
        self._on_radio_toggle_changed()

    def _close_radio_player(self) -> None:
        """Hides the radio player and turns the toggle switch off."""
        self.radio_toggle.deselect()
        self._on_radio_toggle_changed()

    def _on_radio_play_pause_clicked(self) -> None:
        """Toggles radio play/pause."""
        self.radio_controller.toggle_play_pause()
        self.radio_play_pause_btn.configure(text="⏸" if not self.radio_controller.is_paused else "▶")

    def _on_radio_next_clicked(self) -> None:
        """Advances to the next song."""
        self.radio_controller.next_song()

    def _on_radio_prev_clicked(self) -> None:
        """Returns to the previous song or restarts current track."""
        self.radio_controller.prev_song()

    def _on_radio_volume_changed(self, val: float) -> None:
        """Handles volume slider movement with 250ms debounced disk persistence."""
        self.radio_controller.set_volume(float(val), persist=False)
        self._update_radio_mute_icon()
        if self._vol_save_after_id is not None:
            try:
                self.after_cancel(self._vol_save_after_id)
            except Exception:
                pass
        self._vol_save_after_id = self.after(250, self._flush_volume_save)

    def _flush_volume_save(self) -> None:
        """Persists the current radio volume to disk after slider movement settles."""
        self._vol_save_after_id = None
        self.config.save()

    def _adjust_radio_volume(self, delta: float) -> None:
        """Adjusts radio volume incrementally (e.g. from arrow key shortcuts)."""
        new_vol = max(0.0, min(1.0, self.radio_controller.volume + delta))
        self.radio_controller.set_volume(new_vol)
        self.radio_volume_slider.set(new_vol)
        self._update_radio_mute_icon()

    def _on_radio_mute_clicked(self) -> None:
        """Toggles mute on/off."""
        self.radio_controller.toggle_mute()
        self.radio_volume_slider.set(0.0 if self.radio_controller.is_muted else self.radio_controller.volume)
        self._update_radio_mute_icon()

    def _update_radio_mute_icon(self) -> None:
        """Updates the speaker icon to match volume/mute state."""
        if self.radio_controller.is_muted or self.radio_controller.volume == 0.0:
            self.radio_mute_btn.configure(text="🔇")
        elif self.radio_controller.volume < 0.35:
            self.radio_mute_btn.configure(text="🔈")
        elif self.radio_controller.volume < 0.7:
            self.radio_mute_btn.configure(text="🔉")
        else:
            self.radio_mute_btn.configure(text="🔊")

    def _on_timeline_clicked(self, event) -> None:
        """Allows clicking on the progress bar to skip to that specific part of the song."""
        if not hasattr(self, "radio_controller") or not self.radio_controller.is_playing:
            return
        total = self.radio_controller.current_duration
        if total <= 0.0:
            return

        try:
            width = max(1, self.radio_progress.winfo_width())
            x_pos = max(0, min(width, event.x))
            ratio = x_pos / float(width)
            target_sec = ratio * total

            self.radio_controller.seek_to(target_sec)

            self.radio_progress.set(min(1.0, max(0.0, ratio)))
            self.radio_time_curr.configure(text=format_seconds_mm_ss(target_sec))
        except Exception as err:
            print(f"[Faery Radio] Seek error: {err}", file=sys.stderr)

    def _radio_tick(self) -> None:
        """Periodic 250ms tick loop: updates radio progress bar, track labels, embedded artwork, and state."""
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        try:
            if hasattr(self, "radio_controller") and self.radio_controller.is_playing:
                self.radio_controller.check_and_advance()

                self.radio_title_label.configure(text=self.radio_controller.current_track_title)
                self.radio_artist_label.configure(text=self.radio_controller.current_track_subtitle)

                current_p = self.radio_controller.current_track_path
                curr_key = str(current_p) if current_p else ""
                if curr_key != self._current_art_path:
                    self._current_art_path = curr_key
                    if curr_key:
                        if curr_key not in self._art_image_cache:
                            self._art_image_cache[curr_key] = extract_embedded_art(current_p, target_size=(44, 44))
                        art_img = self._art_image_cache[curr_key]
                        if art_img:
                            self.radio_art_lbl.configure(text="", image=art_img)
                        else:
                            self.radio_art_lbl.configure(text="📻", image=None)
                    else:
                        self.radio_art_lbl.configure(text="📻", image=None)

                t_type = self.radio_controller.current_track_type
                if t_type == RadioTrackType.LIABILITY:
                    self.radio_live_badge.configure(
                        text="DISCLAIMER",
                        fg_color=FAERY_BERRY_RED,
                        text_color=FAERY_BERRY_TEXT,
                    )
                elif t_type in (RadioTrackType.ANNOUNCER, RadioTrackType.GRIFT):
                    self.radio_live_badge.configure(
                        text="INTERLUDE",
                        fg_color=FAERY_SECONDARY_BTN,
                        text_color=FAERY_SECONDARY_TEXT,
                    )
                else:
                    self.radio_live_badge.configure(
                        text="ON AIR",
                        fg_color=FAERY_PURPLE,
                        text_color=("#FCF4ED", "#FCF4ED"),
                    )

                elapsed = self.radio_controller.get_elapsed_seconds()
                total = self.radio_controller.current_duration
                self.radio_time_curr.configure(text=format_seconds_mm_ss(elapsed))
                self.radio_time_total.configure(text=format_seconds_mm_ss(total) if total > 0 else "--:--")
                self.radio_progress.set(min(1.0, max(0.0, elapsed / total)) if total > 0 else 0.0)

                self.radio_play_pause_btn.configure(text="⏸" if not self.radio_controller.is_paused else "▶")
        except Exception:
            pass
        finally:
            try:
                if self.winfo_exists() and (
                    self.radio_toggle.get() == 1
                    or (hasattr(self, "radio_controller") and self.radio_controller.is_playing)
                ):
                    self._radio_after_id = self.after(250, self._radio_tick)
                else:
                    self._radio_after_id = None
            except Exception:
                self._radio_after_id = None

    def destroy(self) -> None:
        """Ensures cleanup of timers, radio playback, and scratch space upon destruction."""
        self._cleanup_mic_recording()
        for attr in ("_radio_after_id", "_stream_render_after_id", "_search_debounce_after_id", "_vol_save_after_id"):
            try:
                timer_id = getattr(self, attr, None)
                if timer_id is not None:
                    self.after_cancel(timer_id)
                    setattr(self, attr, None)
                    if attr == "_vol_save_after_id":
                        self.config.save()
            except Exception:
                pass
        try:
            if hasattr(self, "radio_controller"):
                self.radio_controller.stop()
        except Exception:
            pass
        try:
            ScratchLifecycleManager.cleanup_all_active()
        except Exception:
            pass
        super().destroy()

    def _on_window_close(self) -> None:
        """Handles graceful application shutdown, guaranteeing scratch purge."""
        if self.is_transcribing:
            if messagebox.askyesno(
                "Transcription in Progress ⏳",
                "A transcription is currently running. Would you like to cancel it and exit now?",
            ):
                self.cancel_event.set()
                self.destroy()
        else:
            self.destroy()

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
        QuickGuideDialog(self)

    def _show_about_dialog(self) -> None:
        """Displays bespoke Faery Good application details and credits."""
        AboutDialog(self)
