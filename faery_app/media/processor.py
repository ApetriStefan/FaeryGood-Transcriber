"""
Media Inspector & Extraction Subsystem for Faery Good Transcriber
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
import time
import wave
from pathlib import Path
from typing import Optional

from faery_app.models.metadata import MediaMetadata
from faery_app.utils.system import get_verified_ffmpeg_exe


class MediaProcessor:
    """Handles audio track detection, duration probing, and 16kHz WAV extraction."""

    @staticmethod
    def _probe_wav_fast(file_path: Path, file_size: int) -> Optional[MediaMetadata]:
        """Fast-path pure-Python RIFF/WAV header inspection without spawning FFmpeg."""
        if file_path.suffix.lower() != ".wav" or file_size <= 44:
            return None
        try:
            with wave.open(str(file_path), "rb") as wf:
                channels = wf.getnchannels()
                framerate = wf.getframerate()
                nframes = wf.getnframes()
                sampwidth = wf.getsampwidth()
                if channels >= 1 and framerate > 0 and nframes > 0 and sampwidth in (1, 2, 3, 4):
                    return MediaMetadata(
                        path=file_path,
                        file_size_bytes=file_size,
                        duration_seconds=nframes / float(framerate),
                        has_audio=True,
                        format_name="wav",
                    )
        except Exception:
            return None
        return None

    @staticmethod
    def is_16k_mono_pcm_wav(file_path: Path) -> bool:
        """Returns True if file_path is already a standard 16kHz mono 16-bit uncompressed PCM WAV."""
        try:
            if not file_path.is_file() or file_path.stat().st_size <= 44:
                return False
            with wave.open(str(file_path), "rb") as wf:
                return (
                    wf.getnchannels() == 1
                    and wf.getsampwidth() == 2
                    and wf.getframerate() == 16000
                    and wf.getcomptype() == "NONE"
                    and wf.getnframes() > 0
                )
        except Exception:
            return False

    @staticmethod
    def probe_file(file_path: Path) -> MediaMetadata:
        """
        Inspects the input file using fast WAV header inspection or the bundled static FFmpeg binary.
        Raises descriptive exceptions if the file is invalid, corrupt, or lacks audio.
        """
        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(f"Selected file does not exist: {file_path}")

        file_size = file_path.stat().st_size
        if file_size == 0:
            raise ValueError("The selected file is empty (0 bytes).")

        fast_wav = MediaProcessor._probe_wav_fast(file_path, file_size)
        if fast_wav is not None:
            return fast_wav

        ffmpeg_exe = get_verified_ffmpeg_exe()
        cmd = [ffmpeg_exe, "-hide_banner", "-i", str(file_path)]

        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creation_flags,
                timeout=15,
            )
        except subprocess.TimeoutExpired:
            raise TimeoutError("Probing the media file timed out.")
        except Exception as err:
            raise RuntimeError(f"Failed to probe media file with FFmpeg: {err}")

        stderr = proc.stderr or ""

        if "Invalid data found when processing input" in stderr:
            raise ValueError(
                "The selected file is corrupted or is not a recognized media file."
            )

        # Audio stream detection
        has_audio = bool(re.search(r"Stream #\d+:\d+.*Audio:", stderr))
        if not has_audio:
            raise ValueError(
                "No audio track was detected in this file.\n\n"
                "Please select a video or audio file that contains recorded sound."
            )

        # Parse duration
        duration_sec = 0.0
        dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", stderr)
        if dur_match:
            hours = int(dur_match.group(1))
            minutes = int(dur_match.group(2))
            seconds = float(dur_match.group(3))
            duration_sec = hours * 3600 + minutes * 60 + seconds

        format_match = re.search(r"Input #0,\s*([^,]+),", stderr)
        format_name = format_match.group(1) if format_match else file_path.suffix.lstrip(".")

        return MediaMetadata(
            path=file_path,
            file_size_bytes=file_size,
            duration_seconds=duration_sec,
            has_audio=has_audio,
            format_name=format_name,
        )

    @staticmethod
    def extract_16k_mono_wav(
        input_path: Path,
        output_wav_path: Path,
        cancel_event: threading.Event,
    ) -> None:
        """
        Extracts and converts any video or audio stream into a 16kHz mono 16-bit PCM WAV.
        Bypasses FFmpeg re-encoding when the input is already a 16kHz mono 16-bit PCM WAV.
        Supports instantaneous cancellation by terminating the running FFmpeg process.
        """
        if cancel_event.is_set():
            raise InterruptedError("Audio extraction was cancelled by the user.")

        if MediaProcessor.is_16k_mono_pcm_wav(input_path):
            if input_path.resolve() != output_wav_path.resolve():
                shutil.copyfile(input_path, output_wav_path)
            return

        ffmpeg_exe = get_verified_ffmpeg_exe()
        cmd = [
            ffmpeg_exe,
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-i", str(input_path),
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            str(output_wav_path),
        ]

        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creation_flags,
        )

        stdout = ""
        stderr = ""
        while True:
            if cancel_event.is_set():
                proc.kill()
                proc.wait()
                if proc.stdout:
                    proc.stdout.close()
                if proc.stderr:
                    proc.stderr.close()
                raise InterruptedError("Audio extraction was cancelled by the user.")
            try:
                stdout, stderr = proc.communicate(timeout=0.05)
                break
            except subprocess.TimeoutExpired:
                continue

        if proc.stdout:
            proc.stdout.close()
        if proc.stderr:
            proc.stderr.close()

        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg audio extraction failed:\n{(stderr or '').strip()}")
