"""
macOS Sonoma-style High-Contrast Segmented Button Component
"""

from __future__ import annotations

import customtkinter as ctk
from faery_app.constants import FAERY_SECONDARY_TEXT


class FaerySegmentedButton(ctk.CTkSegmentedButton):
    """
    Apple macOS Sonoma-style Segmented Control:
    - Selected segment displays crisp cream/white text on the primary purple pill.
    - Unselected segments display high-contrast deep violet text (Light Mode) or luminous lavender (Dark Mode).
    """

    def __init__(self, *args, **kwargs):
        self._selected_text_color = kwargs.pop("selected_text_color", ("#FCF4ED", "#FCF4ED"))
        self._unselected_text_color = kwargs.pop("unselected_text_color", FAERY_SECONDARY_TEXT)
        super().__init__(*args, **kwargs)
        self._apply_segment_text_contrast()

    def _create_buttons_from_values(self):
        super()._create_buttons_from_values()
        self._apply_segment_text_contrast()

    def _select_button_by_value(self, value: str):
        super()._select_button_by_value(value)
        if hasattr(self, "_buttons_dict") and value in self._buttons_dict:
            self._buttons_dict[value].configure(text_color=self._selected_text_color)

    def _unselect_button_by_value(self, value: str):
        super()._unselect_button_by_value(value)
        if hasattr(self, "_buttons_dict") and value in self._buttons_dict:
            self._buttons_dict[value].configure(text_color=self._unselected_text_color)

    def _apply_segment_text_contrast(self):
        if not hasattr(self, "_buttons_dict"):
            return
        for val, btn in self._buttons_dict.items():
            if val == self._current_value:
                btn.configure(text_color=self._selected_text_color)
            else:
                btn.configure(text_color=self._unselected_text_color)

    def set(self, value: str, from_variable_callback: bool = False, from_button_callback: bool = False):
        super().set(value, from_variable_callback=from_variable_callback, from_button_callback=from_button_callback)
        self._apply_segment_text_contrast()
