# Infrastructure Directory Contract

This directory documents the deployment, packaging, execution environments, self-healing launchers, and testing tools for the project.

---

## 1. Runtime Environments & Code Structure

* **Supported Python Runtimes:** Python 3.10 to Python 3.13 (strictly requiring Python >= 3.10; x86_64 on Windows; x86_64 and ARM64 Apple Silicon on macOS). Legacy Python versions (< 3.10, including macOS's default Python 3.9 stub) are explicitly unsupported due to package and typing compatibility requirements.
* **Isolation Model:** Dedicated `.venv` virtual environment isolated inside the application root directory with automated version validation and stale environment purging.
* **FFmpeg Dependency:** Statically provided through `imageio_ffmpeg` to eliminate any requirement for system-level FFmpeg installation.
* **Modular Package Architecture:** The application code is organized as the `faery_app/` Python package with decoupled subpackages (`config`, `lifecycle`, `models`, `media`, `transcription`, `radio`, `history`, `utils`, `ui`). The root `app.py` acts as a public re-export facade and bootstrap entry point. Both `python app.py` and `python -m faery_app` are supported execution models.

---

## 2. Self-Healing Launchers

### Windows Launcher (`Run_Windows.bat`)
* **Discovery Matrix:**
  1. Active `.venv` environment (validates `python.exe` >= 3.10 and essential imports including `customtkinter`, `faster_whisper`, `yt_dlp_ejs`, `deno`, `sounddevice`, `pygame`).
  2. System `PATH` (`python` and `py -3` checked with `sys.version_info >= (3, 10)`).
  3. Per-user installations (`%LOCALAPPDATA%\Programs\Python\Python310` through `Python313`; legacy 3.8 and 3.9 are pruned from candidate search).
  4. Machine installations (`%ProgramFiles%\Python310` through `Python313`).
* **Self-Healing Fallbacks & Stale Environment Reset:**
  - **Stale `.venv` Purging:** Probes `.venv\Scripts\python.exe` against `sys.version_info >= (3, 10)`. If created with an incompatible or outdated Python version (< 3.10), automatically removes the directory (`rmdir /s /q ".venv"`) and initializes a clean environment.
  - **Missing Python 3.10+ Alerting:** If no supported Python runtime is detected, triggers a native graphical alert using Windows Forms via PowerShell offering to navigate directly to `python.org/downloads/`.
  - Automatically provisions `.venv`, installs packages from `requirements.txt`, and silences routine dependency updates.

### macOS Launcher (`Run_Mac.command`)
* **Discovery Matrix:**
  - Evaluates Python candidates via `is_valid_python()` checking `sys.version_info >= (3, 10)`.
  - Prioritized search order:
    1. Official Python framework installations (`/Library/Frameworks/Python.framework/Versions/3.13` down to `3.10`).
    2. Intel Homebrew / local binaries (`/usr/local/bin/python3.13` down to `3.10`, `/usr/local/bin/python3`).
    3. Apple Silicon Homebrew (`/opt/homebrew/bin/python3.13` down to `3.10`, `/opt/homebrew/bin/python3`).
    4. User environments (`$HOME/.pyenv/shims/python3`, `$HOME/miniforge3/bin/python3`, `$HOME/miniconda3/bin/python3`).
    5. PATH lookups (`which python3.13` down to `python3.10`, `which python3`).
    6. System Python (`/usr/bin/python3`).
* **macOS Python 3.9 Stub Mitigation & 1-Click Bootstrap:**
  - macOS ships with a default Python 3.9.6 stub (`/usr/bin/python3`) that lacks modern runtime support and required dependencies.
  - When no valid Python >= 3.10 is found, the launcher invokes native AppleScript to display an alert informing the user that Python 3.12 is required.
  - Clicking **"Install Python"** automatically initiates a download via `curl -fSL` targeting `https://www.python.org/ftp/python/3.12.10/python-3.12.10-macos11.pkg` saved to `/tmp/python-3.12.10-macos11.pkg`, and invokes `open "$PKG_PATH"` to present the official installer wizard. A modal guidance dialog guides the user to complete installation and re-launch. If download fails, it gracefully opens `https://www.python.org/downloads/macos/` in the default browser.
* **Stale `.venv` Purging & Reset:**
  - Validates `.venv/bin/python` using `is_valid_python()`. If an existing virtual environment was built using Python < 3.10 (such as the default macOS 3.9 stub), it is automatically purged via `rm -rf ".venv"` prior to creating a fresh `.venv` using the resolved modern Python.
* **Automatic Applications Folder Integration (`install_app_bundle`):**
  - Probes writability of `/Applications`; falls back seamlessly to `$HOME/Applications` for standard accounts without root/sudo access.
  - Constructs `Faery Good Transcriber.app` bundle containing `Info.plist` (including `NSMicrophoneUsageDescription`), `.venv` launcher script, and `faery_icon.icns`.
  - Clears quarantine flags via `xattr -cr` and forces LaunchServices registration (`lsregister -f`) with timestamp touch for immediate Spotlight and Launchpad indexing.

---

## 3. Packaging & Standalone Bundling

* **Build Specification:** `FaeryTranscriber.spec` using PyInstaller 6.x.
* **Entry Point:** Targets `app.py` as the top-level script, collecting all modules under `faery_app/` as hidden imports (including `faery_app.media.recorder` and `faery_app.ui.dialogs.cookie_permission`) and collecting `yt_dlp_ejs`, `deno`, and `sounddevice` in `critical_pkgs`.
* **Windowed GUI:** Configured with `console=False` to prevent extraneous command prompt windows on end-user machines.
* **Asset Bundling:**
  - Radio audio tracks (`assets/music/`) and bumpers (`assets/announcer/`).
  - Warm UI theme JSON (`assets/faery_good_theme.json`).
  - Brand icons (`assets/faery_icon.png`, `assets/faery_icon.ico`, `assets/faery_icon.icns`).
  - Bundled binary dependencies (`imageio_ffmpeg` static FFmpeg executable).
* **Standalone Immunity:** In frozen binary mode, `sys.frozen` evaluates to `True`, automatically instructing `AutoUpdater` to skip Git execution.
* **macOS Application Registration Subsystem (`ensure_macos_app_installed`):**
  - Executed on startup bootstrap (`main()`) before GUI initialization.
  - **Source-Run Mode:** Generates `.app` bundle structure with launcher script and metadata on first launch.
  - **Frozen Bundle Mode:** Safely synchronizes the standalone PyInstaller bundle into `/Applications` (or `~/Applications`).
  - **Zero-Sudo Friction:** Falls back from `/Applications` to `~/Applications` if system directory permissions are restricted, ensuring no administrator password dialogs are shown.
  - **System Registration:** Strips quarantine bits (`xattr -cr`), executes `lsregister -f`, and updates directory mtime (`os.utime`) for immediate Spotlight discoverability (`⌘+Space`).

---

## 4. Test Suite & Quality Verification

* **Framework:** Standard library `unittest` (`test_app.py`).
* **Status:** 71 passing unit and integration tests (0 failures, 0 errors).
* **Execution:**
  ```bash
  python -m unittest test_app.py
  ```
* **Test Matrix:** 71 comprehensive unit and integration tests covering:
  - Formatter logic (paragraphs, timecodes, markdown).
  - Scratch lifecycle hygiene, isolated directories, and file lock backoff.
  - Auto-update cadence, bundle detection, and offline handling.
  - History indexing, SQLite WAL mode, schema validation, FTS5 snippet ranking, favorite toggling, and legacy JSON auto-migration.
  - URL detection across all supported social platforms.
  - Media processor audio extraction and duration parsing.
  - Config manager read, write, and corrupt JSON restoration.
  - Public facade symbol exports (ensuring `app.py` exposes all classes and helpers identically to `faery_app`).
  - macOS Application Integration (`TestMacOSAppIntegration`): platform guard on non-darwin OS, `.app` bundle hierarchy generation, permission fallback to `~/Applications`, frozen bundle replication, and directory writability validation.
  - Performance & Hardware Optimization Suite (`TestPerformanceOptimizations`): lazy WhisperModel loading, zero-subprocess WAV fast probing, mono 16kHz PCM conversion bypass, cached binary paths, batched SQLite synchronization, single-record in-place content updates, zero-disk-I/O search, demand-driven 0 Hz idle radio polling, physical CPU core thread allocation heuristics, macOS `prevent_app_nap` lifecycle management via `caffeinate`, and Intel OpenMP passive wait environment variables (`KMP_BLOCKTIME=0`, `OMP_WAIT_POLICY=PASSIVE`).
  - Diagnostic Logging & Task ETA Suite (`TestCrashLoggerAndTaskETA`): `format_eta` boundary transitions (<15s, <60s, <3600s, $\ge$3600s), `ConfigManager` `model_rtf` getters, [0.05, 3.0] boundary clamping, Exponential Moving Average (EMA) calibration persistence, silent rotating crash logging (`~/.faery_transcriber_crash.log`), stdlib `faulthandler` integration, system diagnostic fallback synthesis via `get_diagnostic_log_content`, `TranscriptionEngine` live blended RTF calculation and post-task EMA calibration, dynamic metadata display, model switching with tea hint (`☕`), `MODEL_DISPLAY_NAMES` validation with `large-v3-turbo` as default, and `ConfigManager` baseline RTF (0.48) and canonical alias resolution.
  - Punctuation & Model Accuracy Optimization Suite (`TestFormattersAndEdgeCases`): `TranscriptFormatter._heal_paragraph()` boundary normalization (converting trailing commas, colons, and semicolons to periods on boundary closure, closing unpunctuated alphanumeric endings with periods, auto-capitalizing lowercase paragraph starts, and preserving legitimate terminal punctuation `.`, `!`, `?`, `."`, `!"`, `?"`, `”`, `…`), empty and whitespace-only boundary handling, and `TranscriptionEngine` punctuation priming injection (`initial_prompt=DEFAULT_PUNCTUATION_PROMPT`, `condition_on_previous_text=True`).
  - Launcher Script & Runtime Invariants Suite (`TestLauncherScripts`): script existence and structure validation for `Run_Mac.command` and `Run_Windows.bat`, Python >= 3.10 version checking logic (`sys.version_info >= (3, 10)`), candidate path scans omitting EOL Python 3.8/3.9, macOS built-in Python 3.9 stub rejection, stale/incompatible `.venv` detection and automatic purging simulation, frictionless 1-click Python 3.12 installer package download and invocation flow (`python-3.12.10-macos11.pkg`), and Windows WinForms alert dialog triggers.
