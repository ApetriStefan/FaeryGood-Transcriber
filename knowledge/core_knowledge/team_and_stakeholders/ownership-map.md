# Ownership Map

> **Status:** 🟢 Complete
> **Last Updated:** 2026-11-03

Who owns which component, process, and system. All other Core-Knowledge files refer here when they need to indicate ownership (using roles and links, not names embedded inline).

| Asset | Type | Primary Owner | Secondary | Notes |
|---|---|---|---|---|
| **CustomTkinter GUI (`FaeryTranscriberApp`)** | `component` | Lead Developer | Creator & Brand Owner | User interface layout, widgets, and themes |
| **Inference Engine (`TranscriptionEngine`)** | `component` | Lead Developer | — | faster-whisper CPU model execution |
| **Media Fetcher (`OnlineMediaFetcher`)** | `component` | Lead Developer | — | yt-dlp social media extraction |
| **Scratch Lifecycle (`ScratchLifecycleManager`)** | `component` | Lead Developer | — | Safe temp directory sandbox & cleanup |
| **Ambient Radio (`RadioStationController`)** | `component` | Creator & Brand Owner | Lead Developer | Background audio playback & bumpers |
| **Launchers (`Run_Windows.bat`, `Run_Mac.command`)** | `system` | Lead Developer | — | Self-healing platform runners |
| **Onboarding Guide (`WELCOME_FRIEND.md`)** | `process` | Creator & Brand Owner | Lead Developer | Non-technical creator guide |
| **Quality Verification & Tests (`test_app.py`)** | `process` | Lead Developer | — | Continuous regression testing |

---

## Conventions
- **Asset types:** `component`, `process`, `system`, `integration`, `data-store`
- One primary owner per asset.

_Maintained as part of `team_and_stakeholders/`._
