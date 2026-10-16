# 🦋 Faery Good Transcriber

> *"Small Batch, Whimsical Apothecary for the Tender Hearted — Whimsy is Power"*  
> Custom-crafted for **Ericka** & **[Faery Good](https://faerygood.com/)**

A delightful, 100% private, on-device desktop transcription studio and historical library. Built specifically for **Instagram Reels captions**, **TikTok subtitles**, and **YouTube video chapters**. Developed and tested on **Windows 11**, and engineered to run natively on **Intel-based Macs** (macOS Sonoma, `x86_64`, 4-core Intel Core i7, 32GB RAM).

---

## ✨ Features at a Glance

* **100% On-Device & Private:** Powered by `faster-whisper` running locally on your computer's CPU (`int8`). Your videos, audio, and personal voice memos **never** leave your machine or get sent to the cloud.
* **Paste Any Social Link (Instagram, YouTube, TikTok, Facebook):** Simply copy a link and click **`📋 Paste Link`** (`⌘L` / `Ctrl+L`). Audio is downloaded strictly into a temporary scratch space, converted, transcribed, and **immediately destroyed**—leaving zero temporary media files on disk.
* **Smart Pause Paragraphs & YouTube Chapters:**
  * **`📄 Clean Paragraphs`:** Automatically detects natural speech pauses ($\ge 1.0$s) to format speech into clean, readable paragraphs ready to paste into Instagram captions or blog posts.
  * **`⏱️ Timecoded (YouTube)`:** Formats timestamps (`[00:15] ...`) ready to paste directly into YouTube video descriptions as clickable chapters.
* **Persistent History Library & Smart Full-Text Search:**
  * View, search, rename, edit, copy, and delete all your past transcripts in the **`📜 History`** tab.
  * **Full-Text Spoken Search:** Search not only by title or date, but **by any word spoken in the audio**!
  * **Speech Snippet Previews:** Results highlight the exact sentence from the transcript where the spoken words were detected (e.g. `💬 "...save for the muffled rhythm of rain..."`).
  * Spotlight-style search bar with real-time filtering and an instant `✕` clear pill button.
* **Automatic Weekly Updates (Only on Launch):** When the application is launched, it checks whether 7 days have elapsed since the last check. If an internet connection is available, it automatically pulls updates from the GitHub repository (`main` branch) in the background. You can also trigger an immediate check at any time from **Help → Check for Updates from GitHub...**.
* **📻 Ambient Faery Radio (104.9 The Grift FM):** Toggle on the radio switch (`⌘R` / `Ctrl+R`) to summon a retro-modern ambient music player docked at the bottom of the screen. Plays original apothecary tracks with GTA-style station DJ breaks, high-probability satirical legal disclaimers, and pre-song station bumpers. Completely disappears when toggled off to preserve 100% of your workspace.
* **Overwrite Protection:** If you transcribe the same clip a second time, the studio will ask whether you want to overwrite the old file or create a numbered duplicate (`_1`).
* **Bespoke Faery Good Aesthetics:** Custom-tailored to [FaeryGood.com](https://faerygood.com/) with watercolor fairy icons, whimsical butterfly accents, soft lavender backgrounds, and apothecary cream cards.

---

## 🌸 Faery Good Brand Art Direction

Every screen and control is designed to reflect Ericka's whimsical aesthetic:
* **Faery Royal Purple (`#7A2DB4`):** Primary typography, interactive pill buttons, and accent borders.
* **Soft Lavender Mist (`#EDE6FF`):** Signature dreamy background (paired with Enchanted Plum `#191024` in Dark Mode).
* **Warm Apothecary Cream (`#FCF4ED`):** Botanical card surfaces and input areas.
* **Petal Rose Mist (`#FCECF5`):** Highlighted transcript selection cards.
* **Herbal Sage Green (`#7EA156`):** Gentle visual confirmation pills (`✓ Copied!`, `✓ Saved!`).
* **Official Artwork (`assets/`):** Custom 1024×1024 macOS squircle app icon (`faery_icon.icns`), cursive wordmarks, watercolor fairy mascot, and apothecary botanical icons (butterfly, mortar & pestle, herbal sprig).

---

## 🧠 How It Works Under the Hood

Faery Good Transcriber is designed to be completely self-contained, idiot-proof, and private:

1. **Audio Extraction & Resampling (Static FFmpeg):**  
   Whether you select a 4K `.mov` video, an `.mp4` reel, or paste a web link, the bundled static FFmpeg binary extracts the audio and resamples it into a clean **16,000Hz mono 16-bit PCM WAV stream**. This matches the exact acoustic resolution expected by Whisper's neural network.
2. **On-Device AI Speech Recognition (`faster-whisper`):**  
   Instead of uploading your voice to an external server or charging per-minute API fees, the app runs OpenAI's Whisper model locally on your computer's CPU (`int8` quantization with 4 parallel worker threads). It translates spoken audio directly into text right inside your machine.
3. **Smart Pause & Acoustic Pacing Formatter:**  
   Traditional speech-to-text engines output an overwhelming "wall of text" without natural breaks. Faery Good Transcriber analyzes acoustic pauses in real time: whenever a silence of $\ge 1.0$ second is detected, it automatically inserts a paragraph break. The result reads like natural human writing, matching your real vocal pacing.
4. **Dual Output (Social Captions & YouTube Chapters):**  
   Every transcription simultaneously creates:
   * **`📄 Clean Paragraphs`:** Natural pauses for Instagram captions, TikTok scripts, and newsletters.
   * **`⏱️ Timecoded`:** Exact timestamps (`[00:15] ...`) formatted for YouTube video description chapters.
   * **`📝 Markdown`:** A master document with complete metadata and YouTube chapters saved to your output folder.
5. **100% Scratch Audio Hygiene:**  
   All temporary audio processing and online downloads occur strictly inside Python's `tempfile.TemporaryDirectory(prefix="faery_transcribe_")`. As soon as transcription completes (or if you click Cancel), all scratch audio is immediately deleted. Zero temporary media files remain on your disk.

---

## 🔐 What is "Social Login" and What Is It For?

Under **Studio Preferences**, you'll see a setting labeled **`Social Login`** with options like `Auto / Public (Recommended)`, `Safari (macOS)`, `Chrome`, `Firefox`, and `Edge`.

### Why is this needed?
Platforms like **Instagram** and **Facebook** often place Reels and videos behind a "Login Wall"—especially if a reel is from a private account, contains copyrighted background music, or if Instagram detects automated web traffic. When this happens, Instagram blocks public access with an error like *"Login required"* or *"Sign in to confirm you're not a bot"*.

### How does Social Login solve this safely?
Unlike shady apps or downloaders that ask you to type your personal Instagram username and password into their app (which is dangerous and could compromise your account):
* **Faery Good Transcriber NEVER asks for your password.**
* Instead, it uses `yt-dlp`'s secure cookie extraction to borrow the existing session cookies from the web browser you already use on your computer (`Safari` on Mac, `Chrome`, `Firefox`, etc.).
* Because you are already logged into Instagram in your web browser, the app can fetch the temporary audio stream seamlessly as if you were viewing it yourself!

### Which setting should you use?
* **`Auto / Public (Recommended)`:** Keep this selected by default! The app will always download public clips anonymously without touching any browser. It will only attempt to read browser cookies if Instagram specifically blocks access with a login wall.
* **`Safari (macOS)` / `Chrome` / `Firefox`:** If an Instagram Reel fails with a "Login required" message, simply switch this dropdown to the browser where you are logged into Instagram, and click **Generate Transcript** again!

---

## 🍎 2-Minute Mac Beginner's Guide (Idiot-Proof)

Even if you have never opened the Terminal or written a single line of code in your life, you can run **Faery Good Transcriber** on your Mac in under two minutes.

---

### Step 1: Download & Unpack the Project
1. At the top of this GitHub repository page, click the green **`Code`** button.
2. Click **`Download ZIP`**.
3. Open your Mac's **Downloads** folder in Finder.
4. Double-click the downloaded `.zip` file to unpack it into a folder named `FaeryGood-Transcriber`.
5. *(Recommended)* Drag the `FaeryGood-Transcriber` folder into your **Documents** or **Applications** folder.

---

### Step 2: Ensure Python 3 is on Your Mac (One-Time Check)
Most modern Macs running macOS Sonoma require a standard Python 3 installation:
* If you already have Python 3, you are all set!
* If you aren't sure, don't worry: when you launch the app in Step 3, it will automatically detect if Python is missing and show a friendly alert with a direct button to download it.
* You can also download it directly in 60 seconds from **[python.org/downloads](https://www.python.org/downloads/)** (choose the latest macOS 64-bit universal installer and follow the standard on-screen prompts).

---

### Step 3: Launch with 1-Click!
Open the `FaeryGood-Transcriber` folder in Finder and simply **double-click**:

👉 **`Run_Mac.command`**

A Terminal window will open and automatically do everything for you:
1. Creates your isolated, private virtual environment (`.venv`).
2. Installs required dependencies (`customtkinter`, `faster-whisper`, `imageio-ffmpeg`, `pillow`, `yt-dlp`).
3. Launches **Faery Good Transcriber**!

> [!NOTE]
> **First-Time Launch Note:** On the very first run, it takes about 1–2 minutes to set up the dependencies and download the Whisper AI model. After that, it launches in seconds and works **100% offline** without needing an internet connection!

---

### 🛡️ macOS Security & Permission Tips (If Mac Asks)

Apple has strict security rules for files downloaded from the web. If you see either of these prompts, here is how to resolve them in seconds:

#### 1. "Cannot be opened because it is from an unidentified developer"
* **Fix:** Don't double-click. Instead, **Right-Click** (or hold `Control` and click) on `Run_Mac.command`, then click **Open**. In the pop-up dialog, click **Open**. macOS will remember your permission forever!

#### 2. "The file could not be executed because you do not have appropriate access privileges"
* If your unarchiver stripped the executable permissions:
  1. Open the **Terminal** app (press `⌘ + Space`, type `Terminal`, and press `Enter`).
  2. Paste this single line and press `Enter`:
     ```bash
     chmod +x ~/Downloads/FaeryGood-Transcriber*/*.command
     ```
     *(Or type `chmod +x `, drag `Run_Mac.command` into the Terminal window, and press `Enter`)*.
  3. Now double-click `Run_Mac.command` in Finder!

---

### 📦 Optional: Create a Drag-and-Drop Mac App & DMG
If you want **Faery Good Transcriber** installed in your `/Applications` folder with a true Mac icon pinned to your Dock:

1. Inside the project folder, double-click **`Create_Mac_DMG.command`** (or Right-Click → Open).
2. It compiles the standalone `FaeryTranscriber.app` and produces:
   ```text
   FaeryTranscriber-Intel-Mac.dmg
   ```
3. Double-click the `.dmg` file and drag **Faery Good Transcriber** into the **Applications** folder shortcut.
4. You can now open it from **Launchpad**, **Spotlight** (`⌘ Space`), or keep it in your **Dock** just like Spotify or Pages!

---

## 🎬 How to Use the App (Creator Workflows)

### Workflow 1: Transcribe a Social Media Clip (Instagram, TikTok, YouTube, Facebook)
1. In your browser or phone, copy the link of any **Instagram Reel**, **YouTube video/Short**, **TikTok**, or **Facebook video**.
2. In Faery Good Transcriber, click **`📋 Paste Link`** (or press `⌘L` on Mac / `Ctrl+L` on Windows).
3. *(Optional for Login-Walled Reels):* If an Instagram or Facebook reel requires an account to view, choose your logged-in browser in the **`🔐 Social Login`** dropdown (`Auto / Public`, `Safari`, `Chrome`, `Firefox`, `Edge`).
4. Click **`✨ Generate Transcript`** (or press `⌘Return` / `Ctrl+Enter`).
   * The app downloads the temporary audio stream, converts it, immediately wipes the download from disk, and streams the transcript live into your editor.
   * When complete, a gentle chime rings!
5. Toggle between **`📄 Clean Paragraphs`** (for social captions) and **`⏱️ Timecoded`** (for YouTube chapters).
6. Click **`📋 Copy to Clipboard`** (`⌘C`) and paste it directly into your post!

---

### Workflow 2: Transcribe a Local Video or Voice Memo
1. Click **`Select Video or Audio…`** (or press `⌘O` / `Ctrl+O`).
2. Choose any video or audio file on your computer (`.mp4`, `.mov`, `.m4a`, `.mp3`, `.wav`, `.mkv`).
3. Choose your **Transcription Engine**:
   * **`High Accuracy (small.en - Recommended)`:** Best punctuation, vocabulary, and grammar.
   * **`Standard (base.en - Fast)`:** 2x faster, ideal for quick 30-second reels.
4. Click **`✨ Generate Transcript`** (`⌘Return`).
5. Your formatted text files (`.txt`) and Markdown file (`.md`) are automatically saved to your output directory (`~/Documents/Transcriptions/` by default).

---

### Workflow 3: Explore & Search Your Library (History Tab)
1. Click the **`📜 History`** tab at the top (or press `⌘2` / `Ctrl+2`).
2. All your previous transcripts appear in an Apple-style list on the left.
3. **Smart Full-Text Search:**
   * Type in the search box: you can search by **title**, **date**, **file name**, or **any word spoken in the audio**!
   * If a match was found in the spoken text, the card displays a live quote: `💬 "...muffled rhythm of rain lashing the floor..."`.
   * Press `Enter` to open the first result, or press `Escape` (or click `✕`) to clear the search.
4. **CRUD Actions:**
   * **Edit & Save:** Click into any transcript, make text edits, and click **`💾 Save Edits`** (`⌘S`).
   * **Rename:** Click **`✏️ Rename`** to rename the transcript and all corresponding files on disk.
   * **Copy:** Click **`📋 Copy`** to grab the text.
   * **Open File:** Click **`↗ Open File`** to view it in your Mac's default text editor.
   * **Delete:** Click **`🗑 Delete`** to permanently purge the files from disk.

---

## 🪟 Windows 11 Usage

1. Double-click **`Run_Windows.bat`** in File Explorer, or run in PowerShell:
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

## ⌨️ Keyboard Shortcuts Reference

| Action | macOS Shortcut | Windows Shortcut |
| :--- | :--- | :--- |
| **Select Media File** | `⌘O` | `Ctrl+O` |
| **Paste Social Link (IG/YT/TikTok/FB)** | `⌘L` | `Ctrl+L` |
| **Open Output Folder in Finder / Explorer** | `⇧⌘O` | `Ctrl+Shift+O` |
| **Generate Transcript** | `⌘Return` | `Ctrl+Enter` |
| **Quick Save (.txt or History edits)** | `⌘S` | `Ctrl+S` |
| **Select All Text in Active Editor** | `⌘A` | `Ctrl+A` |
| **Copy Active Transcript** | `⌘C` | `Ctrl+C` |
| **Switch to Transcribe Studio Tab** | `⌘1` | `Ctrl+1` |
| **Switch to History Library Tab** | `⌘2` | `Ctrl+2` |
| **Toggle Ambient Faery Radio** | `⌘R` | `Ctrl+R` |
| **Clear History Search** | `Escape` | `Escape` |
| **Quit Application** | `⌘Q` | `Alt+F4` |

---

## ❓ Frequently Asked Questions (FAQ)

#### Q: Where are my transcript files stored?
> By default, all transcripts are saved in your **`Documents/Transcriptions`** folder. You can change this anytime with one click by clicking **`Browse…`** in the Transcribe Studio tab.

#### Q: Does this app upload my voice or videos to the internet?
> **No, never.** All audio extraction and transcription run 100% locally on your computer's CPU. No audio, video, or text is ever sent to any third-party server or cloud AI provider.

#### Q: How does the social link feature work?
> The app uses `yt-dlp` and a bundled static FFmpeg binary to extract only the audio stream directly into a private temporary folder (`tempfile.TemporaryDirectory`). Once the speech engine finishes transcribing, the temporary audio is deleted immediately. Zero video or audio clutter remains on your hard drive.

#### Q: An Instagram or Facebook reel says "Login required". How do I transcribe it?
> In the **`🔐 Social Login`** dropdown under preferences, select the browser where you are logged into your account (e.g. `Safari (macOS)` or `Chrome`), then click **`Generate Transcript`** again. The app will securely use your browser's existing session cookies without needing you to enter your password.

#### Q: How do automatic updates work?
> **Only when you launch the app**, it checks if 7 days have passed since the previous check. If your computer is connected to the internet, it runs a background check to pull any new updates from GitHub (`origin main`). It will never interrupt you with constant checks while you are using the app. You can also manually check anytime via **Help → Check for Updates from GitHub...**.

#### Q: What is 📻 Faery Radio (104.9 The Grift FM)?
> It's an ambient, built-in music player featuring original tracks (`assets/music`). When you toggle the **`📻 Radio`** switch in the top toolbar (or press `⌘R` / `Ctrl+R`), the player docks gracefully at the bottom of the window with full playback and volume controls. Between songs, you'll hear GTA-style DJ station interludes (with anti-repeat protection), satirical Legal Disclaimers, and pre-song station bumpers! When switched off, it vanishes completely so your workspace stays 100% clean.

---

## 📦 Project File Map

```text
TranscriptionEngine/
├── app.py                      # Complete standalone application code & GUI
├── assets/                     # Official Faery Good icons, logos, artwork & theme
│   ├── music/                  # Original ambient tracks (9 songs)
│   ├── announcer/              # GTA-style DJ station clips, disclaimers & bumpers
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
├── requirements.txt            # Production dependencies (including pygame)
├── FaeryTranscriber.spec       # PyInstaller standalone packaging specification
├── test_app.py                 # Automated unit test suite (23 tests)
├── Run_Mac.command             # 1-Click double-clickable Mac launcher
├── Build_Mac_App.command       # 1-Click standalone .app bundle builder
├── Create_Mac_DMG.command      # 1-Click drag-and-drop .dmg installer creator
├── Run_Windows.bat             # 1-Click double-clickable Windows launcher
└── README.md                   # Complete user documentation & guides
```

---

*Crafted with care and whimsy for Ericka & Faery Good.*  
*Visit the apothecary at **[FaeryGood.com](https://faerygood.com/)**.*


