# Components Directory Contract

This directory defines the individual architectural components of Faery Good Transcriber, mapping each subsystem to its module location within the `faery_app/` package and its re-export in the public facade `app.py`.

## Modules & Contracts

| Component | Class / Symbol | Responsibility | Primary Module | Facade Export |
|---|---|---|---|---|
| **Public Application Facade** | `main` | Entry point, CLI dispatcher, backwards-compatible symbol re-export | `app.py` / `faery_app/__main__.py` | `app.py` |
| **Desktop GUI Main Window** | `FaeryTranscriberApp` | CustomTkinter application window, tab coordinator, 60ms coalesced live segment streaming, $O(1)$ in-place History card highlighting, 80ms debounced search, demand-driven Radio polling (0 Hz when off), dynamic model-switching ETA recalculation, Help menu diagnostic copy action | `faery_app/ui/main_window.py` | `app.py` |
| **Transcribe Studio View** | `TranscribeStudioView` | Bento card transcription UI, drop zone, model selector, upfront self-calibrating ETA with tea break hint (`☕`), real-time transcript streaming | `faery_app/ui/views/transcribe_view.py` | `app.py` |
| **History Library View** | `HistoryLibraryView` | Split-pane historical library, search bar, card list, in-place transcript editor | `faery_app/ui/views/history_view.py` | `app.py` |
| **Ambient Radio Dock** | `RadioPlayerDock` | Dockable 104.9 The Grift FM player widget, album art display, seek scrubber | `faery_app/ui/views/radio_dock.py` | `app.py` |
| **UI Components** | `FaerySegmentedButton` | Custom animated pill-style segmented tab controller | `faery_app/ui/components/segmented_button.py` | `app.py` |
| **Modal Dialogs** | `AboutDialog`, `QuickGuideDialog`, `OverwritePromptDialog`, `CookiePermissionDialog` | Onboarding guide, application credits, file overwrite resolution, and Auto-mode browser cookie permission modals | `faery_app/ui/dialogs/` | `app.py` |
| **Menu & Shortcut Dispatcher** | `MenuBuilder` | System menu bar configuration, Help menu diagnostic clipboard export, and global keyboard shortcut binding (`⌘O`, `⌘D`, `⌘L`, `⌘R`, etc.) | `faery_app/ui/menus.py` | `app.py` |
| **Brand Assets** | `BrandAssets` | Aesthetic palettes, SVG/PNG icons, watercolor mascot, fonts | `faery_app/ui/assets.py` | `app.py` |
| **Inference Engine** | `TranscriptionEngine` | Lazy-imported local English-optimized Whisper model CPU inference (`int8`, `language="en"`, `large-v3-turbo` / `small.en` / `base.en`), punctuation priming (`DEFAULT_PUNCTUATION_PROMPT`, `condition_on_previous_text=True`), adaptive multi-core CPU thread scaling (`get_optimal_cpu_threads`, up to 8 threads), blended live countdown telemetry, post-inference RTF EMA calibration, speech segmentation | `faery_app/transcription/engine.py` | `app.py` |
| **Local Media Processor** | `MediaProcessor` | Audio extraction and conversion to 16kHz mono 16-bit WAV via static FFmpeg, with native Python `wave` header fast-path (`_probe_wav_fast`) and 16kHz mono PCM extraction bypass (`is_16k_mono_pcm_wav`) | `faery_app/media/processor.py` | `app.py` |
| **Microphone Recorder** | `MicrophoneRecorder` | 16kHz mono 16-bit PCM WAV microphone recording via `sounddevice` into `faery_mic_*` scratch directories | `faery_app/media/recorder.py` | `app.py` |
| **Online Media Extractor** | `OnlineMediaFetcher` | Social video/audio download via `yt-dlp[default]`, `yt-dlp-ejs`, and cached `deno` runtime resolution, plus consent-gated browser cookie login integration (Safari, Chrome, Firefox, Edge, Brave) | `faery_app/media/online_fetcher.py` | `app.py` |
| **Scratch Lifecycle Manager** | `ScratchLifecycleManager` | Failsafe sandbox isolation (`faery_transcribe_*`, `faery_mic_*`), Windows retry-backoff cleanup, process exit hooks, crash orphan sweeper | `faery_app/lifecycle/scratch.py` | `app.py` |
| **Diagnostic & Crash Logger** | `init_crash_logging`, `log_exception`, `get_diagnostic_log_content` | Silent rotating diagnostic log (`~/.faery_transcriber_crash.log`, 512KB, 1 backup), stdlib `faulthandler` thread dumping, `sys.excepthook` / `threading.excepthook` unhandled crash interception, system summary generation | `faery_app/lifecycle/crash_logger.py` | `app.py` |
| **Auto Updater** | `AutoUpdater` | Weekly repository sync and `yt-dlp[default]` / `yt-dlp-ejs` / `deno` package upgrades, standalone bundle detection (`sys.frozen`), safe stash/pull | `faery_app/lifecycle/updater.py` | `app.py` |
| **Ambient Radio Controller** | `RadioStationController`, `RadioTrackType`, `extract_embedded_art` | 104.9 The Grift FM playback loop via `pygame.mixer`, bumper rotation, ID3 metadata/artwork parsing | `faery_app/radio/` (`controller.py`, `types.py`, `art.py`) | `app.py` |
| **Configuration Manager** | `ConfigManager` | Persistent JSON settings (`config.json`), window geometry, login browser, fallback defaults, `model_rtf` benchmarks, and Exponential Moving Average calibration | `faery_app/config/config_manager.py` | `app.py` |
| **History Library Manager** | `HistoryManager`, `HistoryRecord`, `SearchResult` | Embedded SQLite storage (`~/.faery_transcriber.db`) with WAL mode, `@contextmanager` connection lifecycle, batched transactions, $O(1)$ single-record FTS5 updates (`update_record_content`), FTS5 spoken search (`unicode61`), legacy JSON auto-migration (`.bak`) | `faery_app/history/history_manager.py` | `app.py` |
| **Formatting & Models** | `TranscriptFormatter`, `format_eta`, `MediaMetadata`, `TranscriptSegment`, `OnlineClipInfo` | Task ETA formatting, timestamp calculation, pause-based paragraph clustering ($\ge 1.0\text{s}$), paragraph boundary punctuation healing (`_heal_paragraph`), timestamped transcripts (`[MM:SS]`) | `faery_app/models/` (`formatter.py`, `metadata.py`) | `app.py` |
| **System Utilities** | `get_verified_ffmpeg_exe`, `check_free_disk_space`, `open_system_folder`, `play_completion_sound` | Cached static FFmpeg path verification, free disk storage checks, file opening, chimes | `faery_app/utils/system.py` | `app.py` |
| **macOS App Integrator** | `ensure_macos_app_installed`, `_create_macos_app_bundle`, `_register_macos_app_bundle` | Automated `/Applications` & `~/Applications` bundle registration, LaunchServices indexing, Spotlight integration | `faery_app/utils/macos.py` | `app.py` |

---

## Component Invariants

1. **Thread Separation:** The inference engine and audio fetcher MUST run on background threads; the GUI main loop MUST remain strictly responsive and non-blocking.
2. **Scratch Isolation:** No audio extraction or media download may write directly to persistent storage; all intermediate media passes through `ScratchLifecycleManager.safe_scratch_directory()`.
3. **Graceful Standalone Execution:** Components that rely on external tools (e.g. `git`) must check `AutoUpdater.is_standalone_bundle()` and fail gracefully without raising unhandled exceptions when packaged with PyInstaller.
4. **Platform Safety:** Platform integration routines (such as macOS application registration) must guard against foreign OS execution (`sys.platform == 'darwin'`) and fail silently/gracefully without interrupting core application startup.
5. **Facade Transparency:** `app.py` must maintain re-exports of all public symbols from `faery_app` to ensure complete backwards compatibility with existing test runners, automation scripts, and packaging specifications.
6. **Database Persistence Integrity:** `HistoryManager` must access `~/.faery_transcriber.db` under WAL mode, maintaining sync between the `transcriptions` relational table and the `transcriptions_fts` virtual table, and preserving user data through automatic `.bak` migration.
