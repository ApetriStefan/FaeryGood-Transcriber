# Infrastructure Directory Contract

This directory documents the deployment, packaging, execution environments, self-healing launchers, and testing tools for the project.

---

## 1. Runtime Environments

* **Supported Python Runtimes:** Python 3.10 to Python 3.13 (x86_64 on Windows; x86_64 and ARM64 Apple Silicon on macOS).
* **Isolation Model:** Dedicated `.venv` virtual environment isolated inside the application root directory.
* **FFmpeg Dependency:** Statically provided through `imageio_ffmpeg` to eliminate any requirement for system-level FFmpeg installation.

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

---

## 3. Packaging & Standalone Bundling

* **Build Specification:** `FaeryTranscriber.spec` using PyInstaller 6.x.
* **Windowed GUI:** Configured with `console=False` to prevent extraneous command prompt windows on end-user machines.
* **Asset Bundling:**
  - Radio audio tracks (`assets/radio/tracks/`) and bumpers (`assets/radio/bumpers/`).
  - Warm UI theme JSON (`assets/faery_warm_theme.json`).
  - Brand icons (`assets/icon.png`, `assets/icon.ico`, `assets/icon.icns`).
  - Bundled binary dependencies (`imageio_ffmpeg` static FFmpeg executable).
* **Standalone Immunity:** In frozen binary mode, `sys.frozen` evaluates to `True`, automatically instructing `AutoUpdater` to skip Git execution.

---

## 4. Test Suite & Quality Verification

* **Framework:** Standard library `unittest` (`test_app.py`).
* **Test Matrix:** 26 comprehensive unit and integration tests covering:
  - Formatter logic (paragraphs, timecodes, markdown).
  - Scratch lifecycle hygiene and file lock backoff.
  - Auto-update cadence, bundle detection, and offline handling.
  - History indexing, search ranking, and persistence.
  - URL detection across all supported social platforms.
