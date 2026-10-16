# 🦋 Faery Good Transcriber

A bespoke, whimsical, 100% private on-device desktop transcription studio custom-crafted for **Ericka** and **[Faery Good](https://faerygood.com/)** (*"Small Batch, Whimsical Apothecary for the Tender Hearted — Whimsy is Power"*).

Designed specifically for effortless **Instagram Reels** captions and **YouTube** video chapters, developed and tested on **Windows 11**, and engineered to run natively on **Intel-based Macs** (macOS Sonoma, `x86_64`, 4-core Intel Core i7, 32GB RAM).

---

## 🌸 Custom Faery Good Art Direction & Brand Identity

Every visual element is custom-tailored to match **[FaeryGood.com](https://faerygood.com/)**:
- **Authentic Color Palette:**
  - **Faery Royal Purple (`#7A2DB4`):** Primary typography, interactive pill buttons, borders, and progress indicators.
  - **Soft Lavender Mist (`#EDE6FF`):** Signature dreamy window backdrop (paired with Deep Enchanted Plum `#191024` in Dark Mode).
  - **Warm Apothecary Cream (`#FCF4ED`):** Botanical card surfaces and input fields.
  - **Petal Rose Mist (`#FCECF5`):** Highlighted transcript cards and secondary accents.
  - **Herbal Sage Green (`#7EA156`):** Visual confirmation feedback (`✓ Copied!`, `✓ Saved!`).
- **Official Brand Artwork & Custom Icon (`assets/`):**
  - **`faery_icon.icns` / `faery_icon.ico` / `faery_icon.png`:** Custom 1024×1024 macOS squircle & Windows application icon featuring Ericka's signature watercolor fairy illustration over a lavender-to-rose gradient with gold/lilac sparkles.
  - **`faery_logo_light.png` & `faery_logo_dark.png`:** Official hand-lettered cursive *"Faery Good"* wordmark rendered in high-DPI for both Light and Dark themes.
  - **`faery_mascot.png`:** Official watercolor fairy illustration displayed in the header banner and creator dialogs.
  - **Botanical Section Icons:** Official butterfly (`faery_butterfly`), apothecary mortar & pestle (`faery_mortar`), and herbal sprig (`faery_sprig`) illustrations adorning each studio card.
- **Typography & Pill Silhouettes:** Editorial serif headings (`Georgia` / `Fraunces` style), clean geometric body copy, and rounded 40px-style pill buttons (`corner_radius=16..18`).

---

## 🎯 Designed for Non-Technical Creators

- **1-Click Launchers:** Simply double-click `Run_Mac.command` on macOS or `Run_Windows.bat` on Windows. All environment setup and dependencies are handled automatically.
- **1-Click DMG Installer:** Double-click `Create_Mac_DMG.command` on macOS to generate a drag-and-drop installer (`FaeryTranscriber-Intel-Mac.dmg`) complete with the custom **Faery Good** volume icon and `/Applications` shortcut.
- **Native macOS Menu Bar & Shortcuts:** Integrated global macOS menu bar with `⌘O` (Open Media), `⌘Return` (Generate), `⌘S` (Save), `⌘A` (Select All), `⌘C` (Copy), `⌘1` (Transcribe), and `⌘2` (History).
- **Audio Completion Chime:** Gentle macOS chime (`Glass.aiff`) alerts you when a transcription completes.
- **Smart Directory Memory:** Automatically remembers your last used media folder and defaults to `~/Movies`, `~/Downloads`, or `~/Desktop`.
- **100% On-Device Privacy:** All transcription runs strictly on the Intel CPU (`int8`). Zero audio or video ever leaves your computer.

---

## 🚀 Key Architectural Highlights

1. **Modern High-DPI GUI:** Built with `customtkinter` and `Pillow` featuring high-DPI `CTkImage` brand assets, custom `faery_good_theme.json`, and Light/Dark/System theme switching.
2. **Zero-Dependency Audio Pipeline:** Uses the bundled static FFmpeg binary from `imageio-ffmpeg` via `imageio_ffmpeg.get_ffmpeg_exe()`. No system-level FFmpeg installation or `brew install` required.
3. **Optimized Transcription Engine:** Uses `faster-whisper` (CTranslate2) running strictly on `device="cpu"` with `compute_type="int8"` and `cpu_threads=4` for maximum Intel i7 throughput.
4. **100% Scratch File Hygiene:** Uses Python's `tempfile.TemporaryDirectory()` context manager. Scratch 16kHz mono WAV files are guaranteed to be purged immediately upon completion, error, or cancellation. Zero leftover files on disk.
5. **Non-blocking Multi-Threading:** Audio extraction and transcription run on a dedicated background worker thread with thread-safe UI dispatches, eliminating UI freezes and macOS spinning beachballs.
6. **Smart Pause & Acoustic Pacing Formatter:** Breaks text into natural, readable paragraphs by detecting acoustic silences (pauses $\ge 1.0$s) and sentence pacing, streaming live in real time.
7. **Dual-View Switcher (Clean Paragraphs & Timecoded):** Instant one-click toggle right above the editor between `📄 Clean Paragraphs` (for Instagram Reels & blog posts) and `⏱️ Timecoded (YouTube)` (for YouTube video description chapters).
8. **Persistent History Library (CRUD):** Full transcript catalog in `~/.faery_transcriptions_history.json` with search, rename, direct editing, and file deletion.
9. **Overwrite Protection:** Detects if a clip was previously transcribed and prompts to overwrite or create a numbered duplicate (`_1`).

---

## 📦 Project File Structure

```text
TranscriptionEngine/
├── app.py                      # Complete standalone application code
├── assets/                     # Official Faery Good icons, logos, artwork & theme
│   ├── faery_icon.icns         # macOS native application & DMG icon
│   ├── faery_icon.ico          # Windows native multi-size application icon
│   ├── faery_icon.png          # High-res 1024x1024 squircle app icon
│   ├── faery_mascot.png        # Watercolor fairy mascot illustration
│   ├── faery_logo_light.png    # Cursive "Faery Good" wordmark (Light mode)
│   ├── faery_logo_dark.png     # Cursive "Faery Good" wordmark (Dark mode)
│   ├── faery_butterfly_*.png   # Whimsical butterfly section icon
│   ├── faery_mortar_*.png      # Apothecary mortar & pestle section icon
│   ├── faery_sprig_*.png       # Botanical herbal sprig section icon
│   └── faery_good_theme.json   # CustomTkinter theme matching FaeryGood.com
├── requirements.txt            # Production dependencies
├── FaeryTranscriber.spec       # PyInstaller packaging configuration
├── test_app.py                 # Automated test suite
├── Run_Mac.command             # 1-Click double-clickable Mac launcher
├── Build_Mac_App.command       # 1-Click standalone .app bundle builder
├── Create_Mac_DMG.command      # 1-Click drag-and-drop .dmg installer creator
├── Run_Windows.bat             # 1-Click double-clickable Windows launcher
└── README.md                   # User and deployment documentation
```

---

## 🍎 macOS Usage (Non-Technical 1-Click Workflow)

### Option 1: 1-Click Launch (No Terminal Needed)
1. Download or copy the `TranscriptionEngine` folder to your Mac (e.g. in `~/Documents` or `~/Desktop`).
2. Double-click **`Run_Mac.command`** in Finder.
3. The script automatically sets up the environment in the background and launches **Faery Good Transcriber**.

### Option 2: 1-Click Standalone `.app` or `.dmg` Installer
1. Double-click **`Create_Mac_DMG.command`** in Finder.
2. The script compiles `FaeryTranscriber.app` with the custom Faery Good icon, clears Gatekeeper quarantine flags (`xattr -cr`), and creates:
   ```text
   FaeryTranscriber-Intel-Mac.dmg
   ```
3. Double-click the `.dmg` file, drag **FaeryTranscriber** into **Applications**, and launch it from Launchpad, Dock, or Spotlight!

---

## 🪟 Windows 11 Usage (Development & Testing)

1. Double-click **`Run_Windows.bat`** in File Explorer, or open PowerShell:
   ```powershell
   cd d:\TranscriptionEngine
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
2. Run the automated test suite:
   ```powershell
   python test_app.py
   ```
3. Launch the app:
   ```powershell
   python app.py
   ```

---

## ⌨️ Native Keyboard Shortcuts

| Action | macOS Shortcut | Windows Shortcut |
| :--- | :--- | :--- |
| **Select Media File** | `⌘O` | `Ctrl+O` |
| **Open Output Folder** | `⇧⌘O` | `Ctrl+Shift+O` |
| **Generate Transcript** | `⌘Return` | `Ctrl+Enter` |
| **Quick Save (.txt / Edits)** | `⌘S` | `Ctrl+S` |
| **Select All Text** | `⌘A` | `Ctrl+A` |
| **Copy Active Transcript** | `⌘C` | `Ctrl+C` |
| **Transcribe Studio Tab** | `⌘1` | `Ctrl+1` |
| **History Library Tab** | `⌘2` | `Ctrl+2` |
| **Exit Application** | `⌘Q` | `Alt+F4` |

