"""
History Library Tab View (Apple Split-View Sidebar + Reader Canvas)
"""

from __future__ import annotations

import customtkinter as ctk

from faery_app.constants import (
    FAERY_CREAM_CARD,
    FAERY_CARD_BORDER,
    FAERY_LAVENDER_BG,
    FAERY_DIVIDER,
    FAERY_SEGMENT_HOVER,
    FAERY_TEXT_MUTED,
    FAERY_TEXT_PRIMARY,
    FAERY_SECONDARY_BTN,
    FAERY_SECONDARY_HOVER,
    FAERY_SECONDARY_TEXT,
    FAERY_SECONDARY_DISABLED_TEXT,
    FAERY_SEGMENT_TRACK,
    FAERY_PURPLE,
    FAERY_PURPLE_HOVER,
    FAERY_BERRY_RED,
    FAERY_BERRY_HOVER,
    FAERY_BERRY_TEXT,
)
from faery_app.ui.components.segmented_button import FaerySegmentedButton


class HistoryLibraryView:
    """Builds the History Library UI components and layout."""

    @staticmethod
    def build(app) -> None:
        tab = app.tab_history
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

        app.history_search_entry = ctk.CTkEntry(
            search_box_frame,
            placeholder_text="🔍 Search transcripts & spoken content…",
            height=34,
            corner_radius=17,
            border_width=1,
            border_color=FAERY_DIVIDER,
            fg_color=FAERY_LAVENDER_BG,
            text_color=FAERY_TEXT_PRIMARY,
            font=app.font_body,
        )
        app.history_search_entry.grid(row=0, column=0, sticky="ew")

        # Apple-style Clear Button (✕) positioned on the right
        app.history_search_clear_btn = ctk.CTkButton(
            search_box_frame,
            text="✕",
            width=26,
            height=26,
            corner_radius=13,
            fg_color="transparent",
            hover_color=FAERY_SEGMENT_HOVER,
            text_color=FAERY_TEXT_MUTED,
            border_width=0,
            font=app.font_small,
            command=app._on_clear_search_clicked,
            cursor="hand2",
        )
        # Event bindings for real-time keystrokes, return, paste, and escape
        app.history_search_entry.bind("<KeyRelease>", app._on_history_search_changed)
        app.history_search_entry.bind("<Return>", app._on_history_search_enter)
        app.history_search_entry.bind("<KP_Enter>", app._on_history_search_enter)
        app.history_search_entry.bind("<Escape>", lambda e: app._on_clear_search_clicked())
        app.history_search_entry.bind("<<Paste>>", lambda e: app.after(20, app._on_history_search_changed))

        # Subheader with count & borderless refresh pill
        subhead = ctk.CTkFrame(left_panel, fg_color="transparent")
        subhead.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 6))
        subhead.grid_columnconfigure(0, weight=1)

        app.history_count_label = ctk.CTkLabel(
            subhead,
            text="0 Transcripts",
            font=app.font_section_caps,
            text_color=FAERY_TEXT_MUTED,
        )
        app.history_count_label.grid(row=0, column=0, sticky="w")

        app.history_refresh_btn = ctk.CTkButton(
            subhead,
            text="↻ Refresh",
            width=74,
            height=24,
            corner_radius=12,
            fg_color=FAERY_SECONDARY_BTN,
            hover_color=FAERY_SECONDARY_HOVER,
            text_color=FAERY_SECONDARY_TEXT,
            border_width=0,
            font=app.font_small,
            command=lambda: app._refresh_history_list(filter_text=None, resync=True),
        )
        app.history_refresh_btn.grid(row=0, column=1, sticky="e")

        # Scrollable list for records
        app.history_list_frame = ctk.CTkScrollableFrame(
            left_panel,
            corner_radius=12,
            fg_color=FAERY_LAVENDER_BG,
        )
        app.history_list_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        app.history_list_frame.grid_columnconfigure(0, weight=1)

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
        app.history_detail_header = ctk.CTkFrame(right_panel, fg_color="transparent")
        app.history_detail_header.grid(row=0, column=0, sticky="ew", padx=20, pady=(14, 6))
        app.history_detail_header.grid_columnconfigure(0, weight=1)

        app.history_title_label = ctk.CTkLabel(
            app.history_detail_header,
            text="✨ Select a transcript from your library",
            font=app.font_serif_title,
            text_color=FAERY_TEXT_PRIMARY,
            anchor="w",
        )
        app.history_title_label.grid(row=0, column=0, sticky="w")

        app.history_meta_label = ctk.CTkLabel(
            app.history_detail_header,
            text="Choose any archived Faery Good transcript to view, edit, rename, or export.",
            font=app.font_small,
            text_color=FAERY_TEXT_MUTED,
            anchor="w",
        )
        app.history_meta_label.grid(row=1, column=0, sticky="w", pady=(2, 0))

        # Action Toolbar (CRUD Operations)
        crud_toolbar = ctk.CTkFrame(right_panel, fg_color="transparent")
        crud_toolbar.grid(row=1, column=0, sticky="ew", padx=20, pady=(4, 10))
        crud_toolbar.grid_columnconfigure(1, weight=1)

        left_crud = ctk.CTkFrame(crud_toolbar, fg_color="transparent")
        left_crud.grid(row=0, column=0, sticky="w")

        app.history_view_selector = FaerySegmentedButton(
            left_crud,
            values=["📄 Clean Paragraphs", "⏱️ Timecoded", "📝 Markdown"],
            command=app._on_history_view_mode_changed,
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
        app.history_view_selector.set("📄 Clean Paragraphs")
        app.history_view_selector.pack(side="left", padx=(0, 10))

        right_crud = ctk.CTkFrame(crud_toolbar, fg_color="transparent")
        right_crud.grid(row=0, column=1, sticky="e")

        app.h_rename_btn = ctk.CTkButton(
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
            font=app.font_body_bold,
            command=app._on_history_rename_clicked,
            state="disabled",
        )
        app.h_rename_btn.pack(side="left", padx=(0, 6))

        app.h_save_btn = ctk.CTkButton(
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
            font=app.font_body_bold,
            command=app._on_history_save_edits_clicked,
            state="disabled",
        )
        app.h_save_btn.pack(side="left", padx=(0, 6))

        app.h_copy_btn = ctk.CTkButton(
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
            font=app.font_body_bold,
            command=app._on_history_copy_clicked,
            state="disabled",
        )
        app.h_copy_btn.pack(side="left", padx=(0, 6))

        app.h_open_file_btn = ctk.CTkButton(
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
            font=app.font_body_bold,
            command=app._on_history_open_file_clicked,
            state="disabled",
        )
        app.h_open_file_btn.pack(side="left", padx=(0, 6))

        app.h_delete_btn = ctk.CTkButton(
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
            font=app.font_body_bold,
            command=app._on_history_delete_clicked,
            state="disabled",
        )
        app.h_delete_btn.pack(side="left")

        h_divider = ctk.CTkFrame(right_panel, height=1, fg_color=FAERY_DIVIDER)
        h_divider.grid(row=2, column=0, sticky="ew", padx=20)

        # Preview & Edit Textbox (Borderless Apple Document Canvas)
        app.history_textbox = ctk.CTkTextbox(
            right_panel,
            wrap="word",
            font=app.font_editor,
            corner_radius=12,
            border_width=0,
            fg_color=FAERY_CREAM_CARD,
            text_color=FAERY_TEXT_PRIMARY,
        )
        app.history_textbox.grid(row=3, column=0, sticky="nsew", padx=16, pady=(6, 14))
