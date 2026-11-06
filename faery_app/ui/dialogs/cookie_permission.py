"""
Browser Cookie Permission Dialog for Faery Good Transcriber
"""

from __future__ import annotations

from tkinter import messagebox


class CookiePermissionDialog:
    """Prompts the user before reading browser cookies when a clip is behind a login wall in Auto mode."""

    @staticmethod
    def prompt(platform: str) -> bool:
        """Displays a Yes/No dialog asking permission to read browser cookies for a login-gated clip."""
        return bool(
            messagebox.askyesno(
                title=f"{platform} Sign-In Required 🔐",
                message=(
                    f"{platform} requires a signed-in session to access this clip.\n\n"
                    "Would you like to allow Faery Good Transcriber to read your web browser's "
                    f"cookies to download the temporary audio for this {platform} clip?\n\n"
                    "• Click 'Yes' to allow browser cookie access for this clip.\n"
                    "• Click 'No' to cancel without reading browser cookies."
                ),
            )
        )
