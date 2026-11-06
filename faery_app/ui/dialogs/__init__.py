"""
Dialogs subpackage for Faery Good Transcriber
"""

from faery_app.ui.dialogs.quick_guide import QuickGuideDialog
from faery_app.ui.dialogs.about import AboutDialog
from faery_app.ui.dialogs.overwrite_prompt import OverwritePromptDialog
from faery_app.ui.dialogs.cookie_permission import CookiePermissionDialog

__all__ = [
    "QuickGuideDialog",
    "AboutDialog",
    "OverwritePromptDialog",
    "CookiePermissionDialog",
]
