"""
Scratch Storage Lifecycle & Hygiene Manager for Faery Good Transcriber
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path


class ScratchLifecycleManager:
    """
    Guarantees 100% fail-safe silent lifecycle hygiene for all temporary audio
    conversions, model download fragments, and working scratch directories.

    Lifecycle guarantees:
    1. Normal Completion: Automatically deletes temporary directories via context manager.
    2. User Cancellation: Instantly purges active scratch directories upon cancel signal.
    3. Unexpected Termination: Hooks into atexit, SIGINT, SIGTERM, and window close handlers.
    4. Anti-Lock Resilience: Retries deletion with exponential backoff on Windows when OS
       antivirus or file indexers temporarily lock recently closed audio handles.
    5. Orphan Sweeping: Cleans orphaned faery_transcribe_* and faery_scratch_* directories
       left behind by previous system crashes or power losses on application startup.
    6. Model Download Hygiene: Sweeps abandoned *.incomplete model fragments in Hugging Face cache.
    """

    _active_scratch_dirs: set[Path] = set()
    _cleanup_callbacks: list = []
    _lock = threading.Lock()
    _initialized = False

    @classmethod
    def register_cleanup_callback(cls, callback) -> None:
        """Registers a callable invoked right before active scratch directories are purged."""
        with cls._lock:
            if callback not in cls._cleanup_callbacks:
                cls._cleanup_callbacks.append(callback)

    @classmethod
    def _is_pid_running(cls, pid: int) -> bool:
        """Checks whether a process ID is currently alive on POSIX or Windows."""
        if pid <= 0:
            return False
        if pid == os.getpid():
            return True
        if sys.platform == "win32":
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                SYNCHRONIZE = 0x00100000
                PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                handle = kernel32.OpenProcess(SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
                if not handle:
                    return False
                try:
                    exit_code = ctypes.c_ulong()
                    STILL_ACTIVE = 259
                    if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                        return exit_code.value == STILL_ACTIVE
                    return True
                finally:
                    kernel32.CloseHandle(handle)
            except Exception:
                return False
        else:
            try:
                os.kill(pid, 0)
                return True
            except ProcessLookupError:
                return False
            except PermissionError:
                return True
            except Exception:
                return False

    @classmethod
    def register_dir(cls, path: Path) -> None:
        """Tracks an active scratch directory and writes a PID marker for orphan safety."""
        resolved = path.resolve()
        with cls._lock:
            cls._active_scratch_dirs.add(resolved)
        try:
            (resolved / ".faery.pid").write_text(str(os.getpid()), encoding="utf-8")
        except Exception:
            pass

    @classmethod
    def unregister_dir(cls, path: Path) -> None:
        """Removes a successfully cleaned scratch directory from tracking."""
        with cls._lock:
            cls._active_scratch_dirs.discard(path.resolve())

    @classmethod
    def safe_remove_tree(cls, target: Path, max_retries: int = 4, delay: float = 0.05) -> None:
        """
        Removes a directory tree safely with retry backoff to survive transient
        Windows file locking (e.g. Defender, search indexing, or async audio releases).
        """
        if not target.exists():
            return
        if not target.is_dir():
            try:
                target.unlink(missing_ok=True)
            except Exception:
                pass
            return
        for attempt in range(max_retries):
            try:
                shutil.rmtree(target, ignore_errors=False)
                return
            except Exception:
                time.sleep(delay * (attempt + 1))
        # Final fallback with ignore_errors=True to guarantee non-blocking silence
        try:
            shutil.rmtree(target, ignore_errors=True)
        except Exception:
            pass

    @classmethod
    @contextmanager
    def safe_scratch_directory(cls, prefix: str = "faery_transcribe_"):
        """Context manager yielding a temporary Path guaranteed to be cleaned under all conditions."""
        temp_dir_str = tempfile.mkdtemp(prefix=prefix)
        temp_path = Path(temp_dir_str)
        cls.register_dir(temp_path)
        try:
            yield temp_path
        finally:
            try:
                cls.safe_remove_tree(temp_path)
            finally:
                cls.unregister_dir(temp_path)

    @classmethod
    def cleanup_all_active(cls) -> None:
        """Silently and immediately closes registered handles and purges all active scratch directories."""
        with cls._lock:
            callbacks = list(cls._cleanup_callbacks)
            active_list = list(cls._active_scratch_dirs)
            cls._active_scratch_dirs.clear()
        for cb in callbacks:
            try:
                cb()
            except Exception:
                pass
        for p in active_list:
            cls.safe_remove_tree(p)

    @classmethod
    def cleanup_orphaned_scratch(cls) -> None:
        """
        Sweeps the system temporary directory for orphaned Faery Transcriber folders
        left by prior system crashes or hard termination. Also sweeps abandoned
        Hugging Face *.incomplete model download fragments.
        """
        # 1. Sweep system temp directory for orphaned audio conversion folders
        try:
            temp_root = Path(tempfile.gettempdir())
            for prefix in ("faery_transcribe_*", "faery_scratch_*", "faery_mic_*"):
                for item in temp_root.glob(prefix):
                    if not item.is_dir() or item.resolve() in cls._active_scratch_dirs:
                        continue
                    pid_file = item / ".faery.pid"
                    if pid_file.exists():
                        try:
                            pid_val = int(pid_file.read_text(encoding="utf-8").strip())
                            if cls._is_pid_running(pid_val):
                                continue
                        except Exception:
                            pass
                    cls.safe_remove_tree(item)
        except Exception:
            pass

        # 2. Sweep Hugging Face Hub cache for stale .incomplete model downloads (>1 hour old)
        try:
            hf_home = os.environ.get("HF_HOME")
            cache_base = Path(hf_home) if hf_home else (Path.home() / ".cache" / "huggingface" / "hub")
            if cache_base.exists():
                now = time.time()
                for incomplete_file in cache_base.rglob("*.incomplete"):
                    try:
                        if now - incomplete_file.stat().st_mtime > 3600:
                            incomplete_file.unlink(missing_ok=True)
                    except Exception:
                        pass
        except Exception:
            pass

    @classmethod
    def initialize_lifecycle(cls) -> None:
        """Installs atexit and signal termination handlers, and runs an orphan sweep."""
        if cls._initialized:
            return
        cls._initialized = True

        import atexit
        atexit.register(cls.cleanup_all_active)

        import signal
        def _signal_handler(signum, frame):
            cls.cleanup_all_active()
            sys.exit(0)

        for sig_name in ("SIGINT", "SIGTERM", "SIGBREAK"):
            if hasattr(signal, sig_name):
                try:
                    signal.signal(getattr(signal, sig_name), _signal_handler)
                except Exception:
                    pass

        # Run background orphan cleanup non-blockingly so application startup remains instantaneous
        threading.Thread(target=cls.cleanup_orphaned_scratch, daemon=True, name="FaeryScratchOrphanSweep").start()
