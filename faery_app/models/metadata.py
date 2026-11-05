"""
Domain Data Models & Metadata for Faery Good Transcriber
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class MediaMetadata:
    """Represents probed metadata for a selected media file."""
    path: Path
    file_size_bytes: int
    duration_seconds: float
    has_audio: bool
    format_name: str

    @property
    def formatted_duration(self) -> str:
        """Returns human-readable duration (MM:SS or HH:MM:SS)."""
        total = int(self.duration_seconds)
        hours = total // 3600
        minutes = (total % 3600) // 60
        secs = total % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    @property
    def formatted_size(self) -> str:
        """Returns human-readable file size."""
        size_mb = self.file_size_bytes / (1024 * 1024)
        if size_mb >= 1000:
            return f"{size_mb / 1024:.2f} GB"
        return f"{size_mb:.1f} MB"


@dataclass
class TranscriptSegment:
    """Represents a single timestamped transcription segment."""
    start: float
    end: float
    text: str

    @property
    def formatted_timestamp(self) -> str:
        total = int(self.start)
        hours = total // 3600
        minutes = (total % 3600) // 60
        secs = total % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"


@dataclass
class OnlineClipInfo:
    """Represents metadata and temporary local audio path for a downloaded online clip."""
    url: str
    platform: str
    title: str
    sanitized_title: str
    video_id: str
    duration_seconds: float
    temp_media_path: Path


def format_seconds_mm_ss(seconds: float) -> str:
    """Formats duration in seconds as MM:SS (or HH:MM:SS if >= 1 hour)."""
    total = max(0, int(seconds))
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"
