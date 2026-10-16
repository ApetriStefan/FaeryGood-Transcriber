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

## 🍎 Step-by-Step Mac Guide (For Ericka & Beginners)

Even if you have never used Terminal or written a line of code in your life, you can run **Faery Good Transcriber** on your Mac in 2 minutes.

---

### Step 1: Download & Unpack the Studio Folder
1. On GitHub, click the green **Code** button at the top right, then click **Download ZIP**.
2. Go to your **Downloads** folder in Finder.
3. Double-click `FaeryGood-Transcriber-main.zip` to unzip it.
4. Move the unzipped `FaeryGood-Transcriber` folder into your **Documents** or **Applications** folder (or keep it on your **Desktop**).

---

### Step 2: Ensure Python 3 is on Your Mac (One-Time Check)
Modern Macs running macOS Sonoma often don't have Python 3 pre-installed.
- If you don't have Python 3, don't worry: when you launch `Run_Mac.command`, it will automatically show a friendly alert with a direct button to download it.
- Or, install it directly in 1 minute from **[python.org/downloads](https://www.python.org/downloads/)** (choose the latest macOS 64-bit universal installer and follow the standard installer prompts).

---

### Step 3: Launch with 1-Click!
Open the `FaeryGood-Transcriber` folder in Finder and simply **double-click**:

👉 **`Run_Mac.command`**

That's it! A Terminal window will open and automatically:
- Create a private isolated virtual environment (`.venv`).
- Install all necessary dependencies (`customtkinter`, `faster-whisper`, `imageio-ffmpeg`, `pillow`).
- Launch the **Faery Good Transcriber** studio window!

> 💡 **First-Time Launch Note:** On the very first launch, it will take about 1–2 minutes to configure dependencies and download the Whisper AI model. After that, it launches in seconds and works **100% offline** without needing internet!

---

### 🛡️ macOS Security & Permission Tips (If macOS Asks)

Apple has strict security rules for files downloaded from the web. If you encounter either of these prompts, here is the 10-second fix:

#### 1. "Cannot be opened because it is from an unidentified developer"
- **Fix:** Don't double-click. Instead, **Right-Click** (or hold `Control` and click) on `Run_Mac.command`, then select **Open**. In the dialog that appears, click **Open**. macOS will remember your choice and you won't be asked again!

#### 2. "The file could not be executed because you do not have appropriate access privileges"
- If executable permissions were stripped by your zip unarchiver:
  1. Open the **Terminal** app (press `⌘ + Space`, type `Terminal`, and press `Enter`).
  2. Copy and paste this single line, then press `Enter`:
     ```bash
     chmod +x ~/Downloads/FaeryGood-Transcriber*/*.command
     ```
     *(Or simply type `chmod +x `, drag `Run_Mac.command` into the Terminal window, and press `Enter`)*.
  3. Now double-click `Run_Mac.command` in Finder!

---

### 📦 Option 2: Build a Native `.app` & Drag-and-Drop `.dmg` Installer

If you prefer having a true Mac application that you can drag into `/Applications` and pin to your Dock just like Apple Pages or Spotify:

1. Inside the project folder, double-click **`Create_Mac_DMG.command`** (or right-click → Open).
2. It compiles `FaeryTranscriber.app` with the official Faery Good squircle icon and automatically produces:
   ```text
   FaeryTranscriber-Intel-Mac.dmg
   ```
3. Double-click the `.dmg` file:
   - A macOS installer window opens.
   - Drag **Faery Good Transcriber** into the **Applications** folder shortcut.
   - Done! You can now launch it anytime from **Launchpad**, **Spotlight** (`⌘ Space`), or keep it in your **Dock**.

---

### 🎬 How to Transcribe a Clip or Social Link (Creator Workflow)

1. **Choose Your Source (Local File OR Social Link):**
   - **Option A — Paste a Social Link:** Copy any **Instagram Reel**, **YouTube video/Short**, **TikTok**, or **Facebook Reel/video** link and click **📋 Paste Link** (or press `⌘L` / `Ctrl+L`). The audio will be fetched automatically into a temporary folder and deleted immediately after transcription!
     - *Tip for Login-Walled Instagram/Facebook Reels:* If a Reel asks for login, use the **🔐 Social Login** dropdown (`Auto / Public`, `Safari`, `Chrome`, `Firefox`, `Edge`) so it can use your browser session seamlessly.
   - **Option B — Select a Local File:** Click **Select Video or Audio…** (or press `⌘O`). Pick any video or audio file on your computer (`.mp4`, `.mov`, `.m4a`, `.mp3`, `.wav`, `.mkv`).
2. **Choose Accuracy Engine:**
   - **High Accuracy (small.en - Recommended):** Best for clear punctuation, accuracy, and longer videos.
   - **Standard (base.en - Fast):** 2x faster, great for quick 30-second reels.
3. **Generate:** Click **✨ Generate Transcript** (or press `⌘Return`).
   - If you pasted a link, the download progress streams live (`0% -> 100%`), converts to temporary 16kHz audio, and immediately deletes the raw download before transcribing.
   - The Cancel button allows you to stop anytime and immediately wipes any temporary files.
   - A gentle chime rings when done!
4. **Copy & Share:**
   - Toggle between **📄 Clean Paragraphs** (natural speech pauses for social captions) and **⏱️ Timecoded (YouTube)** (with exact `00:00 - ...` timestamps for video chapters).
   - Click **📋 Copy to Clipboard** (or press `⌘C`).
   - Click **💾 .txt** or **📝 .md** to save directly into your output folder.

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
| **Paste Social Link (IG/YT/TikTok/FB)** | `⌘L` | `Ctrl+L` |
| **Open Output Folder** | `⇧⌘O` | `Ctrl+Shift+O` |
| **Generate Transcript** | `⌘Return` | `Ctrl+Enter` |
| **Quick Save (.txt / Edits)** | `⌘S` | `Ctrl+S` |
| **Select All Text** | `⌘A` | `Ctrl+A` |
| **Copy Active Transcript** | `⌘C` | `Ctrl+C` |
| **Transcribe Studio Tab** | `⌘1` | `Ctrl+1` |
| **History Library Tab** | `⌘2` | `Ctrl+2` |
| **Exit Application** | `⌘Q` | `Alt+F4` |

