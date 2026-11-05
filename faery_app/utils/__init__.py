"""
Utils subpackage for Faery Good Transcriber
"""

from faery_app.utils.system import (
    get_verified_ffmpeg_exe,
    check_free_disk_space,
    open_system_folder,
    open_system_file,
    play_completion_sound,
    is_directory_writable,
)
from faery_app.utils.macos import (
    ensure_macos_app_installed,
    _create_macos_app_bundle,
    _register_macos_app_bundle,
)

__all__ = [
    "get_verified_ffmpeg_exe",
    "check_free_disk_space",
    "open_system_folder",
    "open_system_file",
    "play_completion_sound",
    "is_directory_writable",
    "ensure_macos_app_installed",
    "_create_macos_app_bundle",
    "_register_macos_app_bundle",
]
