"""
Silent Rotating Diagnostic & Crash Logger for Faery Good Transcriber
Captures silent diagnostic telemetry, unhandled exceptions, faulthandler thread dumps,
and background thread crashes to ~/.faery_transcriber_crash.log
"""

from __future__ import annotations

import faulthandler
import logging
from logging.handlers import RotatingFileHandler
import os
import platform
import sys
import threading
import traceback
from pathlib import Path
from typing import Optional, Union

from faery_app.constants import CRASH_LOG_PATH

_logger = logging.getLogger("faery_crash_logger")
_initialized = False
_crash_file_handle = None
_orig_sys_excepthook = sys.excepthook
_orig_threading_excepthook = getattr(threading, "excepthook", None)


def init_crash_logging() -> None:
    """
    Idempotent bootstrap of rotating file handler, faulthandler, and uncaught exception hooks.
    Ensures crashes in any thread or unhandled interpreter terminations are silently logged.
    """
    global _initialized, _crash_file_handle
    if _initialized:
        return
    _initialized = True

    try:
        CRASH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    # Ensure RotatingFileHandler is attached
    if not any(isinstance(h, RotatingFileHandler) for h in _logger.handlers):
        try:
            handler = RotatingFileHandler(
                CRASH_LOG_PATH,
                maxBytes=512_000,
                backupCount=1,
                encoding="utf-8",
            )
            formatter = logging.Formatter("%(asctime)s [%(levelname)s] (%(threadName)s) %(message)s")
            handler.setFormatter(formatter)
            _logger.addHandler(handler)
            _logger.setLevel(logging.INFO)
            _logger.propagate = False
        except Exception:
            pass

    # Python stdlib faulthandler writes to a dedicated file descriptor so
    # RotatingFileHandler on Windows never collides during log rollover.
    try:
        fh_path = CRASH_LOG_PATH.with_name(".faery_transcriber_faulthandler.log")
        if _crash_file_handle is None or _crash_file_handle.closed:
            _crash_file_handle = open(fh_path, "a", encoding="utf-8")
        faulthandler.enable(file=_crash_file_handle, all_threads=True)
    except Exception:
        pass

    # Set uncaught top-level exception handler
    def _uncaught_sys_excepthook(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            if _orig_sys_excepthook:
                _orig_sys_excepthook(exc_type, exc_value, exc_traceback)
            return
        tb = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        _logger.error(f"Uncaught top-level exception: {exc_value}\n{tb}")
        for h in _logger.handlers:
            try:
                h.flush()
            except Exception:
                pass
        if _orig_sys_excepthook:
            _orig_sys_excepthook(exc_type, exc_value, exc_traceback)

    sys.excepthook = _uncaught_sys_excepthook

    # Set uncaught background thread exception handler
    if hasattr(threading, "excepthook"):
        def _uncaught_threading_excepthook(args):
            tb = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
            thread_name = getattr(args.thread, "name", "UnknownThread")
            _logger.error(f"Uncaught background thread exception in ({thread_name}): {args.exc_value}\n{tb}")
            for h in _logger.handlers:
                try:
                    h.flush()
                except Exception:
                    pass
            if _orig_threading_excepthook:
                _orig_threading_excepthook(args)

        threading.excepthook = _uncaught_threading_excepthook


def shutdown_crash_logging() -> None:
    """
    Flushes and closes all handlers and file handles associated with crash logging.
    Restores original excepthooks. Safe for testing and application teardown.
    """
    global _initialized, _crash_file_handle, _orig_sys_excepthook, _orig_threading_excepthook
    try:
        faulthandler.disable()
    except Exception:
        pass
    if _crash_file_handle is not None and not _crash_file_handle.closed:
        try:
            _crash_file_handle.flush()
            _crash_file_handle.close()
        except Exception:
            pass
        _crash_file_handle = None
    for handler in list(_logger.handlers):
        try:
            handler.flush()
            handler.close()
        except Exception:
            pass
        _logger.removeHandler(handler)
    if _orig_sys_excepthook:
        sys.excepthook = _orig_sys_excepthook
    if _orig_threading_excepthook and hasattr(threading, "excepthook"):
        threading.excepthook = _orig_threading_excepthook
    _initialized = False


def log_exception(exc_or_msg: Union[BaseException, str], context: str = "") -> None:
    """
    Formats and writes full traceback/details to the crash log.
    Accepts either an exception instance or a string message.
    """
    if not _initialized:
        init_crash_logging()

    ctx_prefix = f"[{context}] " if context else ""
    if isinstance(exc_or_msg, BaseException):
        tb = "".join(traceback.format_exception(type(exc_or_msg), exc_or_msg, exc_or_msg.__traceback__))
        _logger.error(f"{ctx_prefix}{type(exc_or_msg).__name__}: {exc_or_msg}\n{tb}")
    else:
        msg = str(exc_or_msg)
        exc_type, exc_val, exc_tb = sys.exc_info()
        if exc_type is not None and exc_tb is not None:
            tb = "".join(traceback.format_exception(exc_type, exc_val, exc_tb))
            _logger.error(f"{ctx_prefix}{msg}\nActive Exception:\n{tb}")
        else:
            _logger.error(f"{ctx_prefix}{msg}")

    for h in _logger.handlers:
        try:
            h.flush()
        except Exception:
            pass


def get_diagnostic_log_content(max_lines: int = 100) -> str:
    """
    Reads the tail of CRASH_LOG_PATH with local user home path redaction. If empty or missing,
    returns a comprehensive system summary (OS, Python version, platform, memory).
    """
    home_str = str(Path.home())
    if CRASH_LOG_PATH.exists():
        try:
            with open(CRASH_LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            if lines and any(l.strip() for l in lines):
                tail = lines[-max_lines:]
                raw = "".join(tail)
                if home_str:
                    raw = raw.replace(home_str, "~")
                return raw
        except Exception:
            pass

    # System summary fallback
    summary_lines = [
        "=== Faery Transcriber Diagnostic Summary ===",
        f"OS: {platform.system()} {platform.release()} ({platform.version()})",
        f"Platform: {platform.platform()}",
        f"Architecture: {platform.machine()}",
        f"Python Version: {platform.python_version()} ({sys.executable.replace(home_str, '~') if home_str else sys.executable})",
    ]
    try:
        import psutil
        vm = psutil.virtual_memory()
        summary_lines.append(f"Total RAM: {vm.total / (1024**3):.1f} GB")
        summary_lines.append(f"Available RAM: {vm.available / (1024**3):.1f} GB")
    except Exception:
        summary_lines.append("Memory: psutil unavailable")
    summary_lines.append("Log Status: Clean (No crashes recorded)")
    return "\n".join(summary_lines)
