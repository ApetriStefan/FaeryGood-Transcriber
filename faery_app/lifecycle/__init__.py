"""
Lifecycle subpackage for Faery Good Transcriber
"""

from faery_app.lifecycle.scratch import ScratchLifecycleManager
from faery_app.lifecycle.updater import AutoUpdater

__all__ = ["ScratchLifecycleManager", "AutoUpdater"]
