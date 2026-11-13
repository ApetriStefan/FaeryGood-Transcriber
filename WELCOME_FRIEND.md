# 🦋 Welcome to Faery Good Transcriber!

Hello and welcome! This little app turns your **voice memos, podcasts, videos, and social clips (Instagram Reels, YouTube, TikTok, and Facebook)** into crystal-clear, beautifully formatted transcripts in seconds.

Everything runs **100% privately on your own computer**—no cloud uploads, no monthly subscriptions, and zero tech headaches.

---

## ⚡ Quick Start (Ready in 3 Simple Steps)

### 1. Launch the App with 1 Click
* **On Windows:** Double-click **`Run_Windows.bat`**
* **On Mac:** Double-click **`Run_Mac.command`**

> 🍎 **Magic on Mac (First-Launch Bonus!):**  
> On your very first launch on macOS, the app automatically adds **Faery Good Transcriber** to your Mac's **Applications** folder with its custom butterfly icon!
>
> That means after the first double-click, you **never need to open this folder or Terminal ever again**. You can launch the app anytime from:
> * 🔍 **Spotlight:** Press **`⌘+Space`**, type **`Faery`**, and press **`Enter`**
> * 🚀 **Launchpad:** Click the Faery Good butterfly icon in your Launchpad grid
> * 📁 **Applications Folder or Dock:** Open it from Finder or drag it right to your Dock for 1-click access!

> **A Quick First-Launch Note:** On your very first run, the app prepares its private Python environment and speech recognition model. This only takes about a minute. After that, launches are near-instant!
> *(If your Mac shows a security prompt on the first double-click, simply right-click `Run_Mac.command` and choose **Open**).*
>
> 🐍 **Modern Python (3.10, 3.11, or 3.12) Requirement:**  
> The app requires a modern version of Python (3.10, 3.11, or 3.12).  
> * **On Mac:** macOS comes with an older built-in Python 3.9 stub that is out of date. If modern Python isn't detected, `Run_Mac.command` will automatically pop up a friendly window with a 1-click **"Install Python"** button. Clicking it automatically downloads and opens the official Python 3.12 installer directly on your screen!
> * **On Windows:** If Python 3.10+ isn't detected yet, `Run_Windows.bat` will display a friendly dialog offering a 1-click button to open the official Python download page (be sure to check the box *"Add python.exe to PATH"* during installation).

---

### 2. Pick Your Audio, Video, or Social Link
Choose whichever is easiest for you:

* **📁 From Your Computer:** Click **`📁 Select Local File…`** (or press `Ctrl+O` on Windows / `⌘O` on Mac). You can drop in voice memos, podcast tracks, phone videos, or Zoom recordings (`.mp4`, `.mov`, `.m4a`, `.mp3`, `.wav`).
* **🎙️ Record Your Microphone:** Click **`🎙️ Record Mic`** (or press `Ctrl+D` / `⌘D`) to record voice notes directly in the app. You'll see a live audio level bar react to your voice as you speak.
  > *(First time using Mic on Mac? Click **Allow** if macOS asks for Microphone access — or turn on **Faery Good Transcriber** in **System Settings → Privacy & Security → Microphone**.)*
* **🌐 From Social Media:** Copy any public link from **Instagram Reels, YouTube, TikTok, or Facebook**, then click **`📋 Paste Link`** (or press `Ctrl+L` / `⌘L`).

> 🔒 **Privacy Guarantee on Links:** When transcribing from a web link, the app extracts the audio into a temporary private scratch area, transcribes it, and then **immediately deletes** the audio file the moment it finishes. Zero clutter is left behind on your disk!

#### 🎛️ Choose Your Transcription Engine (3 Models Available)
Right below the file selection area, pick the engine that best fits your recording:
* **`Maximum Accuracy (large-v3-turbo - Best Punctuation)` (Default & Recommended):** Delivers book-quality punctuation, natural question marks, clean sentence structures, and proper capitalization. Powered by OpenAI's 809M parameter turbo architecture with a fast 4-layer decoder, it gives you publication-ready captions and articles without manual editing.
* **`High Accuracy (small.en - Fast)`:** Fast and reliable English transcription, perfect for longer interviews or podcasts when you want great accuracy at high speed.
* **`Standard Draft (base.en - Ultra Fast)`:** 2–3x faster transcription for quick rough drafts, 30-second clips, or fast keyword searching.

---

### 3. Click "✨ Generate Transcript"
Press **`✨ Generate Transcript`** (or hit `Ctrl+Enter` / `⌘Enter`).

With **`Maximum Accuracy (large-v3-turbo)`** selected, the engine primes the audio with contextual punctuation conditioning and heals paragraph boundaries automatically—delivering crisp sentences, natural question phrasing, and book-quality reading flow.

> 🪄 **Automatic Upfront Time & "Cup of Tea" Indicator:**  
> The moment you select a file or stop a microphone recording, the app shows an upfront estimate of how long transcription will take (e.g. `🪄 Est. time: ~4–5 mins ☕ (time for tea!)`). The app automatically learns your computer's speed and calibrates itself over time for each model. If a job is estimated at 2 minutes or longer, it delightfully reminds you it's `☕ (time for tea!)` so you can take a cozy break. During transcription, you'll also see a live countdown showing remaining time!

Watch your words stream onto the screen in real time! When finished, a gentle chime sounds, and your transcript is automatically saved.

---

## 📄 The 3 Output Formats

At the top of the transcript studio, you can switch between three views with a single click:

| Format | Best For | What It Looks Like |
|---|---|---|
| **📄 Clean Paragraphs** | Newsletters, blog posts, Instagram captions, & articles | Natural sentences automatically grouped by where you naturally paused when speaking. |
| **⏱️ Timestamped** | Show notes, video editing & reference logs | Includes `[MM:SS]` timestamps on every spoken segment so you can easily find any moment in your recording. |
| **📝 Raw Text** | Note-taking apps, AI prompts, or custom editing | Clean, continuous text without any extra markup. |

---

## 📂 Where Are My Transcripts Saved?

Every single transcript is automatically saved to your computer in:
> **`Documents/Transcriptions/`**

You never have to go digging through folders! Just click the **`📂 Folder`** button in the studio bar (or press `Ctrl+Shift+O` / `⇧⌘O`), and your transcript folder will open right in File Explorer (Windows) or Finder (Mac).

Each transcript is saved in both clean text (`.txt`) and formatted Markdown (`.md`).

---

## 📜 The History Library

Click the **`📜 History`** tab (or press `Ctrl+2` / `⌘2`) anytime to review past recordings:

* **🔍 Instant Search:** Type any word or phrase you remember speaking, and find the exact transcript in milliseconds.
* **✏️ In-App Edits:** Fix a misspelled name or add notes directly in the app, then click **`💾 Save Edits`**.
* **📋 1-Click Copy:** Click **`📋 Copy to Clipboard`** (or press `⇧⌘C` / `Ctrl+Shift+C`) to paste your full transcript into Word, Google Docs, Notion, or an email. (`⌘C` / `Ctrl+C` copies whatever highlighted text you select.)

---

## 📻 Bonus: Ambient Radio (104.9 The Grift FM)

Need some inspiring background music while reviewing your work?

Click the **`📻 Radio`** button in the top bar (or press `Ctrl+R` / `⌘R`) to tune into **104.9 The Grift FM**—a custom ambient lo-fi station complete with relaxing beats, GTA-style DJ bumpers, and original apothecary tracks.

We recently added two brand-new tracks to the rotation:
* 🍃 **"The Green Leaf Thief"**
* 🏃‍♀️ **"Where You Gonna Run?"**

Enjoy them alongside old favorites with effortless keyboard navigation!

### Handy Radio Shortcuts:
* **`Space`** — Play / Pause the radio *(active anytime your cursor is not typing in a text field)*
* **`Ctrl+→`** / **`⌘→`** — Skip to next track
* **`Ctrl+←`** / **`⌘←`** — Previous track
* **`Ctrl+↑`** / **`Ctrl+↓`** (`⌘↑`/`⌘↓`) — Turn volume up or down

---

## 🔐 Social Login (Instagram & Facebook Clips)

Occasionally, Instagram or Facebook will ask visitors to sign in before playing certain Reels or private clips.

We made this super easy:
1. In **`Auto / Public (Recommended)`** mode, the app always tries to download clips publicly first. If a clip is behind a login wall, the app will ask your permission before reading browser cookies (supporting **Safari**, **Chrome**, **Firefox**, **Edge**, and **Brave**).
2. Or, in the app's preferences bar, find the **`🔐 Social Login`** dropdown and directly select the web browser where you are already logged into Instagram or Facebook (e.g., **Chrome**, **Safari**, **Edge**, **Brave**, or **Firefox**).
3. Click **`✨ Generate Transcript`** again!

The app will securely reuse your existing browser cookie to access the audio. It **never** asks for, touches, or stores your passwords.

---

## 🛡️ 100% Private, Offline, & Zero-Footprint

Your voice and words belong entirely to you:
* **Runs 100% on CPU:** The AI speech model runs completely on your local computer. No sound or transcript is ever uploaded to external cloud servers or used to train third-party AI models.
* **Works Offline:** Once the model is initialized, you can transcribe without any internet connection at all (great for flights or working in cabins!).
* **Auto-Clean Scratch Storage:** All temporary audio extracts are swept completely clean on transcription finish, user cancellation, or app shutdown.

---

## 💡 Quick Troubleshooting & Tips

* **"My Mac mic recording finished immediately or recorded silence!"** Check **System Settings → Privacy & Security → Microphone** and ensure **Faery Good Transcriber** is toggled **ON** (and check that your Mac's input volume isn't muted in **System Settings → Sound → Input**). Watch the live signal bar under **🎙️ Record Mic** — it lights up green when your voice is coming through!
* **"Can I change the appearance?"** Yes! Click the theme dropdown in the top-right corner to switch between **Light**, **Dark**, or **System** mode whenever you like.
* **"How do I copy just one sentence vs. the whole transcript?"** Highlight any sentence and press `⌘C` / `Ctrl+C` as usual, or press **`⇧⌘C` / `Ctrl+Shift+C`** (or click **`📋 Copy to Clipboard`**) to copy the entire transcript!
* **"What languages are supported?"** Faery Good Transcriber is specifically tuned and optimized for **English** speech across three models: **`Maximum Accuracy (large-v3-turbo - Best Punctuation)`** (the default, delivering publication-ready punctuation and sentence flow), **`High Accuracy (small.en - Fast)`**, and **`Standard Draft (base.en - Ultra Fast)`**.
* **"Need a hand or ran into a glitch?"** Stef has you covered! Simply click **Help → 📋 Copy Diagnostic Log for Stef** in the top menu bar. This copies a private, zero-jargon diagnostic log directly to your clipboard so you can paste and send it right to Stef—without ever sharing your private recordings or spoken words.

---

*Made with love for creators and storytellers by Faery Good.* 🦋
