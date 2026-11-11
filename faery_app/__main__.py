"""
Package CLI Entry Point for `python -m faery_app`
"""

from __future__ import annotations

import sys
from faery_app.utils.macos import ensure_macos_app_installed
from faery_app.ui.main_window import FaeryTranscriberApp


def main() -> None:
    """Bootstrap application entry point."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("faerygood.transcriber.studio.1.0")
        except Exception:
            pass
    try:
        ensure_macos_app_installed()
    except Exception as exc:
        print(f"[FaeryTranscriber] Notice during startup app check: {exc}")
    app = FaeryTranscriberApp()
    app.mainloop()


if __name__ == "__main__":
    main()
