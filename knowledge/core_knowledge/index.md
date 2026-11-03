# Core-Knowledge Index — Faery Good Transcriber

> **Repository Type:** Standalone Desktop Application (CustomTkinter GUI)
> **Primary Language:** Python 3.10+
> **Target Platforms:** Windows 10/11, macOS Sonoma/Ventura/Monterey
> **Last Updated:** 2026-11-03

---

## Mission

Faery Good Transcriber is a standalone, privacy-first desktop application designed for creators and storytellers. It transcribes audio/video files and social media clips (Instagram Reels, YouTube, TikTok, Facebook) completely offline on the user's local CPU using `faster-whisper`, formats speech into clean paragraphs and timecoded chapters, saves outputs to `Documents/Transcriptions`, guarantees zero-residue temporary audio cleanup via `ScratchLifecycleManager`, and provides an ambient background radio player.

---

## Routing Table

| Location | Has answers about | Does NOT have | Read code instead for |
|---|---|---|---|
| [`architecture.md`](architecture.md) | System overview, threading model, audio pipeline, UI layout, `ScratchLifecycleManager`, `AutoUpdater`, self-healing launchers | Line-level event bindings | Function bodies in `app.py` |
| [`components/_about.md`](components/_about.md) | Architectural modules: GUI, inference engine, media extractor, scratch manager, auto-updater, radio, formatting | Full source implementations | Specific widget callbacks |
| [`infrastructure/_about.md`](infrastructure/_about.md) | Virtualenv provisioning, PyInstaller bundling specs, platform-specific launchers (`Run_Windows.bat`, `Run_Mac.command`), test coverage | Core UI logic | Build script internals |
| [`processes/_about.md`](processes/_about.md) | Quality verification, scratch hygiene assurance, friend delivery steps, release workflows | Personal notes | Git commit logs |
| [`team_and_stakeholders/`](team_and_stakeholders/_about.md) | Contact registry, team structure, ownership map, stakeholder roles | Code implementation | Repository issues |

---

## Folder Contracts

The single source of truth for repository documentation structure:

- **`components/`**: Defines the system's software modules, their class contracts, boundaries, and thread invariants.
- **`infrastructure/`**: Documents execution runtimes, platform-specific launchers, PyInstaller specs, and testing harnesses.
- **`processes/`**: Standard operating procedures, test verification routines, packaging workflows, and user delivery steps.
- **`team_and_stakeholders/`**: The authoritative registry for people, contact info, team structure, and asset ownership. *(The ONLY directory where personal names may appear).*

---

## Glossary

| Term | Definition |
|---|---|
| **Faery Good Transcriber** | The official desktop transcription application. |
| **faster-whisper** | CTranslate2-accelerated implementation of OpenAI Whisper running 100% locally on CPU. |
| **yt-dlp** | Standalone online media extraction tool used to fetch temporary audio streams from social URLs. |
| **ScratchLifecycleManager** | Subsystem providing guaranteed failsafe cleanup of temporary audio files across normal exits, cancellations, system signals, and crashes. |
| **AutoUpdater** | Background component checking for updates every 7 days when running in a git clone, safely bypassed in standalone frozen bundles. |
| **Self-Healing Launcher** | Platform batch/shell scripts (`Run_Windows.bat`, `Run_Mac.command`) that detect Python, self-provision virtual environments, and alert users via native GUI dialogs. |
| **Faery Radio** | Embedded ambient music player (104.9 The Grift FM) with GTA-style station bumpers. |

---

## Coverage Status

| Area | Status | Last updated | Notes |
|---|---|---|---|
| `architecture.md` | 🟢 Complete | 2026-11-03 | Full system architecture, scratch lifecycle, and launcher specs |
| `components/` | 🟢 Complete | 2026-11-03 | GUI, inference engine, scratch manager, updater, radio |
| `infrastructure/` | 🟢 Complete | 2026-11-03 | Windows & Mac self-healing launchers, PyInstaller specs |
| `processes/` | 🟢 Complete | 2026-11-03 | Friend delivery, test verification, scratch hygiene routines |
| `team_and_stakeholders/` | 🟢 Complete | 2026-11-03 | Contacts, team structure, and ownership map populated |
