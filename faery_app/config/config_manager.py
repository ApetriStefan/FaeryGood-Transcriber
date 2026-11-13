"""
Configuration Persistence Manager for Faery Good Transcriber
"""

from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import threading
from pathlib import Path

from faery_app.constants import (
    CONFIG_PATH,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_MODEL_DISPLAY,
    DEFAULT_COOKIE_BROWSER,
    COOKIE_BROWSER_OPTIONS,
    MODEL_DISPLAY_NAMES,
)

DEFAULT_CONFIG = {
    "output_directory": str(DEFAULT_OUTPUT_DIR),
    "model_selection": DEFAULT_MODEL_DISPLAY,
    "appearance_mode": "Light",
    "last_media_directory": "",
    "cookie_browser": DEFAULT_COOKIE_BROWSER,
    "last_update_check": 0.0,
    "radio_enabled": False,
    "radio_volume": 0.7,
    "model_rtf": {"large-v3-turbo": 0.48, "small.en": 0.35, "base.en": 0.15},
}


class ConfigManager:
    """Manages application settings stored in ~/.faery_transcriber_config.json."""

    def __init__(self, config_path: Path = CONFIG_PATH):
        self.config_path = config_path
        self._lock = threading.RLock()
        self.data = copy.deepcopy(DEFAULT_CONFIG)
        self.load()

    def load(self) -> None:
        """Loads configuration from disk, creating defaults if missing or corrupted."""
        with self._lock:
            if self.config_path.exists():
                try:
                    with open(self.config_path, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                        if isinstance(loaded, dict):
                            self.data.update(loaded)
                except Exception as err:
                    print(f"[Warning] Failed to read config file, restoring defaults: {err}", file=sys.stderr)

            # Ensure model_rtf structure exists with defaults
            if not isinstance(self.data.get("model_rtf"), dict):
                self.data["model_rtf"] = copy.deepcopy(DEFAULT_CONFIG["model_rtf"])
            else:
                for k, v in DEFAULT_CONFIG["model_rtf"].items():
                    self.data["model_rtf"].setdefault(k, v)

            # Validate that the configured output directory is usable and non-empty
            raw_out = str(self.data.get("output_directory") or "").strip()
            out_dir = Path(raw_out) if raw_out else DEFAULT_OUTPUT_DIR
            try:
                out_dir.mkdir(parents=True, exist_ok=True)
                self.data["output_directory"] = str(out_dir)
            except Exception:
                self.data["output_directory"] = str(DEFAULT_OUTPUT_DIR)
                DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def save(self) -> None:
        """Atomically persists current configuration to disk."""
        with self._lock:
            tmp_path: str | None = None
            try:
                self.config_path.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=str(self.config_path.parent),
                    prefix=".faery_cfg_",
                    suffix=".tmp",
                    delete=False,
                ) as tf:
                    tmp_path = tf.name
                    json.dump(self.data, tf, indent=2)
                    tf.flush()
                    os.fsync(tf.fileno())
                os.replace(tmp_path, self.config_path)
            except Exception as err:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass
                print(f"[Warning] Failed to write config file: {err}", file=sys.stderr)

    @property
    def output_directory(self) -> Path:
        with self._lock:
            raw_out = str(self.data.get("output_directory") or "").strip()
            return Path(raw_out) if raw_out else DEFAULT_OUTPUT_DIR

    @output_directory.setter
    def output_directory(self, new_dir: Path) -> None:
        with self._lock:
            raw_out = str(new_dir or "").strip()
            self.data["output_directory"] = raw_out if raw_out else str(DEFAULT_OUTPUT_DIR)
            self.save()

    @property
    def model_selection(self) -> str:
        with self._lock:
            return self.data.get("model_selection", DEFAULT_MODEL_DISPLAY)

    @model_selection.setter
    def model_selection(self, model_name: str) -> None:
        with self._lock:
            self.data["model_selection"] = model_name
            self.save()

    @property
    def appearance_mode(self) -> str:
        with self._lock:
            return self.data.get("appearance_mode", "Light")

    @appearance_mode.setter
    def appearance_mode(self, mode: str) -> None:
        with self._lock:
            self.data["appearance_mode"] = mode
            self.save()

    @property
    def cookie_browser(self) -> str:
        with self._lock:
            val = self.data.get("cookie_browser", DEFAULT_COOKIE_BROWSER)
            return val if val in COOKIE_BROWSER_OPTIONS else DEFAULT_COOKIE_BROWSER

    @cookie_browser.setter
    def cookie_browser(self, browser_label: str) -> None:
        with self._lock:
            self.data["cookie_browser"] = browser_label
            self.save()

    @property
    def last_update_check(self) -> float:
        with self._lock:
            try:
                return float(self.data.get("last_update_check", 0.0))
            except (ValueError, TypeError):
                return 0.0

    @last_update_check.setter
    def last_update_check(self, ts: float) -> None:
        with self._lock:
            self.data["last_update_check"] = float(ts)
            self.save()

    @property
    def radio_enabled(self) -> bool:
        with self._lock:
            return bool(self.data.get("radio_enabled", False))

    @radio_enabled.setter
    def radio_enabled(self, val: bool) -> None:
        with self._lock:
            self.data["radio_enabled"] = bool(val)
            self.save()

    @property
    def radio_volume(self) -> float:
        with self._lock:
            try:
                return max(0.0, min(1.0, float(self.data.get("radio_volume", 0.7))))
            except Exception:
                return 0.7

    @radio_volume.setter
    def radio_volume(self, val: float) -> None:
        with self._lock:
            self.data["radio_volume"] = max(0.0, min(1.0, float(val)))
            self.save()

    def get_initial_media_dir(self) -> Path:
        """Returns the user's previously browsed media directory or a smart OS default."""
        with self._lock:
            last_dir = self.data.get("last_media_directory")
        if last_dir and Path(last_dir).exists():
            return Path(last_dir)
        home = Path.home()
        for candidate in [home / "Movies", home / "Downloads", home / "Desktop", home / "Videos"]:
            if candidate.exists():
                return candidate
        return home

    @staticmethod
    def _canonical_model_key(model_name: str) -> str:
        """Normalizes model names and display labels to canonical identifiers."""
        if model_name in MODEL_DISPLAY_NAMES:
            return MODEL_DISPLAY_NAMES[model_name]
        name_lower = (model_name or "").lower()
        if "maximum" in name_lower or "turbo" in name_lower or "large" in name_lower:
            return "large-v3-turbo"
        if "small" in name_lower or "high accuracy" in name_lower:
            return "small.en"
        if "base" in name_lower or "standard" in name_lower or "ultra fast" in name_lower or "fast" in name_lower:
            return "base.en"
        return model_name

    def get_model_rtf(self, model_name: str) -> float:
        """
        Returns the persisted Real-Time Factor (RTF) for model_name clamped to [0.05, 3.0].
        Defaults to 0.48 for large-v3-turbo / Maximum Accuracy, 0.35 for small.en / High Accuracy,
        and 0.15 for base.en / Standard Draft / Fast.
        """
        with self._lock:
            rtf_dict = self.data.get("model_rtf")
            if not isinstance(rtf_dict, dict):
                rtf_dict = copy.deepcopy(DEFAULT_CONFIG["model_rtf"])
                self.data["model_rtf"] = rtf_dict

            canonical = self._canonical_model_key(model_name)
            val = rtf_dict.get(model_name)
            if val is None:
                val = rtf_dict.get(canonical)

            if val is None:
                name_lower = (model_name or "").lower()
                if "maximum" in name_lower or "turbo" in name_lower or "large" in name_lower:
                    val = 0.48
                elif "base" in name_lower or "standard" in name_lower or "ultra fast" in name_lower or "fast" in name_lower:
                    val = 0.15
                elif "small" in name_lower or "high accuracy" in name_lower:
                    val = 0.35
                else:
                    val = 0.48

            try:
                val = float(val)
            except (ValueError, TypeError):
                val = 0.48

            return max(0.05, min(3.0, val))

    def update_model_rtf(self, model_name: str, observed_rtf: float) -> None:
        """
        Updates the persisted Real-Time Factor (RTF) using an Exponential Moving Average (EMA):
        new_rtf = round(0.7 * current_rtf + 0.3 * observed_rtf, 3)
        Clamped to [0.05, 3.0], updates config dict, and saves.
        """
        with self._lock:
            current_rtf = self.get_model_rtf(model_name)
            new_rtf = round(0.7 * current_rtf + 0.3 * float(observed_rtf), 3)
            new_rtf = max(0.05, min(3.0, new_rtf))

            if not isinstance(self.data.get("model_rtf"), dict):
                self.data["model_rtf"] = copy.deepcopy(DEFAULT_CONFIG["model_rtf"])

            canonical = self._canonical_model_key(model_name)
            self.data["model_rtf"][canonical] = new_rtf
            if model_name != canonical:
                self.data["model_rtf"][model_name] = new_rtf
            self.save()

