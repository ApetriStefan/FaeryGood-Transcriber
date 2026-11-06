"""
Online Media Fetcher for Faery Good Transcriber (yt-dlp integration)
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import threading
import urllib.parse
from pathlib import Path
from typing import Callable, List, Optional

from faery_app.constants import COOKIE_BROWSER_OPTIONS, DEFAULT_COOKIE_BROWSER
from faery_app.models.metadata import OnlineClipInfo
from faery_app.utils.system import get_verified_ffmpeg_exe


class OnlineMediaFetcher:
    """
    Fetches temporary audio streams from Instagram, YouTube, TikTok, Facebook, and 1,000+ sites
    using yt-dlp and the bundled static FFmpeg binary. Strictly writes into a caller-managed
    TemporaryDirectory so zero media files remain after transcription.
    """

    ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    _cached_deno_exe: Optional[str] = None

    @staticmethod
    def is_valid_url(url_str: str) -> bool:
        """Returns True if url_str is a well-formed HTTP/HTTPS URL."""
        cleaned = (url_str or "").strip()
        if not cleaned:
            return False
        try:
            parsed = urllib.parse.urlparse(cleaned)
            return parsed.scheme in ("http", "https") and bool(parsed.netloc) and "." in parsed.netloc
        except Exception:
            return False

    @staticmethod
    def detect_platform(url_str: str) -> str:
        """Returns a human-friendly platform name for UI badges and status messages."""
        try:
            host = urllib.parse.urlparse((url_str or "").strip()).netloc.lower()
        except Exception:
            host = ""
        if "instagram.com" in host or "instagr.am" in host:
            return "Instagram"
        if "youtube.com" in host or "youtu.be" in host:
            return "YouTube"
        if "tiktok.com" in host:
            return "TikTok"
        if "facebook.com" in host or "fb.watch" in host or "fb.com" in host:
            return "Facebook"
        return "Web Video"

    @staticmethod
    def sanitize_title(raw_title: str, fallback: str = "Online_Clip") -> str:
        """Cleans an online video title into a safe, readable cross-platform filename stem."""
        if not raw_title:
            return fallback
        # Strip filesystem-unsafe characters and control characters
        cleaned = re.sub(r'[\\/*?:"<>|\r\n\t]+', " ", raw_title)
        cleaned = "".join(ch for ch in cleaned if ch.isprintable())
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" .-_")
        if len(cleaned) > 80:
            cleaned = cleaned[:80].rstrip(" .-_")
        return cleaned if cleaned else fallback

    @classmethod
    def clean_error_message(cls, raw_err: str, platform: str) -> str:
        """Strips ANSI escape sequences and formats a friendly, reassuring error message for creators."""
        clean = cls.ANSI_ESCAPE_RE.sub("", str(raw_err or "")).strip()
        clean = re.sub(r"^ERROR:\s*", "", clean, flags=re.IGNORECASE)
        lower = clean.lower()
        if any(k in lower for k in ("login required", "sign in", "cookies", "rate-limit", "private", "not available")):
            return (
                f"{platform} requires you to be signed in to access this clip (or the post is private).\n\n"
                "💡 Tip: In the 'Social Login' dropdown under Studio Preferences, select the browser "
                "where you are logged into your account (e.g. Chrome, Safari, Brave, Edge, or Firefox) and click Generate again!"
            )
        return (
            f"Could not download audio from {platform} link. "
            "Please check that the clip is public and that your computer is connected to the internet."
        )

    @classmethod
    def _get_deno_executable(cls) -> Optional[str]:
        """Resolves and caches the bundled or installed Deno JavaScript runtime for yt-dlp."""
        if cls._cached_deno_exe and os.path.isfile(cls._cached_deno_exe):
            parent_dir = str(Path(cls._cached_deno_exe).parent)
            current_path = os.environ.get("PATH", "")
            path_parts = current_path.split(os.pathsep) if current_path else []
            if parent_dir not in path_parts:
                os.environ["PATH"] = f"{parent_dir}{os.pathsep}{current_path}" if current_path else parent_dir
            return cls._cached_deno_exe

        deno_bin: Optional[str] = None
        try:
            import deno
            cand = deno.find_deno_bin()
            if cand and Path(cand).is_file():
                deno_bin = str(cand)
        except Exception:
            pass

        if not deno_bin:
            which_deno = shutil.which("deno")
            if which_deno and Path(which_deno).is_file():
                deno_bin = which_deno

        if not deno_bin and getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            bundled = Path(sys._MEIPASS) / ("deno.exe" if sys.platform == "win32" else "deno")
            if bundled.is_file():
                deno_bin = str(bundled)

        if deno_bin:
            resolved = Path(deno_bin).resolve()
            resolved_str = str(resolved)
            cls._cached_deno_exe = resolved_str
            parent_dir = str(resolved.parent)
            current_path = os.environ.get("PATH", "")
            path_parts = current_path.split(os.pathsep) if current_path else []
            if parent_dir not in path_parts:
                os.environ["PATH"] = f"{parent_dir}{os.pathsep}{current_path}" if current_path else parent_dir
            return resolved_str
        return None

    @classmethod
    def download_audio_to_temp(
        cls,
        url: str,
        temp_dir: Path,
        cancel_event: threading.Event,
        status_cb: Optional[Callable[[str], None]] = None,
        progress_cb: Optional[Callable[[float], None]] = None,
        cookie_browser_label: str = DEFAULT_COOKIE_BROWSER,
        cookie_permission_cb: Optional[Callable[[str], bool]] = None,
    ) -> OnlineClipInfo:
        """
        Downloads only the best audio stream for the given URL into `temp_dir`.
        Aborts immediately if `cancel_event` is set.
        """
        import yt_dlp

        if not cls.is_valid_url(url):
            raise ValueError("Please enter a valid link starting with https:// or http://")

        if cancel_event.is_set():
            raise InterruptedError("Download was cancelled by the user.")

        platform = cls.detect_platform(url)
        if status_cb:
            status_cb(f"🌐 Connecting to {platform} and inspecting link...")

        def _progress_hook(d: dict) -> None:
            if cancel_event.is_set():
                raise InterruptedError("Download was cancelled by the user.")
            st = d.get("status")
            if st == "downloading":
                downloaded = d.get("downloaded_bytes") or 0
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                if total > 0:
                    pct = min(0.99, max(0.01, downloaded / total))
                    if progress_cb:
                        progress_cb(pct)
                    if status_cb:
                        status_cb(f"📥 Downloading temporary audio from {platform} ({int(pct * 100)}%)...")
                else:
                    if status_cb:
                        status_cb(f"📥 Downloading temporary audio from {platform}...")
            elif st == "finished":
                if status_cb:
                    status_cb(f"✨ {platform} audio downloaded! Preparing audio for transcription...")

        outtmpl = str(temp_dir / "online_source_%(id)s.%(ext)s")
        base_opts = {
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "ffmpeg_location": get_verified_ffmpeg_exe(),
            "progress_hooks": [_progress_hook],
            "socket_timeout": 20,
            "retries": 2,
        }
        deno_bin = cls._get_deno_executable()
        if deno_bin:
            base_opts["js_runtimes"] = {"deno": {"path": deno_bin}}

        chosen_browser = COOKIE_BROWSER_OPTIONS.get(cookie_browser_label)
        attempts: List[Optional[str]] = []
        if chosen_browser:
            attempts.append(chosen_browser)
        else:
            # First try public (no cookies); if auth fails, ask permission before trying installed browsers
            attempts.append(None)
            if sys.platform == "darwin":
                attempts.extend(["safari", "chrome", "brave", "firefox", "edge"])
            else:
                attempts.extend(["chrome", "edge", "brave", "firefox"])

        info_dict: Optional[dict] = None
        last_error: Optional[Exception] = None

        for idx, browser_name in enumerate(attempts):
            if cancel_event.is_set():
                raise InterruptedError("Download was cancelled by the user.")

            # Clean any partial files from previous attempt inside temp_dir
            for part_f in temp_dir.glob("online_source_*"):
                try:
                    part_f.unlink()
                except Exception:
                    pass

            opts = dict(base_opts)
            if browser_name:
                opts["cookiesfrombrowser"] = (browser_name,)
                if idx > 0 and status_cb:
                    status_cb(f"🔐 {platform} requires sign-in — trying {browser_name.title()} session...")

            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info_dict = ydl.extract_info(url.strip(), download=True)
                if info_dict is not None:
                    break
            except InterruptedError:
                raise
            except Exception as err:
                err_str = str(err)
                if cancel_event.is_set() or "cancelled by the user" in err_str.lower():
                    raise InterruptedError("Download was cancelled by the user.")
                if idx == 0:
                    last_error = err
                    # Only auto-retry with browser cookies if it looks like an auth/login/cookie issue
                    lower_err = err_str.lower()
                    needs_auth = any(
                        w in lower_err
                        for w in ("login", "cookie", "sign in", "private", "rate-limit", "403", "forbidden", "instagram", "facebook")
                    )
                    if not needs_auth:
                        break
                    if cookie_permission_cb is None or not cookie_permission_cb(platform):
                        break
                else:
                    continue

        if info_dict is None:
            raise RuntimeError(cls.clean_error_message(str(last_error or "Unknown download error"), platform))

        # Locate the downloaded media file inside temp_dir
        downloaded_files = [
            p for p in temp_dir.glob("online_source_*")
            if p.is_file() and not p.name.endswith((".part", ".ytdl", ".json"))
        ]
        if not downloaded_files:
            raise RuntimeError(f"Failed to locate downloaded audio stream from {platform}.")

        temp_media_path = max(downloaded_files, key=lambda p: p.stat().st_size)
        video_id = str(info_dict.get("id") or "clip")
        raw_title = str(info_dict.get("title") or "").strip()
        if not raw_title or raw_title.lower() in ("video", "reel", "post"):
            raw_title = f"{platform}_{video_id}"
        sanitized_title = cls.sanitize_title(raw_title, fallback=f"{platform}_{video_id}")
        duration_sec = float(info_dict.get("duration") or 0.0)

        return OnlineClipInfo(
            url=url.strip(),
            platform=platform,
            title=raw_title,
            sanitized_title=sanitized_title,
            video_id=video_id,
            duration_seconds=duration_sec,
            temp_media_path=temp_media_path,
        )
