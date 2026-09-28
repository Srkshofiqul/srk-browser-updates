"""
Auto-Update Engine for Facebook Automation Suite.
Handles remote version checking, downloading update ZIP bundles, and extracting updates.
"""

import ctypes
import json
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

from PySide6.QtCore import QThread, Signal

from version import APP_VERSION, UPDATE_CHECK_URL


def create_unverified_ssl_context() -> Optional[ssl.SSLContext]:
    """Create SSL context that bypasses local Windows CA certificate missing errors."""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    except Exception:
        try:
            return ssl._create_unverified_context()
        except Exception:
            return None


def parse_version_tuple(ver_str: str) -> Tuple[int, ...]:
    """Parse version string like '1.0.4' into integer tuple (1, 0, 4)."""
    cleaned = str(ver_str).strip().lstrip("vV")
    parts = []
    for p in cleaned.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def check_remote_update_info(check_url: str = UPDATE_CHECK_URL, current_version: str = APP_VERSION) -> Tuple[bool, str, str, str]:
    """
    Fetch remote version.json and compare with current_version.
    Returns Tuple[has_update: bool, latest_version: str, download_url: str, changelog: str]
    """
    if not check_url or "username" in check_url.lower():
        return False, current_version, "", "No remote update server URL configured."

    try:
        import time
        sep = "&" if "?" in check_url else "?"
        fetch_url = f"{check_url}{sep}_cb={int(time.time())}"
        ssl_ctx = create_unverified_ssl_context()
        req = urllib.request.Request(
            fetch_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AutoUpdater/1.0"}
        )
        with urllib.request.urlopen(req, timeout=10, context=ssl_ctx) as response:
            if response.status != 200:
                return False, current_version, "", f"Server returned HTTP status {response.status}"

            data_str = response.read().decode("utf-8")
            data = json.loads(data_str)

            latest_ver = str(data.get("latest_version", current_version)).strip()
            download_url = str(data.get("download_url", "")).strip()
            changelog = str(data.get("changelog") or data.get("release_notes") or "Bug fixes and performance improvements.").strip()

            curr_tup = parse_version_tuple(current_version)
            latest_tup = parse_version_tuple(latest_ver)

            if latest_tup > curr_tup:
                return True, latest_ver, download_url, changelog

            return False, current_version, "", "You are using the latest version."
    except Exception as err:
        return False, current_version, "", f"Update check failed: {err}"


class UpdateCheckerThread(QThread):
    """Background thread to check for updates asynchronously."""

    check_finished = Signal(bool, str, str, str)  # has_update, latest_ver, download_url, changelog

    def __init__(self, check_url: str = UPDATE_CHECK_URL, current_version: str = APP_VERSION, parent: Optional[Any] = None) -> None:
        super().__init__(parent)
        self.check_url = check_url
        self.current_version = current_version

    def run(self) -> None:
        has_upd, latest_ver, download_url, changelog = check_remote_update_info(self.check_url, self.current_version)
        self.check_finished.emit(has_upd, latest_ver, download_url, changelog)


class UpdateDownloaderThread(QThread):
    """Background thread to download update ZIP bundle with progress reporting."""

    progress_updated = Signal(int, int)  # bytes_downloaded, total_bytes
    download_finished = Signal(bool, str, str)  # success, temp_file_path, error_msg

    def __init__(self, download_url: str, parent: Optional[Any] = None) -> None:
        super().__init__(parent)
        self.download_url = download_url

    def run(self) -> None:
        if not self.download_url:
            self.download_finished.emit(False, "", "Invalid download URL.")
            return

        try:
            ssl_ctx = create_unverified_ssl_context()
            req = urllib.request.Request(
                self.download_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AutoUpdater/1.0"}
            )
            with urllib.request.urlopen(req, timeout=30, context=ssl_ctx) as response:
                total_size = int(response.headers.get("Content-Length", 0))

                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
                temp_path = temp_file.name
                downloaded = 0

                chunk_size = 64 * 1024  # 64 KB
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    temp_file.write(chunk)
                    downloaded += len(chunk)
                    self.progress_updated.emit(downloaded, total_size)

                temp_file.close()
                self.download_finished.emit(True, temp_path, "")
        except Exception as err:
            self.download_finished.emit(False, "", f"Download failed: {err}")


import json
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Tuple, Dict, Any, Optional


def get_app_dir() -> Path:
    """Get real application directory whether running as script or PyInstaller EXE."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def apply_zip_update(zip_path: str, target_dir: Optional[Path] = None) -> Tuple[bool, str]:
    """
    Extract downloaded ZIP update package over target_dir.
    Skips user data directories (profiles, reports, database.db).
    Extracts updated EXE as .new to avoid Windows file locks.
    """
    if not target_dir:
        target_dir = get_app_dir()

    if not os.path.exists(zip_path):
        return False, "Update ZIP file not found."

    try:
        protected_items = {"profiles", "reports", "data", "logs", ".git", "database.db"}
        staging_dir = target_dir / "_update_staging"
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
        staging_dir.mkdir(parents=True, exist_ok=True)

        is_frozen = getattr(sys, 'frozen', False)
        exe_name = Path(sys.executable).name if is_frozen else "BrowserProfileManager.exe"
        new_exe_path = target_dir / (exe_name + ".new")

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            for member in zip_ref.namelist():
                filename = Path(member).name
                clean_member = member.replace("\\", "/")
                parts = [p for p in clean_member.split("/") if p]
                if not parts:
                    continue

                if len(parts) > 1 and parts[0].lower() == "browserprofilemanager":
                    relative_parts = parts[1:]
                else:
                    relative_parts = parts

                if not relative_parts:
                    continue

                first_part = relative_parts[0].lower()
                if first_part in protected_items:
                    continue

                relative_path = Path(*relative_parts)

                # If this member is the main EXE, extract it as .new in target_dir
                if is_frozen and filename.lower() == exe_name.lower():
                    with zip_ref.open(member) as source, open(new_exe_path, "wb") as target:
                        shutil.copyfileobj(source, target)
                    continue

                if clean_member.endswith("/"):
                    (staging_dir / relative_path).mkdir(parents=True, exist_ok=True)
                    continue

                dest_file = staging_dir / relative_path
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                with zip_ref.open(member) as source, open(dest_file, "wb") as target:
                    shutil.copyfileobj(source, target)

        try:
            os.remove(zip_path)
        except Exception:
            pass

        return True, "UPDATE_READY_RESTART"
    except Exception as err:
        return False, f"Failed to extract update package: {err}"


def clean_win32_environment() -> None:
    """Purge PyInstaller environment variables directly from Win32 C Kernel process environment block."""
    if os.name == "nt":
        try:
            for key in ["_MEIPASS", "_MEIPASS2", "_MEIPASS_DIR", "PYTHONPATH", "PYTHONHOME"]:
                os.environ.pop(key, None)
                try:
                    ctypes.windll.kernel32.SetEnvironmentVariableW(key, None)
                except Exception:
                    pass

            current_path = os.environ.get("PATH", "")
            if current_path:
                paths = current_path.split(os.pathsep)
                clean_paths = [p for p in paths if "_MEI" not in p]
                new_path = os.pathsep.join(clean_paths)
                os.environ["PATH"] = new_path
                try:
                    ctypes.windll.kernel32.SetEnvironmentVariableW("PATH", new_path)
                except Exception:
                    pass

            ctypes.windll.kernel32.SetDllDirectoryW(None)
        except Exception:
            pass


def restart_application() -> None:
    """Cleanly restart the desktop application without DLL or process lock errors."""
    app_dir = get_app_dir()
    current_pid = os.getpid()

    # Clean Win32 C Kernel process environment block
    clean_win32_environment()

    if getattr(sys, 'frozen', False):
        exe_path = Path(sys.executable).resolve()
        exe_dir = exe_path.parent
        exe_name = exe_path.name
        new_exe_name = exe_name + ".new"

        temp_dir = Path(os.environ.get("TEMP") or os.environ.get("TMP") or app_dir)
        bat_path = temp_dir / f"srbrowser_restart_{current_pid}.bat"
        bat_content = f"""@echo off
setlocal enabledelayedexpansion

:wait_loop
tasklist /fi "PID eq {current_pid}" 2>NUL | find /I "{current_pid}" >NUL
if "%ERRORLEVEL%"=="0" (
    timeout /t 1 /nobreak >NUL
    goto wait_loop
)

timeout /t 1 /nobreak >NUL

if exist "{exe_dir}\\{new_exe_name}" (
    move /y "{exe_dir}\\{new_exe_name}" "{exe_dir}\\{exe_name}"
)
if exist "{app_dir}\\_update_staging" (
    xcopy /s /e /y "{app_dir}\\_update_staging\\*" "{app_dir}" > NUL
    rmdir /s /q "{app_dir}\\_update_staging"
)

if exist "{app_dir}\\.tmp" (
    rmdir /s /q "{app_dir}\\.tmp" > NUL 2>&1
)

set "_MEIPASS="
set "_MEIPASS2="
set "_MEIPASS_DIR="
set "PYTHONPATH="
set "PYTHONHOME="

set "CLEANPATH="
for %%P in ("%PATH:;=" "%") do (
    set "ITEM=%%~P"
    if "!ITEM:_MEI=!"=="!ITEM!" (
        if defined CLEANPATH (
            set "CLEANPATH=!CLEANPATH!;!ITEM!"
        ) else (
            set "CLEANPATH=!ITEM!"
        )
    )
)
if defined CLEANPATH set "PATH=!CLEANPATH!"

start /I /d "{exe_dir}" "" "{exe_path}"
(goto) 2>nul & del "%~f0"
"""
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(bat_content)

        clean_env = os.environ.copy()
        for k in ["_MEIPASS", "_MEIPASS2", "_MEIPASS_DIR", "PYTHONPATH", "PYTHONHOME"]:
            clean_env.pop(k, None)

        if "PATH" in clean_env:
            paths = clean_env["PATH"].split(os.pathsep)
            clean_paths = [p for p in paths if "_MEI" not in p]
            clean_env["PATH"] = os.pathsep.join(clean_paths)

        subprocess.Popen(
            ["cmd.exe", "/c", str(bat_path)],
            cwd=str(app_dir),
            env=clean_env,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        )
    else:
        # Script mode: restart via python executable with wait-pid handover
        staging_dir = app_dir / "_update_staging"
        if staging_dir.exists():
            for item in staging_dir.iterdir():
                dest = app_dir / item.name
                if item.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest, ignore_errors=True)
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)
            shutil.rmtree(staging_dir, ignore_errors=True)

        clean_env = os.environ.copy()
        clean_env.pop("_MEIPASS", None)
        clean_env.pop("_MEIPASS2", None)

        clean_argv = []
        skip_next = False
        for arg in sys.argv:
            if skip_next:
                skip_next = False
                continue
            if arg == "--wait-pid":
                skip_next = True
                continue
            clean_argv.append(arg)

        cmd = [sys.executable] + clean_argv + ["--wait-pid", str(current_pid)]
        subprocess.Popen(
            cmd,
            cwd=str(app_dir),
            env=clean_env
        )

    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            for w in app.topLevelWidgets():
                setattr(w, "_is_restarting", True)
                setattr(w, "_force_exit", True)
            app.quit()
    except Exception:
        pass
    sys.exit(0)
