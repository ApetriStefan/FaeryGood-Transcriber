"""
Weekly Auto-Update Check & Pull Subsystem for Faery Good Transcriber
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Tuple

from faery_app.config.config_manager import ConfigManager


class AutoUpdater:
    """
    Checks and pulls updates from the GitHub repository once a week (7 days)
    only when the application is launched from a git clone, provided internet is available.
    In standalone packaged bundles (e.g. PyInstaller .exe / .app) or environments without
    Git, automatic updates are skipped entirely to prevent crashes or failing subprocess calls.
    """

    WEEK_IN_SECONDS = 7 * 24 * 3600  # 604,800 seconds

    @classmethod
    def is_standalone_bundle(cls) -> bool:
        """Returns True if the application is running inside a PyInstaller frozen bundle."""
        return getattr(sys, "frozen", False)

    @classmethod
    def is_git_available(cls) -> bool:
        """Returns True if the git command-line tool is installed and reachable in PATH."""
        return shutil.which("git") is not None

    @staticmethod
    def is_internet_available(timeout: float = 2.0) -> bool:
        """Quickly checks for internet connectivity without blocking."""
        import socket
        try:
            # Connect to Cloudflare or Google public DNS on port 53 (extremely fast, low overhead)
            socket.create_connection(("1.1.1.1", 53), timeout=timeout).close()
            return True
        except OSError:
            try:
                socket.create_connection(("8.8.8.8", 53), timeout=timeout).close()
                return True
            except OSError:
                return False

    @classmethod
    def should_check_update(cls, config: ConfigManager, force: bool = False) -> bool:
        """Determines if at least 7 days have passed since the last update check."""
        if force:
            return True
        now = time.time()
        last_check = config.last_update_check
        # If last_check is in the future or older than 7 days, trigger check
        return (now - last_check) >= cls.WEEK_IN_SECONDS

    @classmethod
    def upgrade_runtime_dependencies(cls) -> bool:
        """
        Silently upgrades yt-dlp, yt-dlp-ejs, and deno in non-frozen environments
        so online video extractors remain up to date.
        """
        if cls.is_standalone_bundle():
            return False
        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        try:
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--upgrade",
                    "yt-dlp[default]",
                    "yt-dlp-ejs",
                    "deno",
                    "-q",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=creation_flags,
                timeout=60,
            )
            return proc.returncode == 0
        except Exception:
            return False

    @classmethod
    def run_update_check_and_pull(
        cls,
        config: ConfigManager,
        project_dir: Path,
        force: bool = False,
    ) -> Tuple[bool, str]:
        """
        Checks git remote and performs a fast-forward pull if updates exist.
        Returns (updated, message).
        """
        # 1. Standalone bundle check (PyInstaller distribution)
        if cls.is_standalone_bundle():
            if force:
                return (
                    False,
                    "✨ You are running the standalone packaged version of Faery Good Transcriber!\n\n"
                    "Standalone builds do not require Git. To check for or download new versions, "
                    "visit https://faerygood.com/ or check GitHub Releases."
                )
            return False, "Standalone package: Git updates disabled."

        # 2. Check if git CLI is installed
        if not cls.is_git_available():
            if force:
                return (
                    False,
                    "Git was not found on this computer.\n\n"
                    "If you would like to receive automatic updates via Git, please install Git from https://git-scm.com/ "
                    "or download new versions directly from https://faerygood.com/."
                )
            return False, "Git command-line tool not found: skipping automatic updates."

        # 3. Verify this is an actual git repository (.git folder exists)
        git_dir = project_dir / ".git"
        if not git_dir.exists():
            if force:
                return (
                    False,
                    "This copy of Faery Good Transcriber was installed without Git (e.g. from a ZIP download).\n\n"
                    "You are currently running the complete release version! To update, visit https://faerygood.com/."
                )
            return False, "Not a Git clone: skipping automatic updates."

        # 4. Check if 7 days have elapsed
        if not cls.should_check_update(config, force=force):
            return False, "You're already up to date! Updates were checked recently."

        # 5. Check internet availability
        if not cls.is_internet_available():
            return False, "Unable to check for updates because your computer is offline. Please check your internet connection."

        # Record this check timestamp
        config.last_update_check = time.time()
        cls.upgrade_runtime_dependencies()

        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

        try:
            # Check for uncommitted local changes to avoid merge conflicts
            status_proc = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(project_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=creation_flags,
                timeout=10,
            )
            if status_proc.returncode != 0:
                return False, "Unable to check for updates at this time. Please try again later."

            has_local_changes = bool(status_proc.stdout.strip())

            # Fetch origin main
            fetch_proc = subprocess.run(
                ["git", "fetch", "--quiet", "origin", "main"],
                cwd=str(project_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=creation_flags,
                timeout=20,
            )
            if fetch_proc.returncode != 0:
                return False, "Unable to reach the update server. Please check your internet connection and try again."

            # Check local HEAD vs remote origin/main
            rev_local = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(project_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=creation_flags,
                timeout=5,
            ).stdout.strip()

            rev_remote = subprocess.run(
                ["git", "rev-parse", "origin/main"],
                cwd=str(project_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=creation_flags,
                timeout=5,
            ).stdout.strip()

            if not rev_local or not rev_remote:
                return False, "Unable to verify version information. Please try again later."

            if rev_local == rev_remote:
                return False, "✨ Faery Good Transcriber is already up to date!"

            # Remote has new commits! Pull them
            if has_local_changes:
                # Stash local modifications, pull, and reapply cleanly
                subprocess.run(
                    ["git", "stash"],
                    cwd=str(project_dir),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=creation_flags,
                    timeout=10,
                )
                try:
                    pull_proc = subprocess.run(
                        ["git", "pull", "--ff-only", "origin", "main"],
                        cwd=str(project_dir),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        creationflags=creation_flags,
                        timeout=30,
                    )
                finally:
                    subprocess.run(
                        ["git", "stash", "pop"],
                        cwd=str(project_dir),
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=creation_flags,
                        timeout=10,
                    )
            else:
                pull_proc = subprocess.run(
                    ["git", "pull", "--ff-only", "origin", "main"],
                    cwd=str(project_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    creationflags=creation_flags,
                    timeout=30,
                )

            if pull_proc.returncode == 0:
                return True, "✨ Updated successfully to the latest version from GitHub!"
            else:
                return False, "Could not download the update. Please try again later."

        except subprocess.TimeoutExpired:
            return False, "Update check timed out. Please check your internet connection and try again."
        except Exception:
            return False, "Unable to complete the update check right now. Please try again later."
