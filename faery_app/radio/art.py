"""
Embedded Album Art Extraction for Faery Good Radio
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional, Tuple

import customtkinter as ctk


def extract_embedded_art(audio_path: Optional[Path], target_size: Tuple[int, int] = (44, 44)) -> Optional[ctk.CTkImage]:
    """Extracts embedded ID3 / APIC album artwork from an audio file and returns a CTkImage."""
    if not audio_path or not audio_path.exists():
        return None
    try:
        from PIL import Image
        with open(audio_path, "rb") as f:
            data = f.read(5 * 1024 * 1024)  # Read up to 5MB to inspect ID3 header

        apic_idx = data.find(b"APIC")
        sub = data[apic_idx : apic_idx + 2 * 1024 * 1024] if apic_idx != -1 else data[: 2 * 1024 * 1024]

        # Look for JPEG SOI (\xff\xd8\xff) or PNG header (\x89PNG\r\n\x1a\n)
        jpg_idx = sub.find(b"\xff\xd8\xff")
        png_idx = sub.find(b"\x89PNG\r\n\x1a\n")

        img_bytes: Optional[bytes] = None
        if jpg_idx != -1 and (png_idx == -1 or jpg_idx < png_idx):
            end_idx = sub.find(b"\xff\xd9", jpg_idx)
            img_bytes = sub[jpg_idx : end_idx + 2] if end_idx != -1 else sub[jpg_idx:]
        elif png_idx != -1:
            end_idx = sub.find(b"IEND\xaeB`\x82", png_idx)
            img_bytes = sub[png_idx : end_idx + 8] if end_idx != -1 else sub[png_idx:]

        if img_bytes:
            pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
            return ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=target_size)
    except Exception:
        pass
    return None
