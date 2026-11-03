# Components Directory Contract

This directory defines the individual architectural components of Faery Good Transcriber.

## Modules & Contracts

| Component | Class / Symbol | Responsibility | Primary File |
|---|---|---|---|
| **Desktop GUI** | `FaeryTranscriberApp` | Dual-tab CustomTkinter UI, real-time transcript streaming, shortcut dispatcher | `app.py` |
| **Inference Engine** | `TranscriptionEngine` | Local Whisper model inference on CPU, thread coordination, speech segmentation | `app.py` |
| **Audio Extraction** | `OnlineMediaFetcher` | Social video/audio download via `yt-dlp`, browser cookie login integration | `app.py` |
| **Scratch Lifecycle** | `ScratchLifecycleManager` | Failsafe sandbox management, Windows retry-backoff cleanup, process exit hooks, crash orphan sweeper | `app.py` |
| **Auto Updater** | `AutoUpdater` | Weekly repository sync, standalone bundle detection (`sys.frozen`), safe stash/pull | `app.py` |
| **Ambient Radio** | `RadioStationController` | 104.9 The Grift FM playback loop via `pygame.mixer`, bumper rotation, metadata/artwork parsing | `app.py` |
| **Configuration** | `ConfigManager` | Persistent JSON settings (theme, window geometry, login browser, update intervals) | `app.py` |
| **History Library** | `HistoryManager` | In-memory indexing, search engine, multi-format file persistence (`.txt`, `.md`) | `app.py` |
| **Formatting** | `TranscriptFormatter` | Timestamp calculation, pause-based paragraph clustering, YouTube chapter syntax | `app.py` |
| **macOS App Integrator** | `ensure_macos_app_installed` | Automated `/Applications` & `~/Applications` bundle registration, LaunchServices indexing, Spotlight integration | `app.py` |

---

## Component Invariants
1. **Thread Separation:** The inference engine and audio fetcher MUST run on background threads; the GUI thread MUST remain strictly responsive (non-blocking).
2. **Scratch Isolation:** No audio extraction may write directly to persistent storage; all intermediate media passes through `ScratchLifecycleManager.safe_scratch_directory()`.
3. **Graceful Standalone Execution:** Components that rely on external tools (e.g. `git`) must check `AutoUpdater.is_standalone_bundle()` and fail gracefully without raising unhandled exceptions.
4. **Platform Safety:** Platform integration routines (such as macOS application registration) must guard against foreign OS execution (`sys.platform == 'darwin'`) and fail silently/gracefully without interrupting core application startup.
