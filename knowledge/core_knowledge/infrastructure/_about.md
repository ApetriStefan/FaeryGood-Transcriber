# Infrastructure Directory Contract

This directory documents the deployment, packaging, execution environments, self-healing launchers, and testing tools for the project.

---

## 1. Runtime Environments & Code Structure

* **Supported Python Runtimes:** Python 3.10 to Python 3.13 (x86_64 on Windows; x86_64 and ARM64 Apple Silicon on macOS).
* **Isolation Model:** Dedicated `.venv` virtual environment isolated inside the application root directory.
* **FFmpeg Dependency:** Statically provided through `imageio_ffmpeg` to eliminate any requirement for system-level FFmpeg installation.
* **Modular Package Architecture:** The application code is organized as the `faery_app/` Python package with decoupled subpackages (`config`, `lifecycle`, `models`, `media`, `transcription`, `radio`, `history`, `utils`, `ui`). The root `app.py` acts as a public re-export facade and bootstrap entry point. Both `python app.py` and `python -m faery_app` are supported execution models.

---

## 2. Self-Healing Launchers

### Windows Launcher (`Run_Windows.bat`)
* **Discovery Matrix:**
  1. Active `.venv` environment (validates `python.exe` and essential imports).
  2. System `PATH` (`python` and `py -3`).
  3. Per-user installations (`%LOCALAPPDATA%\Programs\Python\Python38` through `Python313`).
  4. Machine installations (`%ProgramFiles%\Python38` through `Python313`).
* **Self-Healing Fallbacks:**
  - If Python 3 is absent, triggers a native graphical alert using Windows Forms via PowerShell with a direct prompt offering to navigate to `python.org/downloads/`.
  - Automatically provisions `.venv`, installs packages from `requirements.txt`, and silences routine dependency updates.

### macOS Launcher (`Run_Mac.command`)
* **Discovery Matrix:**
  - Homebrew Apple Silicon (`/opt/homebrew/bin/python3`), Intel Homebrew (`/usr/local/bin/python3`), and system binaries (`/usr/bin/python3`, `which python3`).
* **Self-Healing Fallbacks:**
  - If Python 3 is absent, displays a native AppleScript dialog offering 1-click browser navigation to the official Python download page.
  - Automatically creates `.venv`, upgrades `pip`, and installs dependencies quietly.
* **Automatic Applications Folder Integration (`install_app_bundle`):**
  - Probes writability of `/Applications`; falls back seamlessly to `$HOME/Applications` for standard accounts without root/sudo access.
  - Constructs `Faery Good Transcriber.app` bundle containing `Info.plist`, `.venv` launcher script, and `faery_icon.icns`.
  - Clears quarantine flags via `xattr -cr` and forces LaunchServices registration (`lsregister -f`) with timestamp touch for immediate Spotlight and Launchpad indexing.

---

## 3. Packaging & Standalone Bundling

* **Build Specification:** `FaeryTranscriber.spec` using PyInstaller 6.x.
* **Entry Point:** Targets `app.py` as the top-level script, collecting all modules under `faery_app/` as hidden imports.
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
* **Status:** 37 passing unit and integration tests (0 failures, 0 errors).
* **Execution:**
  ```bash
  python -m unittest test_app.py
  ```
* **Test Matrix:** 37 comprehensive unit and integration tests covering:
  - Formatter logic (paragraphs, timecodes, markdown).
  - Scratch lifecycle hygiene, isolated directories, and file lock backoff.
  - Auto-update cadence, bundle detection, and offline handling.
  - History indexing, search ranking, and persistence.
  - URL detection across all supported social platforms.
  - Media processor audio extraction and duration parsing.
  - Config manager read, write, and corrupt JSON restoration.
  - Public facade symbol exports (ensuring `app.py` exposes all classes and helpers identically to `faery_app`).
  - macOS Application Integration (`TestMacOSAppIntegration`): platform guard on non-darwin OS, `.app` bundle hierarchy generation, permission fallback to `~/Applications`, frozen bundle replication, and directory writability validation.
