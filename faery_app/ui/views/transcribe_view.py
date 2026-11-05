"""
Transcribe Studio Tab View (Bento Inspector + Document Canvas)
"""

from __future__ import annotations

import customtkinter as ctk

from faery_app.constants import (
    FAERY_CREAM_CARD,
    FAERY_CARD_BORDER,
    FAERY_PURPLE,
    FAERY_PURPLE_HOVER,
    FAERY_TEXT_PRIMARY,
    FAERY_TEXT_MUTED,
    FAERY_DIVIDER,
    FAERY_LAVENDER_BG,
    FAERY_SECONDARY_BTN,
    FAERY_SECONDARY_HOVER,
    FAERY_SECONDARY_TEXT,
    FAERY_SECONDARY_DISABLED_TEXT,
    FAERY_ROSE_CARD,
    FAERY_SEGMENT_TRACK,
    FAERY_SEGMENT_HOVER,
    MODEL_DISPLAY_NAMES,
    COOKIE_BROWSER_OPTIONS,
)
from faery_app.ui.components.segmented_button import FaerySegmentedButton


class TranscribeStudioView:
    """Builds the Transcribe Studio UI components and layout."""

    @staticmethod
    def build(app) -> None:
        tab = app.tab_transcribe
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
            text="  SOURCE MEDIA" if app.brand.icon_butterfly else "🦋 SOURCE MEDIA",
            image=app.brand.icon_butterfly,
            compound="left",
            font=app.font_section_caps,
            text_color=FAERY_TEXT_MUTED,
            anchor="w",
        )
        source_badge.grid(row=0, column=0, sticky="w")

        app.select_file_btn = ctk.CTkButton(
            file_top_bar,
            text="📁 Select Local File…",
            font=app.font_body_bold,
            fg_color=FAERY_PURPLE,
            hover_color=FAERY_PURPLE_HOVER,
            text_color=("#FCF4ED", "#FCF4ED"),
            text_color_disabled=("#E8DCF7", "#D4C2EB"),
            corner_radius=14,
            command=app._on_select_file_clicked,
            width=158,
            height=28,
        )
        app.select_file_btn.grid(row=0, column=1, sticky="e")

        app.file_name_label = ctk.CTkLabel(
            file_card,
            text="No clip or link selected yet",
            font=app.font_serif_card,
            text_color=FAERY_TEXT_PRIMARY,
            anchor="w",
        )
        app.file_name_label.grid(row=1, column=0, sticky="ew", padx=16, pady=(1, 0))

        app.file_meta_label = ctk.CTkLabel(
            file_card,
            text="Select a local file or paste an Instagram, YouTube, TikTok, or Facebook link below",
            font=app.font_small,
            text_color=FAERY_TEXT_MUTED,
            anchor="w",
        )
        app.file_meta_label.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 6))

        # Online Link Input Row (Instagram / YouTube / TikTok / Facebook)
        url_bar_frame = ctk.CTkFrame(file_card, fg_color="transparent")
        url_bar_frame.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 11))
        url_bar_frame.grid_columnconfigure(0, weight=1)

        app.url_entry = ctk.CTkEntry(
            url_bar_frame,
            placeholder_text="🔗 Paste Instagram, YouTube, TikTok, or Facebook link…",
            height=28,
            corner_radius=10,
            border_width=1,
            border_color=FAERY_DIVIDER,
            fg_color=FAERY_LAVENDER_BG,
            text_color=FAERY_TEXT_PRIMARY,
            font=app.font_small,
        )
        app.url_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        app.url_entry.bind("<KeyRelease>", app._on_url_entry_changed)
        app.url_entry.bind("<Return>", lambda e: app._on_generate_clicked())

        app.paste_url_btn = ctk.CTkButton(
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
            font=app.font_body_bold,
            command=app._on_paste_url_clicked,
        )
        app.paste_url_btn.grid(row=0, column=1, sticky="e")

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
            text="  Transcription Engine" if app.brand.icon_mortar else "🌿 Transcription Engine",
            image=app.brand.icon_mortar,
            compound="left",
            font=app.font_body_bold,
            text_color=FAERY_TEXT_PRIMARY,
        )
        model_label.grid(row=0, column=0, padx=(16, 12), pady=(10, 6), sticky="w")

        app.model_dropdown = ctk.CTkOptionMenu(
            settings_card,
            values=list(MODEL_DISPLAY_NAMES.keys()),
            command=app._on_model_changed,
            height=26,
            width=255,
            corner_radius=13,
            font=app.font_small,
            fg_color=FAERY_SECONDARY_BTN,
            button_color=FAERY_SECONDARY_HOVER,
            button_hover_color=FAERY_CARD_BORDER,
            text_color=FAERY_SECONDARY_TEXT,
        )
        app.model_dropdown.set(app.config.model_selection)
        app.model_dropdown.grid(row=0, column=1, padx=(0, 16), pady=(10, 6), sticky="e")

        # 1px Apple Settings Divider
        divider = ctk.CTkFrame(settings_card, height=1, fg_color=FAERY_DIVIDER)
        divider.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16)

        # Row 2: Output Folder
        out_label = ctk.CTkLabel(
            settings_card,
            text="  Output Folder" if app.brand.icon_sprig else "🌸 Output Folder",
            image=app.brand.icon_sprig,
            compound="left",
            font=app.font_body_bold,
            text_color=FAERY_TEXT_PRIMARY,
        )
        out_label.grid(row=2, column=0, padx=(16, 12), pady=(6, 6), sticky="w")

        out_path_subframe = ctk.CTkFrame(settings_card, fg_color="transparent")
        out_path_subframe.grid(row=2, column=1, padx=(0, 16), pady=(6, 6), sticky="ew")
        out_path_subframe.grid_columnconfigure(0, weight=1)

        app.out_path_entry = ctk.CTkEntry(
            out_path_subframe,
            height=26,
            corner_radius=10,
            border_width=1,
            border_color=FAERY_DIVIDER,
            fg_color=FAERY_LAVENDER_BG,
            text_color=FAERY_TEXT_PRIMARY,
            font=app.font_small,
        )
        app.out_path_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        app.out_path_entry.configure(state="readonly")

        app.change_folder_btn = ctk.CTkButton(
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
            font=app.font_body_bold,
            command=app._on_change_folder_clicked,
        )
        app.change_folder_btn.grid(row=0, column=1, sticky="e")

        # 1px Apple Settings Divider
        divider2 = ctk.CTkFrame(settings_card, height=1, fg_color=FAERY_DIVIDER)
        divider2.grid(row=3, column=0, columnspan=2, sticky="ew", padx=16)

        # Row 4: Social Login (Browser Cookies for Instagram/Facebook Reels)
        cookie_label = ctk.CTkLabel(
            settings_card,
            text="  Social Login" if app.brand.icon_butterfly else "🔐 Social Login",
            image=app.brand.icon_butterfly,
            compound="left",
            font=app.font_body_bold,
            text_color=FAERY_TEXT_PRIMARY,
        )
        cookie_label.grid(row=4, column=0, padx=(16, 12), pady=(6, 10), sticky="w")

        app.cookie_dropdown = ctk.CTkOptionMenu(
            settings_card,
            values=list(COOKIE_BROWSER_OPTIONS.keys()),
            command=app._on_cookie_browser_changed,
            height=26,
            width=255,
            corner_radius=13,
            font=app.font_small,
            fg_color=FAERY_SECONDARY_BTN,
            button_color=FAERY_SECONDARY_HOVER,
            button_hover_color=FAERY_CARD_BORDER,
            text_color=FAERY_SECONDARY_TEXT,
        )
        app.cookie_dropdown.set(app.config.cookie_browser)
        app.cookie_dropdown.grid(row=4, column=1, padx=(0, 16), pady=(6, 10), sticky="e")

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
            font=app.font_serif_card,
            text_color=FAERY_TEXT_PRIMARY,
        )
        result_title.pack(side="left", padx=(0, 10))

        app.stats_badge = ctk.CTkLabel(
            title_left,
            text="0 words  |  0 characters",
            font=app.font_small,
            fg_color=FAERY_ROSE_CARD,
            text_color=FAERY_SECONDARY_TEXT,
            corner_radius=10,
            padx=10,
            pady=2,
        )
        app.stats_badge.pack(side="left")

        app.view_selector = FaerySegmentedButton(
            result_header,
            values=["📄 Clean Paragraphs", "⏱️ Timecoded (YouTube)", "📝 Raw Text"],
            command=app._on_view_mode_changed,
            height=30,
            corner_radius=15,
            font=app.font_small,
            fg_color=FAERY_SEGMENT_TRACK,
            selected_color=FAERY_PURPLE,
            selected_hover_color=FAERY_PURPLE_HOVER,
            unselected_color=FAERY_SEGMENT_TRACK,
            unselected_hover_color=FAERY_SEGMENT_HOVER,
            selected_text_color=("#FCF4ED", "#FCF4ED"),
            unselected_text_color=FAERY_SECONDARY_TEXT,
        )
        app.view_selector.set("📄 Clean Paragraphs")
        app.view_selector.grid(row=0, column=2, sticky="e")

        canvas_divider = ctk.CTkFrame(result_card, height=1, fg_color=FAERY_DIVIDER)
        canvas_divider.grid(row=1, column=0, sticky="ew", padx=18)

        app.textbox = ctk.CTkTextbox(
            result_card,
            wrap="word",
            font=app.font_editor,
            corner_radius=12,
            border_width=0,
            fg_color=FAERY_CREAM_CARD,
            text_color=FAERY_TEXT_PRIMARY,
        )
        app.textbox.grid(row=2, column=0, sticky="nsew", padx=14, pady=(6, 12))
        app.textbox.bind("<KeyRelease>", app._update_stats)

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

        app.generate_btn = ctk.CTkButton(
            left_dock,
            text="✨ Generate Transcript",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=FAERY_PURPLE,
            hover_color=FAERY_PURPLE_HOVER,
            text_color=("#FCF4ED", "#FCF4ED"),
            text_color_disabled=("#E8DCF7", "#D4C2EB"),
            corner_radius=19,
            command=app._on_generate_clicked,
            width=192,
            height=38,
        )
        app.generate_btn.pack(side="left", padx=(0, 6))

        app.cancel_btn = ctk.CTkButton(
            left_dock,
            text="Cancel",
            font=app.font_body_bold,
            fg_color=FAERY_SEGMENT_TRACK,
            hover_color=FAERY_SEGMENT_HOVER,
            text_color=FAERY_TEXT_MUTED,
            text_color_disabled=FAERY_SECONDARY_DISABLED_TEXT,
            corner_radius=19,
            command=app._on_cancel_clicked,
            width=74,
            height=38,
            state="disabled",
        )
        app.cancel_btn.pack(side="left")

        # Center Dock: Live Status & Sleek 6px Apple Progress Bar
        center_dock = ctk.CTkFrame(action_card, fg_color="transparent")
        center_dock.grid(row=0, column=1, padx=8, pady=10, sticky="ew")
        center_dock.grid_columnconfigure(0, weight=1)

        app.status_label = ctk.CTkLabel(
            center_dock,
            text="✨ Ready — Select a video or audio clip to begin.",
            font=app.font_small,
            text_color=FAERY_TEXT_MUTED,
            anchor="w",
        )
        app.status_label.grid(row=0, column=0, sticky="ew", pady=(0, 4))

        app.progress_bar = ctk.CTkProgressBar(
            center_dock,
            height=6,
            corner_radius=3,
            fg_color=FAERY_SEGMENT_TRACK,
            progress_color=FAERY_PURPLE,
        )
        app.progress_bar.grid(row=1, column=0, sticky="ew")
        app.progress_bar.set(0.0)

        # Right Dock: Borderless Apple-Tinted Export Pills
        right_dock = ctk.CTkFrame(action_card, fg_color="transparent")
        right_dock.grid(row=0, column=2, padx=(10, 14), pady=12, sticky="e")

        app.copy_btn = ctk.CTkButton(
            right_dock,
            text="📋 Copy to Clipboard",
            width=142,
            height=34,
            corner_radius=17,
            fg_color=FAERY_SECONDARY_BTN,
            hover_color=FAERY_SECONDARY_HOVER,
            text_color=FAERY_SECONDARY_TEXT,
            border_width=0,
            font=app.font_body_bold,
            command=app._on_copy_clicked,
        )
        app.copy_btn.pack(side="left", padx=(0, 6))
        app.default_btn_fg = app.copy_btn.cget("fg_color")

        app.save_txt_btn = ctk.CTkButton(
            right_dock,
            text="💾 .txt",
            width=72,
            height=34,
            corner_radius=17,
            fg_color=FAERY_SECONDARY_BTN,
            hover_color=FAERY_SECONDARY_HOVER,
            text_color=FAERY_SECONDARY_TEXT,
            border_width=0,
            font=app.font_body_bold,
            command=app._on_save_txt_clicked,
        )
        app.save_txt_btn.pack(side="left", padx=(0, 6))

        app.save_md_btn = ctk.CTkButton(
            right_dock,
            text="📝 .md",
            width=72,
            height=34,
            corner_radius=17,
            fg_color=FAERY_SECONDARY_BTN,
            hover_color=FAERY_SECONDARY_HOVER,
            text_color=FAERY_SECONDARY_TEXT,
            border_width=0,
            font=app.font_body_bold,
            command=app._on_save_md_clicked,
        )
        app.save_md_btn.pack(side="left", padx=(0, 6))

        app.open_folder_btn = ctk.CTkButton(
            right_dock,
            text="📂 Folder",
            width=88,
            height=34,
            corner_radius=17,
            fg_color=FAERY_ROSE_CARD,
            hover_color=FAERY_SECONDARY_HOVER,
            text_color=FAERY_SECONDARY_TEXT,
            border_width=0,
            font=app.font_body_bold,
            command=app._on_open_folder_clicked,
        )
        app.open_folder_btn.pack(side="left")
