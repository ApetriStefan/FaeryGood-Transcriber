"""
Brand Assets & Visual Identity Loader for Faery Good Transcriber
"""

from __future__ import annotations

import sys
from pathlib import Path
import tkinter as tk
from typing import Optional

import customtkinter as ctk

from faery_app.constants import get_assets_dir


class BrandAssets:
    """Loads and caches official Faery Good (faerygood.com) artwork, wordmark logos, and icons."""

    def __init__(self):
        self.assets_dir = get_assets_dir()
        self.mascot_header: Optional[ctk.CTkImage] = None
        self.mascot_dialog: Optional[ctk.CTkImage] = None
        self.logo_header: Optional[ctk.CTkImage] = None
        self.logo_dialog: Optional[ctk.CTkImage] = None
        self.icon_butterfly: Optional[ctk.CTkImage] = None
        self.icon_mortar: Optional[ctk.CTkImage] = None
        self.icon_sprig: Optional[ctk.CTkImage] = None
        self._load_all()

    def _load_all(self) -> None:
        try:
            from PIL import Image

            mascot_p = self.assets_dir / "faery_mascot.png"
            if mascot_p.exists():
                m_img = Image.open(mascot_p)
                self.mascot_header = ctk.CTkImage(light_image=m_img, dark_image=m_img, size=(38, 43))
                self.mascot_dialog = ctk.CTkImage(light_image=m_img, dark_image=m_img, size=(58, 65))

            logo_l = self.assets_dir / "faery_logo_light.png"
            logo_d = self.assets_dir / "faery_logo_dark.png"
            if logo_l.exists():
                l_img = Image.open(logo_l)
                d_img = Image.open(logo_d) if logo_d.exists() else l_img
                self.logo_header = ctk.CTkImage(light_image=l_img, dark_image=d_img, size=(138, 40))
                self.logo_dialog = ctk.CTkImage(light_image=l_img, dark_image=d_img, size=(138, 40))

            bf_l = self.assets_dir / "faery_butterfly_light.png"
            bf_d = self.assets_dir / "faery_butterfly_dark.png"
            if bf_l.exists():
                bf_img_l = Image.open(bf_l).convert("RGBA")
                bf_img_d = Image.open(bf_d).convert("RGBA") if bf_d.exists() else bf_img_l
                self.icon_butterfly = ctk.CTkImage(
                    light_image=bf_img_l,
                    dark_image=bf_img_d,
                    size=(20, 20),
                )

            mt_l = self.assets_dir / "faery_mortar_light.png"
            mt_d = self.assets_dir / "faery_mortar_dark.png"
            if mt_l.exists():
                mt_img_l = Image.open(mt_l).convert("RGBA")
                mt_img_d = Image.open(mt_d).convert("RGBA") if mt_d.exists() else mt_img_l
                self.icon_mortar = ctk.CTkImage(
                    light_image=mt_img_l,
                    dark_image=mt_img_d,
                    size=(18, 18),
                )

            sp_l = self.assets_dir / "faery_sprig_light.png"
            sp_d = self.assets_dir / "faery_sprig_dark.png"
            if sp_l.exists():
                sp_img_l = Image.open(sp_l).convert("RGBA")
                sp_img_d = Image.open(sp_d).convert("RGBA") if sp_d.exists() else sp_img_l
                self.icon_sprig = ctk.CTkImage(
                    light_image=sp_img_l,
                    dark_image=sp_img_d,
                    size=(18, 18),
                )
        except Exception:
            pass

    def apply_window_icon(self, window: tk.Misc) -> None:
        """Applies the Faery Good watercolor fairy icon to the window titlebar, taskbar, and macOS Dock."""
        try:
            # Set explicit AppUserModelID on Windows so the Taskbar groups under Faery Good Transcriber
            if sys.platform == "win32":
                try:
                    import ctypes
                    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("faerygood.transcriber.studio.1.0")
                except Exception:
                    pass

            ico_path = self.assets_dir / "faery_icon.ico"
            png_path = self.assets_dir / "faery_icon.png"
            icns_path = self.assets_dir / "faery_icon.icns"

            # Apply iconphoto (for high-DPI taskbars, Linux desktops, and cross-platform Tkinter)
            if png_path.exists():
                try:
                    from PIL import Image, ImageTk
                    pil_img = Image.open(png_path).resize((256, 256), Image.Resampling.LANCZOS)
                    tk_icon = ImageTk.PhotoImage(pil_img, master=window)
                    setattr(window, "_faery_tk_icon", tk_icon)
                    window.iconphoto(True, tk_icon)
                except Exception:
                    pass

            # Apply native Windows ICO to titlebar
            if sys.platform == "win32" and ico_path.exists():
                try:
                    window.iconbitmap(default=str(ico_path))
                except Exception:
                    pass

            # Apply native macOS Dock icon
            if sys.platform == "darwin":
                try:
                    from AppKit import NSApplication, NSImage
                    ns_app = NSApplication.sharedApplication()
                    target_icon = str(icns_path if icns_path.exists() else png_path)
                    ns_img = NSImage.alloc().initByReferencingFile_(target_icon)
                    if ns_img:
                        ns_app.setApplicationIconImage_(ns_img)
                except Exception:
                    pass
        except Exception:
            pass
