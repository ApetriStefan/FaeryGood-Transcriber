"""
System Utilities, Audio Chimes, and File System Probing for Faery Good Transcriber
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import imageio_ffmpeg

from faery_app.constants import MIN_DISK_SPACE_MB

_CACHED_FFMPEG_EXE: Optional[str] = None


def get_verified_ffmpeg_exe() -> str:
    """
    Retrieves the bundled static FFmpeg binary path from imageio-ffmpeg.
    Ensures execution permissions are granted on Unix/macOS environments and caches the verified path.
    """
    global _CACHED_FFMPEG_EXE
    if _CACHED_FFMPEG_EXE and os.path.exists(_CACHED_FFMPEG_EXE):
        return _CACHED_FFMPEG_EXE

    exe = imageio_ffmpeg.get_ffmpeg_exe()
    if not exe or not os.path.exists(exe):
        raise FileNotFoundError(
            "The bundled FFmpeg binary could not be located via imageio-ffmpeg. "
            "Please ensure imageio-ffmpeg is installed properly."
        )
    # Ensure executable permission on macOS/Linux
    if sys.platform != "win32":
        try:
            current_perms = os.stat(exe).st_mode
            if not (current_perms & 0o111):
                os.chmod(exe, current_perms | 0o755)
        except Exception:
            pass
    _CACHED_FFMPEG_EXE = exe
    return exe


def check_free_disk_space(target_path: Path, min_mb: int = MIN_DISK_SPACE_MB) -> bool:
    """Verifies that the target path or its parent volume has at least min_mb free space."""
    try:
        check_dir = target_path if target_path.exists() else target_path.parent
        usage = shutil.disk_usage(check_dir)
        free_mb = usage.free / (1024 * 1024)
        return free_mb >= min_mb
    except Exception:
        return True


def open_system_folder(folder_path: Path) -> None:
    """Opens a directory in the native file manager across Windows, macOS, and Linux."""
    folder_path.mkdir(parents=True, exist_ok=True)
    abs_path = str(folder_path.resolve())

    if sys.platform == "win32":
        os.startfile(abs_path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", abs_path])
    else:
        subprocess.Popen(["xdg-open", abs_path])


def open_system_file(file_path: Path) -> None:
    """Opens a file in the default system viewer/editor across OSes."""
    if not file_path.exists():
        return
    abs_path = str(file_path.resolve())
    if sys.platform == "win32":
        os.startfile(abs_path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", abs_path])
    else:
        subprocess.Popen(["xdg-open", abs_path])


def play_completion_sound() -> None:
    """Plays a native, non-intrusive completion chime on macOS, Windows, and Linux."""
    try:
        if sys.platform == "darwin":
            sound_candidates = [
                "/System/Library/Sounds/Glass.aiff",
                "/System/Library/Sounds/Ping.aiff",
                "/System/Library/Sounds/Hero.aiff",
            ]
            for sound in sound_candidates:
                if os.path.exists(sound):
                    subprocess.Popen(
                        ["afplay", sound],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    break
        elif sys.platform == "win32":
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        else:
            if shutil.which("paplay"):
                sound_p = "/usr/share/sounds/freedesktop/stereo/complete.oga"
                if os.path.exists(sound_p):
                    subprocess.Popen(
                        ["paplay", sound_p],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
    except Exception:
        pass


def is_directory_writable(directory: Path | str) -> bool:
    """Checks whether the current process has write permissions to the specified directory."""
    path = Path(directory)
    try:
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            return True
        if not os.access(str(path), os.W_OK):
            return False
        # Create a lightweight probe file to confirm actual write permission
        test_file = path / f".write_test_{os.getpid()}_{int(time.time() * 1000)}"
        try:
            test_file.touch()
            test_file.unlink(missing_ok=True)
            return True
        except (PermissionError, OSError):
            return False
    except (PermissionError, OSError):
        return False
