"""
Native System Menu Bar & Keyboard Shortcut Builder for Faery Good Transcriber
"""

from __future__ import annotations

import sys
import tkinter as tk
import webbrowser

import customtkinter as ctk

from faery_app.constants import APP_NAME, FAERY_GOOD_URL


class MenuBuilder:
    """Constructs native menu bar and binds keyboard shortcuts."""

    @staticmethod
    def build_menu_bar(app) -> None:
        """Constructs native system menu bar (mounted to macOS top bar or Windows title bar)."""
        is_mac = sys.platform == "darwin"
        mod_sym = "Cmd" if is_mac else "Ctrl"

        menu_bar = tk.Menu(app)

        # File Menu
        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(
            label="Select Local Media File...",
            accelerator=f"{mod_sym}+O",
            command=app._on_select_file_clicked,
        )
        file_menu.add_command(
            label="Record from Microphone (Start / Stop)",
            accelerator=f"{mod_sym}+D",
            command=app._on_record_mic_clicked,
        )
        file_menu.add_command(
            label="Paste Online Video / Reel Link",
            accelerator=f"{mod_sym}+L",
            command=app._on_paste_url_clicked,
        )
        file_menu.add_command(
            label="Open Output Folder",
            accelerator=f"Shift+{mod_sym}+O",
            command=app._on_open_folder_clicked,
        )
        file_menu.add_separator()
        file_menu.add_command(
            label="Save Clean Text (.txt)...",
            accelerator=f"{mod_sym}+S",
            command=app._on_save_txt_clicked,
        )
        file_menu.add_command(
            label="Save Markdown (.md)...",
            command=app._on_save_md_clicked,
        )
        if not is_mac:
            file_menu.add_separator()
            file_menu.add_command(
                label="Exit",
                accelerator="Alt+F4",
                command=app._on_window_close,
            )
        menu_bar.add_cascade(label="File", menu=file_menu)

        # Edit Menu
        edit_menu = tk.Menu(menu_bar, tearoff=0)
        edit_menu.add_command(
            label="Copy Active Transcript",
            accelerator=f"Shift+{mod_sym}+C",
            command=app._on_copy_clicked,
        )
        edit_menu.add_command(
            label="Select All in Textbox",
            accelerator=f"{mod_sym}+A",
            command=app._select_all_active_text,
        )
        menu_bar.add_cascade(label="Edit", menu=edit_menu)

        # View Menu
        view_menu = tk.Menu(menu_bar, tearoff=0)
        view_menu.add_command(
            label="🎙️ Transcribe Studio",
            accelerator=f"{mod_sym}+1",
            command=lambda: app.tabview.set("🎙️ Transcribe"),
        )
        view_menu.add_command(
            label="📜 History Library",
            accelerator=f"{mod_sym}+2",
            command=lambda: app.tabview.set("📜 History"),
        )
        view_menu.add_separator()
        view_menu.add_command(
            label="📻 Toggle Faery Radio",
            accelerator=f"{mod_sym}+R",
            command=app._toggle_radio,
        )
        view_menu.add_command(
            label="⏯ Play / Pause Radio",
            accelerator="Space",
            command=app._on_radio_play_pause_clicked,
        )
        view_menu.add_command(
            label="⏭ Next Track",
            accelerator=f"{mod_sym}+Right",
            command=app._on_radio_next_clicked,
        )
        view_menu.add_command(
            label="⏮ Previous Track",
            accelerator=f"{mod_sym}+Left",
            command=app._on_radio_prev_clicked,
        )
        view_menu.add_separator()
        view_menu.add_command(
            label="Toggle Dark / Light Theme",
            command=app._cycle_theme,
        )
        menu_bar.add_cascade(label="View", menu=view_menu)

        # Help Menu
        help_menu = tk.Menu(menu_bar, tearoff=0)
        help_menu.add_command(
            label="Check for Updates from GitHub...",
            command=lambda: app._trigger_background_update_check(force=True),
        )
        help_menu.add_command(
            label="Quick Start Guide for Creators",
            command=app._show_quick_guide,
        )
        help_menu.add_command(
            label="Visit FaeryGood.com 🦋",
            command=lambda: webbrowser.open(FAERY_GOOD_URL),
        )
        help_menu.add_separator()
        help_menu.add_command(
            label="📋 Copy Diagnostic Log for Stef",
            command=app.copy_diagnostic_log,
        )
        help_menu.add_separator()
        help_menu.add_command(
            label=f"About {APP_NAME}",
            command=app._show_about_dialog,
        )
        menu_bar.add_cascade(label="Help", menu=help_menu)

        app.configure(menu=menu_bar)

    @staticmethod
    def setup_shortcuts(app) -> None:
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
            app.bind_class("Text", f"<{mod}-Key-a>", select_all_text)
            app.bind_class("Entry", f"<{mod}-Key-a>", select_all_entry)

            # Application actions
            app.bind(f"<{mod}-Key-o>", lambda e: app._on_select_file_clicked())
            app.bind(f"<{mod}-Key-d>", lambda e: app._on_record_mic_clicked())
            app.bind(f"<{mod}-Key-D>", lambda e: app._on_record_mic_clicked())
            app.bind(f"<{mod}-Key-l>", lambda e: app._on_paste_url_clicked())
            app.bind(f"<{mod}-Shift-Key-O>", lambda e: app._on_open_folder_clicked())
            app.bind(f"<{mod}-Shift-Key-o>", lambda e: app._on_open_folder_clicked())
            app.bind(f"<{mod}-Shift-Key-C>", lambda e: app._on_copy_clicked())
            app.bind(f"<{mod}-Shift-Key-c>", lambda e: app._on_copy_clicked())
            app.bind(f"<{mod}-Key-s>", lambda e: app._on_quick_save())
            app.bind(f"<{mod}-Key-Return>", lambda e: app._on_generate_clicked())
            app.bind(f"<{mod}-KP_Enter>", lambda e: app._on_generate_clicked())
            app.bind(f"<{mod}-Key-r>", lambda e: app._toggle_radio())
            app.bind(f"<{mod}-Key-R>", lambda e: app._toggle_radio())
            app.bind(f"<{mod}-Key-1>", lambda e: app.tabview.set("🎙️ Transcribe"))
            app.bind(f"<{mod}-Key-2>", lambda e: app.tabview.set("📜 History"))
            app.bind(f"<{mod}-Key-q>", lambda e: app._on_window_close())

            # Media Player Shortcuts (Cmd/Ctrl + Right/Left, Cmd/Ctrl + Up/Down, Cmd/Ctrl + M)
            app.bind(f"<{mod}-Right>", lambda e: app._on_radio_next_clicked())
            app.bind(f"<{mod}-Left>", lambda e: app._on_radio_prev_clicked())
            app.bind(f"<{mod}-Up>", lambda e: app._adjust_radio_volume(0.05))
            app.bind(f"<{mod}-Down>", lambda e: app._adjust_radio_volume(-0.05))
            app.bind(f"<{mod}-Key-m>", lambda e: app._on_radio_mute_clicked())
            app.bind(f"<{mod}-Key-M>", lambda e: app._on_radio_mute_clicked())

        # Global Spacebar playback toggle (when not typing in an entry or text editing widget)
        def on_space_pressed(event):
            # Check if user is actively focused in a text or entry widget
            try:
                focused = app.focus_get()
                if focused:
                    widget_class = focused.winfo_class() if hasattr(focused, "winfo_class") else ""
                    if (
                        widget_class in ("Entry", "Text", "TEntry")
                        or isinstance(focused, (ctk.CTkEntry, ctk.CTkTextbox))
                        or any(t in widget_class.lower() for t in ("entry", "text"))
                    ):
                        return  # Let normal typing of spaces work
            except Exception:
                pass

            if getattr(getattr(app, "recorder", None), "is_recording", False):
                return

            if hasattr(app, "radio_controller"):
                # If radio UI is visible or radio is playing/paused, toggle playback
                if app.radio_toggle.get() == 1 or app.radio_controller.is_playing:
                    app._on_radio_play_pause_clicked()
                    return "break"

        app._on_space_pressed_handler = on_space_pressed
        app.bind("<space>", on_space_pressed)

        # Standard Media Keys (Play/Pause, Next, Prev, Stop on multimedia keyboards)
        app.bind("<XF86AudioPlay>", lambda e: app._on_radio_play_pause_clicked())
        app.bind("<XF86AudioPause>", lambda e: app._on_radio_play_pause_clicked())
        app.bind("<XF86AudioNext>", lambda e: app._on_radio_next_clicked())
        app.bind("<XF86AudioPrev>", lambda e: app._on_radio_prev_clicked())
        app.bind("<XF86AudioStop>", lambda e: app.radio_controller.stop() if hasattr(app, "radio_controller") else None)
