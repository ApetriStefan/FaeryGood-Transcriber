"""
Lifecycle subpackage for Faery Good Transcriber
"""

from faery_app.lifecycle.scratch import ScratchLifecycleManager
from faery_app.lifecycle.updater import AutoUpdater
from faery_app.lifecycle.crash_logger import (
    init_crash_logging,
    shutdown_crash_logging,
    log_exception,
    get_diagnostic_log_content,
    CRASH_LOG_PATH,
)

__all__ = [
    "ScratchLifecycleManager",
    "AutoUpdater",
    "init_crash_logging",
    "shutdown_crash_logging",
    "log_exception",
    "get_diagnostic_log_content",
    "CRASH_LOG_PATH",
]
