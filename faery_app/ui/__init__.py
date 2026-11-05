"""
UI subpackage for Faery Good Transcriber
"""

from faery_app.ui.assets import BrandAssets
from faery_app.ui.components.segmented_button import FaerySegmentedButton
from faery_app.ui.dialogs.quick_guide import QuickGuideDialog
from faery_app.ui.dialogs.about import AboutDialog
from faery_app.ui.dialogs.overwrite_prompt import OverwritePromptDialog
from faery_app.ui.views.transcribe_view import TranscribeStudioView
from faery_app.ui.views.history_view import HistoryLibraryView
from faery_app.ui.views.radio_dock import RadioPlayerDock
from faery_app.ui.menus import MenuBuilder
from faery_app.ui.main_window import FaeryTranscriberApp

__all__ = [
    "BrandAssets",
    "FaerySegmentedButton",
    "QuickGuideDialog",
    "AboutDialog",
    "OverwritePromptDialog",
    "TranscribeStudioView",
    "HistoryLibraryView",
    "RadioPlayerDock",
    "MenuBuilder",
    "FaeryTranscriberApp",
]
