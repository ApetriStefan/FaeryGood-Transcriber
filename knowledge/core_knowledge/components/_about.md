# Components Directory Contract

This directory defines the individual architectural components of Faery Good Transcriber, mapping each subsystem to its module location within the `faery_app/` package and its re-export in the public facade `app.py`.

## Modules & Contracts

| Component | Class / Symbol | Responsibility | Primary Module | Facade Export |
|---|---|---|---|---|
| **Public Application Facade** | `main` | Entry point, CLI dispatcher, backwards-compatible symbol re-export | `app.py` / `faery_app/__main__.py` | `app.py` |
| **Desktop GUI Main Window** | `FaeryTranscriberApp` | CustomTkinter application window, tab coordinator, thread event listener | `faery_app/ui/main_window.py` | `app.py` |
| **Transcribe Studio View** | `TranscribeStudioView` | Bento card transcription UI, drop zone, model selector, real-time transcript streaming | `faery_app/ui/views/transcribe_view.py` | `app.py` |
| **History Library View** | `HistoryLibraryView` | Split-pane historical library, search bar, card list, in-place transcript editor | `faery_app/ui/views/history_view.py` | `app.py` |
| **Ambient Radio Dock** | `RadioPlayerDock` | Dockable 104.9 The Grift FM player widget, album art display, seek scrubber | `faery_app/ui/views/radio_dock.py` | `app.py` |
| **UI Components** | `FaerySegmentedButton` | Custom animated pill-style segmented tab controller | `faery_app/ui/components/segmented_button.py` | `app.py` |
| **Modal Dialogs** | `AboutDialog`, `QuickGuideDialog`, `OverwritePromptDialog` | Onboarding guide, application credits, file overwrite resolution modals | `faery_app/ui/dialogs/` | `app.py` |
| **Menu & Shortcut Dispatcher** | `MenuBuilder` | System menu bar configuration and global keyboard shortcut binding | `faery_app/ui/menus.py` | `app.py` |
| **Brand Assets** | `BrandAssets` | Aesthetic palettes, SVG/PNG icons, watercolor mascot, fonts | `faery_app/ui/assets.py` | `app.py` |
| **Inference Engine** | `TranscriptionEngine` | Local Whisper model CPU inference (`int8`), thread coordination, speech segmentation | `faery_app/transcription/engine.py` | `app.py` |
| **Local Media Processor** | `MediaProcessor` | Audio extraction and conversion to 16kHz mono 16-bit WAV via static FFmpeg | `faery_app/media/processor.py` | `app.py` |
| **Online Media Extractor** | `OnlineMediaFetcher` | Social video/audio download via `yt-dlp`, browser cookie login integration | `faery_app/media/online_fetcher.py` | `app.py` |
| **Scratch Lifecycle Manager** | `ScratchLifecycleManager` | Failsafe sandbox isolation, Windows retry-backoff cleanup, process exit hooks, crash orphan sweeper | `faery_app/lifecycle/scratch.py` | `app.py` |
| **Auto Updater** | `AutoUpdater` | Weekly repository sync, standalone bundle detection (`sys.frozen`), safe stash/pull | `faery_app/lifecycle/updater.py` | `app.py` |
| **Ambient Radio Controller** | `RadioStationController`, `RadioTrackType`, `extract_embedded_art` | 104.9 The Grift FM playback loop via `pygame.mixer`, bumper rotation, ID3 metadata/artwork parsing | `faery_app/radio/` (`controller.py`, `types.py`, `art.py`) | `app.py` |
| **Configuration Manager** | `ConfigManager` | Persistent JSON settings (`config.json`), window geometry, login browser, fallback defaults | `faery_app/config/config_manager.py` | `app.py` |
| **History Library Manager** | `HistoryManager`, `HistoryRecord`, `SearchResult` | Embedded SQLite storage (`~/.faery_transcriber.db`) with WAL mode, FTS5 full-text spoken search indexing (`unicode61`), legacy JSON auto-migration (`.bak`), file persistence (`.txt`, `.md`) | `faery_app/history/history_manager.py` | `app.py` |
| **Formatting & Models** | `TranscriptFormatter`, `MediaMetadata`, `TranscriptSegment`, `OnlineClipInfo` | Timestamp calculation, pause-based paragraph clustering ($\ge 1.0\text{s}$), YouTube chapter syntax | `faery_app/models/` (`formatter.py`, `metadata.py`) | `app.py` |
| **System Utilities** | `get_verified_ffmpeg_exe`, `check_free_disk_space`, `open_system_folder`, `play_completion_sound` | Static FFmpeg path verification, free disk storage checks, file opening, chimes | `faery_app/utils/system.py` | `app.py` |
| **macOS App Integrator** | `ensure_macos_app_installed`, `_create_macos_app_bundle`, `_register_macos_app_bundle` | Automated `/Applications` & `~/Applications` bundle registration, LaunchServices indexing, Spotlight integration | `faery_app/utils/macos.py` | `app.py` |

---

## Component Invariants

1. **Thread Separation:** The inference engine and audio fetcher MUST run on background threads; the GUI main loop MUST remain strictly responsive and non-blocking.
2. **Scratch Isolation:** No audio extraction or media download may write directly to persistent storage; all intermediate media passes through `ScratchLifecycleManager.safe_scratch_directory()`.
3. **Graceful Standalone Execution:** Components that rely on external tools (e.g. `git`) must check `AutoUpdater.is_standalone_bundle()` and fail gracefully without raising unhandled exceptions when packaged with PyInstaller.
4. **Platform Safety:** Platform integration routines (such as macOS application registration) must guard against foreign OS execution (`sys.platform == 'darwin'`) and fail silently/gracefully without interrupting core application startup.
5. **Facade Transparency:** `app.py` must maintain re-exports of all public symbols from `faery_app` to ensure complete backwards compatibility with existing test runners, automation scripts, and packaging specifications.
6. **Database Persistence Integrity:** `HistoryManager` must access `~/.faery_transcriber.db` under WAL mode, maintaining sync between the `transcriptions` relational table and the `transcriptions_fts` virtual table, and preserving user data through automatic `.bak` migration.
