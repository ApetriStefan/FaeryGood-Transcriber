"""
About Dialog for Faery Good Transcriber
"""

from __future__ import annotations

import webbrowser
import customtkinter as ctk

from faery_app.constants import (
    APP_NAME,
    APP_VERSION,
    FAERY_GOOD_SUBTITLE,
    FAERY_GOOD_TAGLINE,
    FAERY_GOOD_URL,
    FAERY_BG,
    FAERY_CREAM_CARD,
    FAERY_CARD_BORDER,
    FAERY_PURPLE,
    FAERY_PURPLE_HOVER,
    FAERY_SECONDARY_BTN,
    FAERY_SECONDARY_HOVER,
    FAERY_SECONDARY_TEXT,
    FAERY_TEXT_PRIMARY,
    FAERY_TEXT_MUTED,
)


class AboutDialog(ctk.CTkToplevel):
    """Displays bespoke Faery Good application details and credits."""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent_app = parent
        self.title(f"About {APP_NAME}")
        width, height = 510, 450
        self.geometry(f"{width}x{height}")
        self.resizable(False, False)
        self.transient(parent)
        try:
            px = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
            py = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
            self.geometry(f"{width}x{height}+{max(0, px)}+{max(0, py)}")
        except Exception:
            pass
        self.lift()
        self.focus_set()
        self.configure(fg_color=FAERY_BG)
        if hasattr(parent, "brand"):
            parent.brand.apply_window_icon(self)

        # Standard keyboard dismissal shortcuts (Escape, Cmd+W / Ctrl+W)
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Command-w>", lambda e: self.destroy())
        self.bind("<Control-w>", lambda e: self.destroy())

        content_frame = ctk.CTkFrame(
            self,
            corner_radius=16,
            fg_color=FAERY_CREAM_CARD,
            border_width=1,
            border_color=FAERY_CARD_BORDER,
        )
        content_frame.pack(fill="both", expand=True, padx=16, pady=16)

        brand_top = ctk.CTkFrame(content_frame, fg_color="transparent")
        brand_top.pack(fill="x", padx=16, pady=(14, 6))

        if hasattr(parent, "brand") and parent.brand.mascot_dialog is not None:
            m_lbl = ctk.CTkLabel(brand_top, text="", image=parent.brand.mascot_dialog)
            m_lbl.pack(side="left", padx=(0, 12))

        title_col = ctk.CTkFrame(brand_top, fg_color="transparent")
        title_col.pack(side="left", fill="x", expand=True)

        if hasattr(parent, "brand") and parent.brand.logo_dialog is not None:
            l_lbl = ctk.CTkLabel(title_col, text="", image=parent.brand.logo_dialog, anchor="w")
            l_lbl.pack(anchor="w")

        title = ctk.CTkLabel(
            title_col,
            text=f"{APP_NAME} v{APP_VERSION}",
            font=getattr(parent, "font_serif_card", ctk.CTkFont(family="Georgia", size=13, weight="bold")),
            text_color=FAERY_TEXT_PRIMARY,
            anchor="w",
        )
        title.pack(anchor="w", pady=(2, 0))

        sub = ctk.CTkLabel(
            title_col,
            text=f"{FAERY_GOOD_SUBTITLE} • “{FAERY_GOOD_TAGLINE}”",
            font=getattr(parent, "font_serif_italic", ctk.CTkFont(family="Georgia", size=12, slant="italic")),
            text_color=FAERY_TEXT_MUTED,
            anchor="w",
            wraplength=360,
            justify="left",
        )
        sub.pack(anchor="w")

        about_text = (
            "Custom-Crafted Desktop Video & Audio Transcriber for Ericka & Faery Good\n\n"
            "• Brand & Art Direction: Inspired by FaeryGood.com\n"
            "• AI Engine: faster-whisper (CTranslate2 int8 CPU, 4 threads)\n"
            "• Models: large-v3-turbo (Best Punctuation), small.en & base.en\n"
            "• Target Systems: macOS (Apple Silicon & Intel) & Windows 11\n"
            "• Audio Extraction: Bundled static FFmpeg (Zero external setup)\n"
            "• Hygiene Guarantee: 100% automatic cleanup of temporary audio files\n"
            "• Privacy: 100% offline, on-device transcription\n\n"
            "Crafted with love & whimsy for effortless reels, voice notes, and timestamped transcripts."
        )

        lbl = ctk.CTkLabel(
            content_frame,
            text=about_text,
            font=getattr(parent, "font_body", ctk.CTkFont(size=12)),
            text_color=FAERY_TEXT_PRIMARY,
            justify="left",
            wraplength=440,
        )
        lbl.pack(anchor="w", padx=18, pady=8)

        btn_row = ctk.CTkFrame(content_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(8, 14))

        web_btn = ctk.CTkButton(
            btn_row,
            text="🦋 Visit FaeryGood.com",
            height=34,
            corner_radius=17,
            font=getattr(parent, "font_body_bold", ctk.CTkFont(size=12, weight="bold")),
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
            font=getattr(parent, "font_body_bold", ctk.CTkFont(size=12, weight="bold")),
            fg_color=FAERY_PURPLE,
            hover_color=FAERY_PURPLE_HOVER,
            text_color="#FCF4ED",
            command=self.destroy,
        )
        close_btn.pack(side="right")
