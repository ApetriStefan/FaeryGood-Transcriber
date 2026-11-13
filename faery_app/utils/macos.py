"""
macOS Application Bundle Creation, TCC Microphone Permissions, & App Nap Protection
"""

from __future__ import annotations

import ctypes
import ctypes.util
import json
import os
import plistlib
import shutil
import subprocess
import sys
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Tuple

from faery_app.constants import APP_NAME, APP_VERSION, FAERY_GOOD_URL, FAERY_GOOD_TAGLINE

_BUNDLE_META_FILENAME = ".faery_bundle_meta.json"


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


def _resolve_macos_libpython_path() -> Optional[str]:
    """Resolves the shared Python framework / libpython path for in-process hosting on macOS."""
    if sys.platform != "darwin":
        return None
    try:
        import sysconfig

        candidates = []
        fw_prefix = sysconfig.get_config_var("PYTHONFRAMEWORKPREFIX") or ""
        ldlibrary = sysconfig.get_config_var("LDLIBRARY") or ""
        libdir = sysconfig.get_config_var("LIBDIR") or ""
        instsoname = sysconfig.get_config_var("INSTSONAME") or ""

        if fw_prefix and ldlibrary:
            candidates.append(Path(fw_prefix) / ldlibrary)
        if libdir and ldlibrary:
            candidates.append(Path(libdir) / ldlibrary)
        if libdir and instsoname:
            candidates.append(Path(libdir) / instsoname)

        # Framework layout relative to real executable (e.g. Python.app/Contents/MacOS/Python -> .../Python)
        real_exe = Path(sys.executable).resolve()
        for parent in real_exe.parents:
            if parent.suffix == ".framework":
                candidates.append(parent / parent.stem)
                break

        for cand in candidates:
            if cand.exists() and cand.is_file():
                return str(cand.resolve())
    except Exception:
        pass
    return None


def _can_compile_macos_launcher() -> bool:
    """Checks non-interactively whether Xcode CLT clang is installed without prompting an OS popup."""
    if sys.platform != "darwin":
        return False
    try:
        # xcode-select -p exits 0 when CLT/Xcode is already installed, avoiding /usr/bin/clang shim GUI prompt
        res = subprocess.run(
            ["xcode-select", "-p"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
            check=False,
        )
        if res.returncode != 0:
            return False
        clang_path = shutil.which("clang")
        if not clang_path:
            return False
        ver = subprocess.run(
            [clang_path, "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
            check=False,
        )
        return ver.returncode == 0
    except Exception:
        return False


def _escape_c_string(val: str) -> str:
    """Escapes a string safely for inclusion as a C string literal."""
    return (
        val.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )


def _compile_macos_macho_launcher(launcher_path: Path, repo_dir: Path) -> bool:
    """
    Compiles a lightweight Mach-O binary launcher that hosts the repository's .venv
    Python interpreter in-process via dlopen(libpython) + Py_BytesMain.

    Keeping execution inside the .app bundle's own Mach-O process preserves macOS TCC
    attribution (kTCCServiceMicrophone / NSMicrophoneUsageDescription) when launched from
    Spotlight or Applications, while keeping sys.frozen=False so AutoUpdater continues to work.
    Falls back to execv() inside the binary if dlopen fails.
    """
    if not _can_compile_macos_launcher():
        return False

    clang_path = shutil.which("clang")
    if not clang_path:
        return False

    abs_repo = str(repo_dir.resolve())
    venv_python = str((repo_dir / ".venv" / "bin" / "python").resolve())
    app_py = str((repo_dir / "app.py").resolve())
    run_mac = str((repo_dir / "Run_Mac.command").resolve())
    libpython = _resolve_macos_libpython_path() or ""

    c_source = f"""#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {{
    (void)argc;
    (void)argv;
    const char *repo_dir = "{_escape_c_string(abs_repo)}";
    const char *venv_py = "{_escape_c_string(venv_python)}";
    const char *app_py = "{_escape_c_string(app_py)}";
    const char *run_mac = "{_escape_c_string(run_mac)}";
    const char *lib_py = "{_escape_c_string(libpython)}";

    if (chdir(repo_dir) != 0) {{
        return 1;
    }}

    if (access(venv_py, X_OK) == 0 && lib_py[0] != '\\0') {{
        void *handle = dlopen(lib_py, RTLD_NOW | RTLD_GLOBAL);
        if (handle != NULL) {{
            typedef int (*py_bytes_main_fn)(int, char **);
            py_bytes_main_fn py_main = (py_bytes_main_fn)dlsym(handle, "Py_BytesMain");
            if (py_main != NULL) {{
                char *py_argv[] = {{ (char *)venv_py, (char *)app_py, NULL }};
                return py_main(2, py_argv);
            }}
        }}
    }}

    if (access(venv_py, X_OK) == 0) {{
        char *fallback_argv[] = {{ (char *)venv_py, (char *)app_py, NULL }};
        execv(venv_py, fallback_argv);
    }}

    if (access(run_mac, X_OK) == 0) {{
        char *mac_argv[] = {{ (char *)run_mac, NULL }};
        execv(run_mac, mac_argv);
    }}

    char *sys_argv[] = {{ "python3", (char *)app_py, NULL }};
    execvp("python3", sys_argv);
    return 1;
}}
"""
    src_file = launcher_path.parent / "_faery_launcher.c"
    try:
        src_file.write_text(c_source, encoding="utf-8")
        proc = subprocess.run(
            [clang_path, "-O2", str(src_file), "-o", str(launcher_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
            check=False,
        )
        return proc.returncode == 0 and launcher_path.exists()
    except Exception:
        return False
    finally:
        try:
            src_file.unlink(missing_ok=True)
        except Exception:
            pass


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
        "NSRequiresAquaSystemAppearance": False,
        "LSMinimumSystemVersion": "11.0",
        "LSApplicationCategoryType": "public.app-category.video",
        "NSDocumentsFolderUsageDescription": "Faery Good Transcriber stores generated transcripts in your Documents folder.",
        "NSMicrophoneUsageDescription": "Faery Good Transcriber uses your microphone when you record voice notes for local on-device transcription.",
        "NSHumanReadableCopyright": f"Crafted for Faery Good ({FAERY_GOOD_URL}) • {FAERY_GOOD_TAGLINE}",
    }
    with open(plist_path, "wb") as fp:
        plistlib.dump(plist_data, fp)

    # 2. Contents/MacOS/Faery Good Transcriber launcher
    launcher_path = macos_dir / APP_NAME
    launcher_kind = "script"

    if repo_dir:
        compiled = _compile_macos_macho_launcher(launcher_path, repo_dir)
        if compiled:
            launcher_kind = "macho"
        else:
            abs_repo = str(repo_dir.resolve())
            escaped_repo = abs_repo.replace('"', '\\"')
            launcher_script = f"""#!/usr/bin/env bash
REPO_DIR="{escaped_repo}"
cd "$REPO_DIR" || exit 1
if [ -f "$REPO_DIR/.venv/bin/python" ]; then
    exec "$REPO_DIR/.venv/bin/python" "$REPO_DIR/app.py"
elif [ -x "$REPO_DIR/Run_Mac.command" ]; then
    exec "$REPO_DIR/Run_Mac.command"
else
    exec python3 "$REPO_DIR/app.py"
fi
"""
            launcher_path.write_text(launcher_script, encoding="utf-8")
    elif exe_dir:
        abs_exe = str(exe_dir.resolve()).replace('"', '\\"')
        launcher_script = f"""#!/usr/bin/env bash
cd "{abs_exe}" || exit 1
if [ -x "{abs_exe}/FaeryTranscriber" ]; then
    exec "{abs_exe}/FaeryTranscriber"
else
    exec "{abs_exe}/{APP_NAME}"
fi
"""
        launcher_path.write_text(launcher_script, encoding="utf-8")
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

    # 4. Write bundle metadata sentinel so subsequent launches avoid unnecessary rewrites
    try:
        meta_file = contents_dir / _BUNDLE_META_FILENAME
        meta_file.write_text(
            json.dumps(
                {
                    "version": APP_VERSION,
                    "repo_dir": str(repo_dir.resolve()) if repo_dir else "",
                    "launcher_kind": launcher_kind,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass

    return target_bundle


def _is_bundle_current(target_bundle: Path, repo_dir: Path) -> bool:
    """Returns True if an existing source-mode .app bundle is already current and valid."""
    try:
        contents_dir = target_bundle / "Contents"
        plist_file = contents_dir / "Info.plist"
        launcher_file = contents_dir / "MacOS" / APP_NAME
        meta_file = contents_dir / _BUNDLE_META_FILENAME
        if not (plist_file.is_file() and launcher_file.is_file() and meta_file.is_file()):
            return False

        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        if meta.get("version") != APP_VERSION:
            return False
        if meta.get("repo_dir") != str(repo_dir.resolve()):
            return False

        # If Xcode CLT is present on macOS, upgrade any older bash-script bundle once to Mach-O
        if meta.get("launcher_kind") != "macho" and _can_compile_macos_launcher():
            return False

        return True
    except Exception:
        return False


def _register_macos_app_bundle(target_bundle: Path, entitlements_path: Optional[Path] = None) -> None:
    """Removes quarantine, ad-hoc signs bundle for TCC stability, and registers with LaunchServices."""
    bundle_str = str(target_bundle.resolve())
    # 1. Gatekeeper quarantine removal
    try:
        subprocess.run(["xattr", "-cr", bundle_str], capture_output=True, check=False)
    except Exception:
        pass

    # 2. Ad-hoc codesign on macOS so TCC associates permissions cleanly with bundle identifier
    if sys.platform == "darwin" and shutil.which("codesign"):
        try:
            cmd = ["codesign", "--force", "--deep", "--sign", "-"]
            if entitlements_path and entitlements_path.is_file():
                cmd.extend(["--entitlements", str(entitlements_path)])
            cmd.append(bundle_str)
            subprocess.run(cmd, capture_output=True, timeout=15, check=False)
        except Exception:
            pass

    # 3. LaunchServices registration
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

    # 4. Touch bundle directory to notify Finder/Spotlight
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

    Skips recreating an already-current source bundle so macOS TCC microphone permissions
    and code signatures remain intact across launches.

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

                # Copy running bundle to target Applications folder preserving framework symlinks
                if target_bundle.exists():
                    shutil.rmtree(target_bundle, ignore_errors=True)
                shutil.copytree(source_bundle, target_bundle, symlinks=True)
                _register_macos_app_bundle(target_bundle)
            else:
                _create_macos_app_bundle(target_bundle, exe_dir=exe_path.parent)
                _register_macos_app_bundle(target_bundle)
        else:
            repo_dir = _get_repo_dir()
            if _is_bundle_current(target_bundle, repo_dir):
                return target_bundle
            _create_macos_app_bundle(target_bundle, repo_dir=repo_dir)
            entitlements = repo_dir / "macos_entitlements.plist"
            _register_macos_app_bundle(target_bundle, entitlements_path=entitlements)

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


# ---------------------------------------------------------------------------
# macOS TCC Microphone Authorization Helpers (Zero-Dependency ObjC Bridge)
# ---------------------------------------------------------------------------
_TCC_STATUS_MAP = {
    0: "not_determined",
    1: "restricted",
    2: "denied",
    3: "authorized",
}


class _ObjCBlockDescriptor(ctypes.Structure):
    _fields_ = [
        ("reserved", ctypes.c_ulong),
        ("size", ctypes.c_ulong),
    ]


class _ObjCBlockLiteral(ctypes.Structure):
    _fields_ = [
        ("isa", ctypes.c_void_p),
        ("flags", ctypes.c_int),
        ("reserved", ctypes.c_int),
        ("invoke", ctypes.c_void_p),
        ("descriptor", ctypes.POINTER(_ObjCBlockDescriptor)),
    ]


def _load_objc_avfoundation():
    """Loads libobjc and AVFoundation.framework on macOS, or returns None."""
    if sys.platform != "darwin":
        return None
    try:
        objc_path = ctypes.util.find_library("objc") or "/usr/lib/libobjc.A.dylib"
        objc = ctypes.CDLL(objc_path)
        avf_path = "/System/Library/Frameworks/AVFoundation.framework/AVFoundation"
        ctypes.CDLL(avf_path, mode=ctypes.RTLD_GLOBAL)

        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        return objc
    except Exception:
        return None


def _nsstring(objc, value: str) -> Optional[int]:
    """Creates an NSString* from a UTF-8 Python string via NSString stringWithUTF8String:."""
    try:
        ns_cls = objc.objc_getClass(b"NSString")
        if not ns_cls:
            return None
        sel_utf8 = objc.sel_registerName(b"stringWithUTF8String:")
        msg_ptr = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p)(
            ("objc_msgSend", objc)
        )
        return msg_ptr(ns_cls, sel_utf8, value.encode("utf-8"))
    except Exception:
        return None


def get_macos_microphone_auth_status() -> str:
    """
    Returns macOS AVCaptureDevice authorization status for audio input:
    'authorized', 'denied', 'restricted', 'not_determined', or 'unknown'.
    Always returns 'authorized' on non-macOS platforms.
    """
    if sys.platform != "darwin":
        return "authorized"
    objc = _load_objc_avfoundation()
    if objc is None:
        return "unknown"
    try:
        av_cls = objc.objc_getClass(b"AVCaptureDevice")
        if not av_cls:
            return "unknown"
        media_type = _nsstring(objc, "soun")  # AVMediaTypeAudio = @"soun"
        if not media_type:
            return "unknown"
        sel_status = objc.sel_registerName(b"authorizationStatusForMediaType:")
        msg_status = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(
            ("objc_msgSend", objc)
        )
        code = int(msg_status(av_cls, sel_status, media_type))
        return _TCC_STATUS_MAP.get(code, "unknown")
    except Exception:
        return "unknown"


def request_macos_microphone_access(timeout: float = 20.0) -> str:
    """
    Triggers the native macOS microphone permission dialog when status is 'not_determined',
    waiting up to `timeout` seconds for the user's response.
    Returns resulting auth status ('authorized', 'denied', 'restricted', 'not_determined', or 'unknown').
    """
    if sys.platform != "darwin":
        return "authorized"
    status = get_macos_microphone_auth_status()
    if status != "not_determined":
        return status

    objc = _load_objc_avfoundation()
    if objc is None:
        return status
    try:
        av_cls = objc.objc_getClass(b"AVCaptureDevice")
        media_type = _nsstring(objc, "soun")
        global_block_isa = ctypes.c_void_p.in_dll(objc, "_NSConcreteGlobalBlock")
        if not av_cls or not media_type:
            return get_macos_microphone_auth_status()

        done_evt = threading.Event()
        granted_holder = [False]

        cb_type = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_bool)

        @cb_type
        def _handler(_block_ptr, granted: bool) -> None:
            granted_holder[0] = bool(granted)
            done_evt.set()

        desc = _ObjCBlockDescriptor(0, ctypes.sizeof(_ObjCBlockLiteral))
        block = _ObjCBlockLiteral(
            isa=ctypes.addressof(global_block_isa),
            flags=(1 << 28),
            reserved=0,
            invoke=ctypes.cast(_handler, ctypes.c_void_p).value,
            descriptor=ctypes.pointer(desc),
        )

        sel_req = objc.sel_registerName(b"requestAccessForMediaType:completionHandler:")
        msg_req = ctypes.CFUNCTYPE(
            None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
        )(("objc_msgSend", objc))
        msg_req(av_cls, sel_req, media_type, ctypes.byref(block))

        if done_evt.wait(timeout=timeout):
            return "authorized" if granted_holder[0] else "denied"
        return get_macos_microphone_auth_status()
    except Exception:
        return get_macos_microphone_auth_status()


def ensure_macos_mic_permission(timeout: float = 20.0) -> Tuple[bool, str]:
    """
    Checks and (if not yet determined) requests macOS microphone permission.
    Returns (is_allowed_to_proceed, status_string).
    """
    if sys.platform != "darwin":
        return True, "authorized"
    status = get_macos_microphone_auth_status()
    if status == "not_determined":
        status = request_macos_microphone_access(timeout=timeout)
    return status in ("authorized", "unknown"), status


def open_macos_mic_privacy_settings() -> None:
    """Opens macOS System Settings directly to Privacy & Security -> Microphone."""
    if sys.platform != "darwin":
        return
    try:
        subprocess.Popen(
            ["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


@contextmanager
def prevent_app_nap():
    """Context manager to prevent macOS App Nap and system idle sleep during transcription.

    Launches `caffeinate -i -w <pid>` on macOS (Darwin) while the block executes,
    ensuring macOS Sonoma / Intel hardware does not throttle background worker threads
    when the app window is hidden, minimized, or occluded by Safari/Finder.
    """
    caffeinate_proc = None
    if sys.platform == "darwin":
        try:
            caffeinate_proc = subprocess.Popen(
                ["caffeinate", "-i", "-w", str(os.getpid())],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            caffeinate_proc = None
    try:
        yield
    finally:
        if caffeinate_proc:
            try:
                caffeinate_proc.terminate()
                caffeinate_proc.wait(timeout=1.0)
            except Exception:
                pass
