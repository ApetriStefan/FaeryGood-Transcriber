"""
File Collision & Overwrite Prompt Dialog for Faery Good Transcriber
"""

from __future__ import annotations

from pathlib import Path
from tkinter import messagebox
from typing import Optional


class OverwritePromptDialog:
    """Prompts the user when transcribing a clip whose output files already exist."""

    @staticmethod
    def prompt(base_stem: str, existing_file: Path) -> Optional[bool]:
        """Displays a Yes/No/Cancel dialog asking whether to overwrite or create a numbered copy."""
        return messagebox.askyesnocancel(
            title="Transcript Already Exists 📄",
            message=(
                f"A transcript for '{base_stem}' already exists in your output folder:\n\n"
                f"• {existing_file.name}\n\n"
                "How would you like to save this new transcript?\n\n"
                "• Click 'Yes' to replace the existing file.\n"
                f"• Click 'No' to keep both and save as a new numbered copy (e.g. '{base_stem}_1').\n"
                "• Click 'Cancel' to stop without making changes."
            ),
        )
