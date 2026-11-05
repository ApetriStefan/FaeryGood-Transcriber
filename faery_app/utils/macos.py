"""
macOS Application Bundle Creation & Applications Folder Registration
"""

from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from faery_app.constants import APP_NAME, APP_VERSION, FAERY_GOOD_URL, FAERY_GOOD_TAGLINE


def _is_dir_writable(directory: Path | str) -> bool:
    """Delegates to app.is_directory_writable if present (for mock compatibility), else uses internal helper."""
    app_mod = sys.modules.get("app")
    if app_mod and hasattr(app_mod, "is_directory_writable"):
        return app_mod.is_directory_writable(directory)
    from faery_app.utils.system import is_directory_writable
    return is_directory_writable(directory)


def _get_repo_dir() -> Path:
    """Finds the root repository directory containing app.py and assets."""
    app_mod = sys.modules.get("app")
    if app_mod and hasattr(app_mod, "__file__") and app_mod.__file__:
        return Path(app_mod.__file__).resolve().parent
    # faery_app/utils/macos.py -> parents[2] is the repository root
    return Path(__file__).resolve().parents[2]


def _create_macos_app_bundle(
    target_bundle: Path,
    repo_dir: Optional[Path] = None,
    exe_dir: Optional[Path] = None,
) -> Path:
    """Builds the macOS .app directory structure, Info.plist, launcher, and icon."""
    contents_dir = target_bundle / "Contents"
    macos_dir = contents_dir / "MacOS"
    resources_dir = contents_dir / "Resources"
    macos_dir.mkdir(parents=True, exist_ok=True)
    resources_dir.mkdir(parents=True, exist_ok=True)

    # 1. Info.plist
    plist_path = contents_dir / "Info.plist"
    plist_data = {
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleIdentifier": "com.faerygood.transcriber",
        "CFBundleVersion": APP_VERSION,
        "CFBundleShortVersionString": APP_VERSION,
        "CFBundlePackageType": "APPL",
        "CFBundleExecutable": APP_NAME,
        "CFBundleIconFile": "faery_icon.icns",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "11.0",
        "LSApplicationCategoryType": "public.app-category.video",
        "NSDocumentsFolderUsageDescription": "Faery Good Transcriber stores generated transcripts in your Documents folder.",
        "NSHumanReadableCopyright": f"Crafted for Faery Good ({FAERY_GOOD_URL}) • {FAERY_GOOD_TAGLINE}",
    }
    with open(plist_path, "wb") as fp:
        plistlib.dump(plist_data, fp)

    # 2. Contents/MacOS/Faery Good Transcriber launcher script
    launcher_path = macos_dir / APP_NAME
    if repo_dir:
        abs_repo = str(repo_dir.resolve())
        launcher_script = f"""#!/usr/bin/env bash
REPO_DIR="{abs_repo}"
cd "$REPO_DIR" || exit 1
if [ -f "$REPO_DIR/.venv/bin/python" ]; then
    exec "$REPO_DIR/.venv/bin/python" "$REPO_DIR/app.py"
elif [ -x "$REPO_DIR/Run_Mac.command" ]; then
    exec "$REPO_DIR/Run_Mac.command"
else
    exec python3 "$REPO_DIR/app.py"
fi
"""
    elif exe_dir:
        abs_exe = str(exe_dir.resolve())
        launcher_script = f"""#!/usr/bin/env bash
cd "{abs_exe}" || exit 1
if [ -x "{abs_exe}/FaeryTranscriber" ]; then
    exec "{abs_exe}/FaeryTranscriber"
else
    exec "{abs_exe}/{APP_NAME}"
fi
"""
    else:
        launcher_script = """#!/usr/bin/env bash
exit 1
"""
    launcher_path.write_text(launcher_script, encoding="utf-8")
    try:
        launcher_path.chmod(0o755)
    except Exception:
        pass

    # 3. Icon
    icon_src: Optional[Path] = None
    if repo_dir:
        icon_src = repo_dir / "assets" / "faery_icon.icns"
    elif exe_dir:
        icon_src = exe_dir / "assets" / "faery_icon.icns"

    if icon_src and icon_src.exists():
        icon_dst = resources_dir / "faery_icon.icns"
        try:
            shutil.copy2(icon_src, icon_dst)
        except Exception:
            pass

    return target_bundle


def _register_macos_app_bundle(target_bundle: Path) -> None:
    """Registers app bundle with macOS Gatekeeper, LaunchServices, and Finder."""
    bundle_str = str(target_bundle.resolve())
    # 1. Gatekeeper quarantine removal
    try:
        subprocess.run(["xattr", "-cr", bundle_str], capture_output=True, check=False)
    except Exception:
        pass

    # 2. LaunchServices registration
    lsregister_paths = [
        "/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister",
        shutil.which("lsregister"),
    ]
    for lsr in lsregister_paths:
        if lsr and os.path.exists(lsr):
            try:
                subprocess.run([lsr, "-f", bundle_str], capture_output=True, check=False)
                break
            except Exception:
                pass

    # 3. Touch bundle directory to notify Finder/Spotlight
    try:
        os.utime(bundle_str, None)
    except Exception:
        pass


def ensure_macos_app_installed(
    applications_dir: Optional[Path | str] = None,
    user_applications_dir: Optional[Path | str] = None,
    force_platform: Optional[str] = None,
) -> Optional[Path]:
    """Ensures 'Faery Good Transcriber.app' is installed and registered in macOS Applications folder.

    Supports:
    - Frozen Bundle mode: PyInstaller standalone app (`sys.frozen`).
    - Source-Run mode: Git clone / source repo.

    Returns:
        Path to the installed application bundle, or None if skipped or on non-darwin OS.
    """
    current_platform = force_platform or sys.platform
    if current_platform != "darwin":
        return None

    try:
        sys_apps = Path(applications_dir) if applications_dir is not None else Path("/Applications")
        usr_apps = Path(user_applications_dir) if user_applications_dir is not None else (Path.home() / "Applications")

        if _is_dir_writable(sys_apps):
            target_parent = sys_apps
        else:
            usr_apps.mkdir(parents=True, exist_ok=True)
            target_parent = usr_apps

        target_bundle = target_parent / f"{APP_NAME}.app"
        is_frozen = getattr(sys, "frozen", False)

        if is_frozen:
            exe_path = Path(sys.executable).resolve()
            source_bundle: Optional[Path] = None
            for parent in exe_path.parents:
                if parent.suffix.lower() == ".app":
                    source_bundle = parent
                    break

            if source_bundle is not None:
                # If already executing directly from target bundle, nothing to copy
                try:
                    if source_bundle.resolve() == target_bundle.resolve():
                        return target_bundle
                except Exception:
                    pass

                # Copy running bundle to target Applications folder
                if target_bundle.exists():
                    shutil.rmtree(target_bundle, ignore_errors=True)
                shutil.copytree(source_bundle, target_bundle)
            else:
                _create_macos_app_bundle(target_bundle, exe_dir=exe_path.parent)
        else:
            repo_dir = _get_repo_dir()
            _create_macos_app_bundle(target_bundle, repo_dir=repo_dir)

        _register_macos_app_bundle(target_bundle)
        try:
            print(f'✔ Added "{APP_NAME}" to Applications (Searchable via Spotlight ⌘+Space)')
        except UnicodeEncodeError:
            print(f'[OK] Added "{APP_NAME}" to Applications (Searchable via Spotlight)')
        except Exception:
            pass
        return target_bundle

    except Exception as exc:
        print(f"[FaeryTranscriber] Note: Applications integration notice: {exc}")
        return None
