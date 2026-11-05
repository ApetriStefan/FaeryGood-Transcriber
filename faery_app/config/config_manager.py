"""
Configuration Persistence Manager for Faery Good Transcriber
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from faery_app.constants import (
    CONFIG_PATH,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_MODEL_DISPLAY,
    DEFAULT_COOKIE_BROWSER,
    COOKIE_BROWSER_OPTIONS,
)


class ConfigManager:
    """Manages application settings stored in ~/.faery_transcriber_config.json."""

    def __init__(self, config_path: Path = CONFIG_PATH):
        self.config_path = config_path
        self.data = {
            "output_directory": str(DEFAULT_OUTPUT_DIR),
            "model_selection": DEFAULT_MODEL_DISPLAY,
            "appearance_mode": "Light",
            "last_media_directory": "",
            "cookie_browser": DEFAULT_COOKIE_BROWSER,
            "last_update_check": 0.0,
            "radio_enabled": False,
            "radio_volume": 0.7,
        }
        self.load()

    def load(self) -> None:
        """Loads configuration from disk, creating defaults if missing or corrupted."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        self.data.update(loaded)
            except Exception as err:
                print(f"[Warning] Failed to read config file, restoring defaults: {err}", file=sys.stderr)

        # Validate that the configured output directory is usable
        out_dir = Path(self.data.get("output_directory", str(DEFAULT_OUTPUT_DIR)))
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            self.data["output_directory"] = str(DEFAULT_OUTPUT_DIR)
            DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def save(self) -> None:
        """Persists current configuration to disk."""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception as err:
            print(f"[Warning] Failed to write config file: {err}", file=sys.stderr)

    @property
    def output_directory(self) -> Path:
        return Path(self.data["output_directory"])

    @output_directory.setter
    def output_directory(self, new_dir: Path) -> None:
        self.data["output_directory"] = str(new_dir)
        self.save()

    @property
    def model_selection(self) -> str:
        return self.data.get("model_selection", DEFAULT_MODEL_DISPLAY)

    @model_selection.setter
    def model_selection(self, model_name: str) -> None:
        self.data["model_selection"] = model_name
        self.save()

    @property
    def appearance_mode(self) -> str:
        return self.data.get("appearance_mode", "Light")

    @appearance_mode.setter
    def appearance_mode(self, mode: str) -> None:
        self.data["appearance_mode"] = mode
        self.save()

    @property
    def cookie_browser(self) -> str:
        val = self.data.get("cookie_browser", DEFAULT_COOKIE_BROWSER)
        return val if val in COOKIE_BROWSER_OPTIONS else DEFAULT_COOKIE_BROWSER

    @cookie_browser.setter
    def cookie_browser(self, browser_label: str) -> None:
        self.data["cookie_browser"] = browser_label
        self.save()

    @property
    def last_update_check(self) -> float:
        try:
            return float(self.data.get("last_update_check", 0.0))
        except (ValueError, TypeError):
            return 0.0

    @last_update_check.setter
    def last_update_check(self, ts: float) -> None:
        self.data["last_update_check"] = float(ts)
        self.save()

    @property
    def radio_enabled(self) -> bool:
        return bool(self.data.get("radio_enabled", False))

    @radio_enabled.setter
    def radio_enabled(self, val: bool) -> None:
        self.data["radio_enabled"] = bool(val)
        self.save()

    @property
    def radio_volume(self) -> float:
        try:
            return max(0.0, min(1.0, float(self.data.get("radio_volume", 0.7))))
        except Exception:
            return 0.7

    @radio_volume.setter
    def radio_volume(self, val: float) -> None:
        self.data["radio_volume"] = max(0.0, min(1.0, float(val)))
        self.save()

    def get_initial_media_dir(self) -> Path:
        """Returns the user's previously browsed media directory or a smart OS default."""
        last_dir = self.data.get("last_media_directory")
        if last_dir and Path(last_dir).exists():
            return Path(last_dir)
        home = Path.home()
        for candidate in [home / "Movies", home / "Downloads", home / "Desktop", home / "Videos"]:
            if candidate.exists():
                return candidate
        return home
