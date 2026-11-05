"""
Creator Quick Start Guide Dialog for Faery Good Transcriber
"""

from __future__ import annotations

import customtkinter as ctk

from faery_app.constants import (
    FAERY_BG,
    FAERY_CREAM_CARD,
    FAERY_CARD_BORDER,
    FAERY_ROSE_CARD,
    FAERY_PURPLE,
    FAERY_PURPLE_HOVER,
    FAERY_TEXT_PRIMARY,
    FAERY_TEXT_MUTED,
    FAERY_GOOD_TAGLINE,
)


class QuickGuideDialog(ctk.CTkToplevel):
    """Displays an accessible, Faery Good styled walkthrough for Ericka."""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent_app = parent
        self.title("Faery Good — Creator Quick Start Guide")
        self.geometry("580x560")
        self.resizable(False, False)
        self.attributes("-topmost", True)
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

        header_row = ctk.CTkFrame(content_frame, fg_color="transparent")
        header_row.pack(fill="x", padx=16, pady=(14, 8))

        if hasattr(parent, "brand") and parent.brand.mascot_dialog is not None:
            m_lbl = ctk.CTkLabel(header_row, text="", image=parent.brand.mascot_dialog)
            m_lbl.pack(side="left", padx=(0, 12))

        title_stack = ctk.CTkFrame(header_row, fg_color="transparent")
        title_stack.pack(side="left", fill="x", expand=True)

        title = ctk.CTkLabel(
            title_stack,
            text="✨ Faery Good Creator Guide",
            font=getattr(parent, "font_serif_title", ctk.CTkFont(family="Georgia", size=17, weight="bold")),
            text_color=FAERY_TEXT_PRIMARY,
            anchor="w",
        )
        title.pack(anchor="w")

        sub = ctk.CTkLabel(
            title_stack,
            text=f"“{FAERY_GOOD_TAGLINE}” — Effortless Instagram Reels & YouTube Transcripts",
            font=getattr(parent, "font_serif_italic", ctk.CTkFont(family="Georgia", size=12, slant="italic")),
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
            "4. 100% PRIVATE & ON-DEVICE\n"
            "   All transcription runs 100% privately on your computer. Downloaded and converted "
            "audio files are strictly temporary and cleaned up automatically immediately after transcription.\n\n"
            "5. SOCIAL LOGIN (FOR INSTAGRAM & FACEBOOK)\n"
            "   Most links transcribe automatically! If an Instagram or Facebook clip requires sign-in, "
            "simply select your browser in '🔐 Social Login' under Studio Preferences.\n\n"
            "6. HISTORY LIBRARY (⌘2 / Ctrl+2)\n"
            "   Every transcript is saved to your output folder. Search, rename, edit, and "
            "export any past transcript in the History tab!"
        )

        tb = ctk.CTkTextbox(
            content_frame,
            wrap="word",
            font=getattr(parent, "font_body", ctk.CTkFont(size=12)),
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
            font=getattr(parent, "font_body_bold", ctk.CTkFont(size=12, weight="bold")),
            fg_color=FAERY_PURPLE,
            hover_color=FAERY_PURPLE_HOVER,
            text_color="#FCF4ED",
            command=self.destroy,
        )
        close_btn.pack(anchor="e", padx=16, pady=(0, 14))
