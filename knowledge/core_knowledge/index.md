# Core-Knowledge Index — Faery Good Transcriber

> **Repository Type:** Standalone Desktop Application (CustomTkinter GUI)
> **Primary Language:** Python 3.10+
> **Target Platforms:** Windows 10/11, macOS Sonoma/Ventura/Monterey
> **Architecture:** Modular package (`faery_app/`) with backwards-compatible facade (`app.py`)
> **Last Updated:** 2026-11-05

---

## Mission

Faery Good Transcriber is a standalone, privacy-first desktop application designed for creators and storytellers. It transcribes English audio/video files, built-in microphone voice recordings (`MicrophoneRecorder`), and social media clips (Instagram Reels, YouTube, TikTok, Facebook) completely offline on the user's local CPU using `faster-whisper` (`small.en` and `base.en`), formats speech into clean paragraphs and timestamped transcripts (`[MM:SS]`), saves outputs to `Documents/Transcriptions`, guarantees zero-residue temporary audio cleanup via `ScratchLifecycleManager`, and provides an ambient background radio player.

---

## Routing Table

| Location | Has answers about | Does NOT have | Read code instead for |
|---|---|---|---|
| [`architecture.md`](architecture.md) | System overview, modular `faery_app` architecture, threading model, audio pipeline, microphone recording, UI layout, `ScratchLifecycleManager`, `AutoUpdater`, self-healing launchers | Line-level event bindings | Function bodies in `faery_app/` and `app.py` |
| [`components/_about.md`](components/_about.md) | Architectural modules: GUI views, inference engine, media extractor, microphone recorder, cookie permission dialog, scratch manager, auto-updater, radio, formatting, contracts | Full source implementations | Specific widget callbacks |
| [`infrastructure/_about.md`](infrastructure/_about.md) | Virtualenv provisioning, PyInstaller bundling specs (`FaeryTranscriber.spec`), platform-specific launchers (`Run_Windows.bat`, `Run_Mac.command`), test coverage | Core UI logic | Build script internals |
| [`processes/_about.md`](processes/_about.md) | Quality verification, scratch hygiene assurance, friend delivery steps, release workflows | Personal notes | Git commit logs |
| [`team_and_stakeholders/`](team_and_stakeholders/_about.md) | Contact registry, team structure, ownership map, stakeholder roles | Code implementation | Repository issues |

---

## Folder Contracts

The single source of truth for repository documentation structure:

- **`components/`**: Defines the system's software modules, their class contracts, boundaries, and thread invariants across `faery_app/`.
- **`infrastructure/`**: Documents execution runtimes, platform-specific launchers, PyInstaller specs, and testing harnesses (37 automated tests).
- **`processes/`**: Standard operating procedures, test verification routines, packaging workflows, and user delivery steps.
- **`team_and_stakeholders/`**: The authoritative registry for people, contact info, team structure, and asset ownership. *(The ONLY directory where personal names may appear).*

---

## Glossary

| Term | Definition |
|---|---|
| **Faery Good Transcriber** | The official desktop transcription application. |
| **faery_app** | The modular Python package containing decoupled subsystems (`config`, `lifecycle`, `models`, `media`, `transcription`, `radio`, `history`, `utils`, `ui`). |
| **app.py** | Backwards-compatible public facade re-exporting all symbols and bootstrapping application startup. |
| **faster-whisper** | CTranslate2-accelerated implementation of OpenAI Whisper running 100% locally on CPU (`int8` quantization) with English-optimized models (`small.en`, `base.en`). |
| **yt-dlp / deno** | Online media extraction stack (`yt-dlp[default]`, `yt-dlp-ejs`, and bundled `deno` runtime) used to fetch temporary audio streams from social URLs and solve YouTube JS challenges. |
| **MicrophoneRecorder** | Built-in microphone voice recording subsystem (`faery_app/media/recorder.py`) capturing 16kHz mono PCM WAV via `sounddevice` into `faery_mic_*` scratch directories. |
| **CookiePermissionDialog** | Modal dialog (`faery_app/ui/dialogs/cookie_permission.py`) gating browser cookie extraction in `Auto / Public` mode when a social clip is behind a login wall. |
| **ScratchLifecycleManager** | Subsystem providing guaranteed failsafe cleanup of temporary audio files (`faery_transcribe_*`, `faery_mic_*`) across normal exits, cancellations, system signals, and crashes. |
| **AutoUpdater** | Background component checking for git and extractor (`yt-dlp[default]`, `yt-dlp-ejs`, `deno`) updates every 7 days when running in a git clone, safely bypassed in standalone frozen bundles. |
| **Self-Healing Launcher** | Platform batch/shell scripts (`Run_Windows.bat`, `Run_Mac.command`) that detect Python, self-provision virtual environments, and alert users via native GUI dialogs. |
| **macOS App Registration** | Automated subsystem (`ensure_macos_app_installed`, `install_app_bundle`) installing `.app` bundles into `/Applications` (or `~/Applications`), clearing quarantine flags, and registering with LaunchServices for Spotlight indexing. |
| **Faery Radio** | Embedded ambient music player (104.9 The Grift FM) with GTA-style station bumpers. |
| **SQLite Database & FTS5** | Embedded database (`~/.faery_transcriber.db`) configured with WAL journal mode (`PRAGMA journal_mode=WAL`) and FTS5 full-text search virtual table (`unicode61` tokenizer), providing crash-safe ACID persistence and sub-millisecond spoken word indexing with automatic migration from legacy JSON. |

---

## Coverage Status

| Area | Status | Last updated | Notes |
|---|---|---|---|
| `architecture.md` | 🟢 Complete | 2026-11-05 | Modular `faery_app` package architecture, scratch lifecycle, SQLite FTS5 database, and launcher specs |
| `components/` | 🟢 Complete | 2026-11-05 | Modular subsystem contracts mapped to `faery_app/` paths, SQLite FTS5 history, and `app.py` facade |
| `infrastructure/` | 🟢 Complete | 2026-11-05 | Windows & Mac self-healing launchers, PyInstaller specs, 41 passing unit/integration tests |
| `processes/` | 🟢 Complete | 2026-11-05 | Friend delivery, 41-test verification routine, scratch hygiene SOPs |
| `team_and_stakeholders/` | 🟢 Complete | 2026-11-05 | Contacts, team structure, and ownership map populated |
