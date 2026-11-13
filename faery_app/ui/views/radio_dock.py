"""
Radio Player Dock View (104.9 The Grift FM Bottom Player)
"""

from __future__ import annotations

from typing import Dict, Optional
import customtkinter as ctk

from faery_app.constants import (
    FAERY_CREAM_CARD,
    FAERY_CARD_BORDER,
    FAERY_ROSE_CARD,
    FAERY_TEXT_PRIMARY,
    FAERY_PURPLE,
    FAERY_PURPLE_HOVER,
    FAERY_TEXT_MUTED,
    FAERY_SECONDARY_BTN,
    FAERY_SECONDARY_HOVER,
    FAERY_SECONDARY_TEXT,
    FAERY_SEGMENT_TRACK,
)


class RadioPlayerDock:
    """Constructs the Apple-style ambient music and GTA radio player at the bottom of the window."""

    @staticmethod
    def build(app) -> None:
        app.grid_rowconfigure(2, weight=0)

        app.radio_player_frame = ctk.CTkFrame(
            app,
            corner_radius=16,
            fg_color=FAERY_CREAM_CARD,
            border_width=1,
            border_color=FAERY_CARD_BORDER,
            height=68,
        )
        app.radio_player_frame.grid_columnconfigure(0, weight=0)
        app.radio_player_frame.grid_columnconfigure(1, weight=1)
        app.radio_player_frame.grid_columnconfigure(2, weight=0)
        app.radio_player_frame.grid_rowconfigure(0, weight=1)

        # Left Dock: Embedded Track Album Art / Radio Icon Badge + Live Title & Station Info
        left_dock = ctk.CTkFrame(app.radio_player_frame, fg_color="transparent")
        left_dock.grid(row=0, column=0, sticky="w", padx=(14, 10), pady=8)

        app.radio_art_badge = ctk.CTkFrame(
            left_dock,
            width=44,
            height=44,
            corner_radius=10,
            fg_color=FAERY_ROSE_CARD,
            border_width=1,
            border_color=FAERY_CARD_BORDER,
        )
        app.radio_art_badge.pack(side="left", padx=(0, 10))
        app.radio_art_badge.pack_propagate(False)

        app.radio_art_lbl = ctk.CTkLabel(app.radio_art_badge, text="📻", font=ctk.CTkFont(size=20))
        app.radio_art_lbl.place(relx=0.5, rely=0.5, anchor="center")
        app._current_art_path = None
        app._art_image_cache = {}

        info_col = ctk.CTkFrame(left_dock, fg_color="transparent")
        info_col.pack(side="left", fill="y", expand=True)

        title_row = ctk.CTkFrame(info_col, fg_color="transparent")
        title_row.pack(anchor="w")

        app.radio_title_label = ctk.CTkLabel(
            title_row,
            text="Faery Good Radio",
            font=app.font_body_bold,
            text_color=FAERY_TEXT_PRIMARY,
            anchor="w",
        )
        app.radio_title_label.pack(side="left", padx=(0, 6))

        app.radio_live_badge = ctk.CTkLabel(
            title_row,
            text="ON AIR",
            font=app.font_section_caps,
            fg_color=FAERY_PURPLE,
            text_color=("#FCF4ED", "#FCF4ED"),
            corner_radius=6,
            padx=6,
            pady=1,
        )
        app.radio_live_badge.pack(side="left")

        app.radio_artist_label = ctk.CTkLabel(
            info_col,
            text="104.9 The Grift FM  ·  Ambient Apothecary Tunes",
            font=app.font_small,
            text_color=FAERY_TEXT_MUTED,
            anchor="w",
        )
        app.radio_artist_label.pack(anchor="w")

        # Center Dock: Prev / Play-Pause / Next & Sleek Timeline
        center_dock = ctk.CTkFrame(app.radio_player_frame, fg_color="transparent")
        center_dock.grid(row=0, column=1, sticky="ew", padx=10, pady=6)
        center_dock.grid_columnconfigure(0, weight=1)

        controls_row = ctk.CTkFrame(center_dock, fg_color="transparent")
        controls_row.pack(anchor="center")

        app.radio_prev_btn = ctk.CTkButton(
            controls_row,
            text="⏮",
            width=30,
            height=28,
            corner_radius=14,
            fg_color=FAERY_SECONDARY_BTN,
            hover_color=FAERY_SECONDARY_HOVER,
            text_color=FAERY_SECONDARY_TEXT,
            border_width=0,
            font=ctk.CTkFont(size=13),
            command=app._on_radio_prev_clicked,
        )
        app.radio_prev_btn.pack(side="left", padx=3)

        app.radio_play_pause_btn = ctk.CTkButton(
            controls_row,
            text="▶",
            width=36,
            height=30,
            corner_radius=15,
            fg_color=FAERY_PURPLE,
            hover_color=FAERY_PURPLE_HOVER,
            text_color=("#FCF4ED", "#FCF4ED"),
            border_width=0,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=app._on_radio_play_pause_clicked,
        )
        app.radio_play_pause_btn.pack(side="left", padx=4)

        app.radio_next_btn = ctk.CTkButton(
            controls_row,
            text="⏭",
            width=30,
            height=28,
            corner_radius=14,
            fg_color=FAERY_SECONDARY_BTN,
            hover_color=FAERY_SECONDARY_HOVER,
            text_color=FAERY_SECONDARY_TEXT,
            border_width=0,
            font=ctk.CTkFont(size=13),
            command=app._on_radio_next_clicked,
        )
        app.radio_next_btn.pack(side="left", padx=3)

        timeline_row = ctk.CTkFrame(center_dock, fg_color="transparent")
        timeline_row.pack(anchor="center", fill="x", expand=True, pady=(2, 0))

        app.radio_time_curr = ctk.CTkLabel(
            timeline_row,
            text="00:00",
            font=app.font_small,
            text_color=FAERY_TEXT_MUTED,
            width=36,
            anchor="e",
        )
        app.radio_time_curr.pack(side="left", padx=(0, 6))

        # Interactive click-to-seek progress timeline bar
        app.radio_progress = ctk.CTkProgressBar(
            timeline_row,
            height=7,
            corner_radius=3.5,
            fg_color=FAERY_SEGMENT_TRACK,
            progress_color=FAERY_PURPLE,
            cursor="hand2",
        )
        app.radio_progress.pack(side="left", fill="x", expand=True)
        app.radio_progress.set(0.0)
        app.radio_progress.bind("<Button-1>", app._on_timeline_clicked)
        app.radio_progress.bind("<B1-Motion>", app._on_timeline_clicked)

        app.radio_time_total = ctk.CTkLabel(
            timeline_row,
            text="--:--",
            font=app.font_small,
            text_color=FAERY_TEXT_MUTED,
            width=36,
            anchor="w",
        )
        app.radio_time_total.pack(side="left", padx=(6, 0))

        # Right Dock: Mute Icon + Volume Slider + Close '✕' Button
        right_dock = ctk.CTkFrame(app.radio_player_frame, fg_color="transparent")
        right_dock.grid(row=0, column=2, sticky="e", padx=(10, 14), pady=8)

        app.radio_mute_btn = ctk.CTkButton(
            right_dock,
            text="🔊",
            width=28,
            height=28,
            corner_radius=14,
            fg_color="transparent",
            hover_color=FAERY_SECONDARY_HOVER,
            text_color=FAERY_SECONDARY_TEXT,
            border_width=0,
            font=ctk.CTkFont(size=13),
            command=app._on_radio_mute_clicked,
        )
        app.radio_mute_btn.pack(side="left", padx=(0, 2))

        app.radio_volume_slider = ctk.CTkSlider(
            right_dock,
            width=76,
            height=14,
            from_=0.0,
            to=1.0,
            number_of_steps=100,
            progress_color=FAERY_PURPLE,
            button_color=FAERY_PURPLE,
            button_hover_color=FAERY_PURPLE_HOVER,
            fg_color=FAERY_SEGMENT_TRACK,
            command=app._on_radio_volume_changed,
        )
        app.radio_volume_slider.set(app.radio_controller.volume)
        app.radio_volume_slider.pack(side="left", padx=(0, 8))

        app.radio_close_btn = ctk.CTkButton(
            right_dock,
            text="✕",
            width=26,
            height=26,
            corner_radius=13,
            fg_color=FAERY_SECONDARY_BTN,
            hover_color=FAERY_SECONDARY_HOVER,
            text_color=FAERY_SECONDARY_TEXT,
            border_width=0,
            font=app.font_small,
            command=app._close_radio_player,
        )
        app.radio_close_btn.pack(side="left")

        # The radio/music player UI should be off and hidden by default when opening the app.
        app.radio_toggle.deselect()
        app.radio_player_frame.grid_forget()
