# Processes Directory Contract

This directory defines key engineering, delivery, and verification workflows.

---

## Standard Workflows

### 1. Friend Delivery & Onboarding Workflow
- Ensure `WELCOME_FRIEND.md` is present at the repository or bundle root.
- Instruct recipient to double-click the self-healing launcher:
  - Windows: `Run_Windows.bat`
  - macOS: `Run_Mac.command`
- On launch, the launcher manages `.venv` creation, installs dependencies, and runs the application with zero user configuration required.
- If system dependencies are missing, native GUI alerts guide the user.

### 2. Quality Verification Workflow
- Execute full test suite prior to committing or creating distribution builds:
  ```bash
  python -m unittest test_app.py
  ```
- Verify all 41 test cases pass without regressions.
- Verify GUI launches cleanly without unhandled console exceptions.

### 3. Scratch Hygiene Assurance Workflow
- Verify `ScratchLifecycleManager` operates under all exit conditions:
  - Normal transcription exit: temporary directories (`faery_transcribe_*`, `faery_mic_*`) deleted immediately.
  - User cancellation: active scratch directory purged on cancel signal.
  - Process interruption: `atexit` and signal handlers clean active directories.
  - Startup sweeper: orphaned folders matching `faery_transcribe_*` and `faery_mic_*` and stale Hugging Face cache fragments are cleaned on app boot.

### 4. Release & Standalone Packaging Workflow
- On macOS: Execute `Build_Mac_App.command` followed by `Create_Mac_DMG.command`.
- On Windows: Run PyInstaller with `FaeryTranscriber.spec`.
- Verify standalone bundle bypass in `AutoUpdater` (`sys.frozen == True`).
