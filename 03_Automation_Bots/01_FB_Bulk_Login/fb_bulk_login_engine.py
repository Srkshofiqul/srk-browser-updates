import os
import sys
import time
import random
import re
import urllib.request
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from PySide6.QtCore import QThread, Signal
from playwright.sync_api import sync_playwright

# Import security and helpers from bot package
from fb_bulk_login_security import get_app_root_dir, check_srbrowser_heartbeat, get_effective_bot_license
from fb_bulk_login_helpers import (
    parse_profile_numbers_input,
    filter_profiles_by_target,
    check_facebook_login_status,
    dismiss_facebook_popup_notices,
    generate_profile_fingerprint,
    get_stealth_anti_detect_script
)


def resolve_user_data_dir(profile_data: Dict[str, Any]) -> str:
    """Smart resolution of the exact profile folder for srkBrowser."""
    if profile_data.get("user_data_dir"):
        return str(Path(profile_data["user_data_dir"]).resolve())

    # 1. Try to resolve directly via ProfileManager
    pid = profile_data.get("id")
    if pid:
        try:
            from profile_manager import ProfileManager
            pm = ProfileManager()
            p_f = pm.get_profile_folder(pid)
            if p_f and p_f.exists():
                return str(p_f.resolve())
        except Exception:
            pass
        try:
            from core.profile_manager import ProfileManager
            pm = ProfileManager()
            p_f = pm.get_profile_folder(pid)
            if p_f and p_f.exists():
                return str(p_f.resolve())
        except Exception:
            pass

    app_root = get_app_root_dir()
    pnum = str(profile_data.get("number", profile_data.get("name", ""))).strip()

    # 2. Check users directories in 01_Main_Software/core/profiles/users/*
    core_users_dir = app_root / "01_Main_Software" / "core" / "profiles" / "users"
    if core_users_dir.exists() and pnum:
        for u_folder in core_users_dir.iterdir():
            if u_folder.is_dir():
                cand = u_folder / pnum
                if cand.exists() and cand.is_dir():
                    return str(cand.resolve())

    # 3. Fallback standard check
    profiles_base = app_root / "profiles"
    if not profiles_base.exists():
        profiles_base = app_root / "01_Main_Software" / "core" / "profiles"

    clean_digits = re.sub(r"\D", "", pnum)
    candidates = [pnum]
    if clean_digits:
        n_val = int(clean_digits)
        candidates.extend([f"Profile{n_val:03d}", f"Profile{n_val}", str(n_val)])

    for cand in candidates:
        p_dir = profiles_base / cand
        if p_dir.exists() and p_dir.is_dir():
            return str(p_dir.resolve())

    p_dir = profiles_base / (candidates[0] if candidates else "Profile001")
    p_dir.mkdir(parents=True, exist_ok=True)
    return str(p_dir.resolve())

def calculate_cdp_port(profile_data: Dict[str, Any], index: int = 1) -> int:
    """Calculates collision-free CDP port based on profile number."""
    raw_num = str(profile_data.get("number", profile_data.get("name", "")))
    digits = re.sub(r"\D", "", raw_num)
    if digits.isdigit():
        return 9200 + (int(digits) % 500)
    return 9200 + (index % 500)

def get_chrome_executable_path() -> Optional[str]:
    """Finds srkBrowser's bundled Portable Chromium."""
    try:
        from browser import BrowserLauncher
        launcher = BrowserLauncher()
        exe = launcher.get_default_browser_executable()
        if exe and os.path.exists(exe):
            return str(Path(exe).resolve())
    except Exception:
        pass

    try:
        from core.browser import BrowserLauncher
        launcher = BrowserLauncher()
        exe = launcher.get_default_browser_executable()
        if exe and os.path.exists(exe):
            return str(Path(exe).resolve())
    except Exception:
        pass

    app_root = get_app_root_dir()
    candidates = [
        app_root / "chromium" / "chrome.exe",
        app_root / "01_Main_Software" / "chromium" / "chrome.exe",
        app_root / "01_Main_Software" / "core" / "chrome" / "chrome.exe",
        app_root / "chrome" / "chrome.exe",
        app_root / "01_Main_Software" / "chrome" / "chrome.exe"
    ]
    for c in candidates:
        if c.exists():
            return str(c.resolve())
    return None

def kill_profile_chrome_process(user_data_dir: str, cdp_port: int = 0) -> None:
    """Forcefully terminates any Chrome / Chromium process for a given folder or port."""
    if not user_data_dir and not cdp_port:
        return

    # 1. CDP close request
    if cdp_port:
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{cdp_port}/json/close", data=b"")
            urllib.request.urlopen(req, timeout=1)
        except Exception:
            pass

    # 2. Windows process termination
    if os.name == 'nt' and user_data_dir:
        try:
            folder_name = Path(user_data_dir).name
            if folder_name and len(folder_name) > 1:
                cmd_ps = f'powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \\"Name = \'chrome.exe\' and CommandLine like \'%{folder_name}%\'\\" | Invoke-CimMethod -MethodName Terminate"'
                subprocess.run(cmd_ps, shell=True, capture_output=True, timeout=3)
                cmd_wmic = f'wmic process where "name=\'chrome.exe\' and commandline like \'%%{folder_name}%%\'" call terminate'
                subprocess.run(cmd_wmic, shell=True, capture_output=True, timeout=2)
        except Exception:
            pass

def apply_smart_profile_window_icon_win32(user_data_dir: str, ico_path: Path, num_text: str = "") -> None:
    """
    Applies custom srkBrowser Smart Number Badge icon and AppUserModelID to the Chromium Taskbar window.
    """
    if os.name != "nt" or not ico_path.exists():
        return

    main_pid = os.getpid()

    def _worker():
        import time
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x00000010

        hIcon = user32.LoadImageW(
            None,
            str(ico_path.resolve()),
            IMAGE_ICON,
            0,
            0,
            LR_LOADFROMFILE
        )
        if not hIcon:
            return

        for _ in range(16):
            time.sleep(0.3)
            found_hwnds = []

            def EnumWindowsProc(hwnd, lParam):
                if user32.IsWindowVisible(hwnd):
                    lpdwProcessId = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(lpdwProcessId))
                    pid = lpdwProcessId.value
                    if pid == main_pid or pid == 0:
                        return True

                    try:
                        cls_buf = ctypes.create_unicode_buffer(256)
                        user32.GetClassNameW(hwnd, cls_buf, 256)
                        c_name = cls_buf.value
                        if "Chrome_WidgetWin" in c_name:
                            found_hwnds.append(hwnd)
                    except Exception:
                        pass
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            user32.EnumWindows(WNDENUMPROC(EnumWindowsProc), 0)

            if found_hwnds:
                for hwnd in found_hwnds:
                    try:
                        user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hIcon)
                        user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hIcon)
                        user32.SetPropW(hwnd, "AppUserModelID", f"srkBrowser.Profile.{num_text}")
                    except Exception:
                        pass
                break

    import threading
    threading.Thread(target=_worker, daemon=True).start()

def launch_native_profile_browser(
    playwright_instance: Any,
    profile_data: Dict[str, Any],
    profile_index: int = 1,
    headless: bool = False,
    log_func: Optional[Any] = None
) -> Tuple[Any, Any]:
    """
    Universal srkBrowser Profile Launcher:
    1. Generates custom Number Badge Icon & Profile Inspector Extension.
    2. Launches native Portable Chromium via Playwright launch_persistent_context.
    3. Connects Win32 Taskbar icon and AppUserModelID for instant numbered badge display on taskbar.
    Returns: (context, page)
    """
    def log(msg: str):
        if log_func:
            try:
                log_func(msg)
            except Exception:
                try:
                    log_func(msg.encode("ascii", "replace").decode("ascii"))
                except Exception:
                    pass

    pname = profile_data.get("name", f"Profile{profile_index:03d}")
    user_data_dir = resolve_user_data_dir(profile_data)
    p_dir = Path(user_data_dir)

    # Clean leftover singleton locks
    lock_f = p_dir / "SingletonLock"
    if lock_f.exists():
        try: lock_f.unlink(missing_ok=True)
        except Exception: pass

    # Native Browser Language Setup: Ensure Chromium profile is permanently set to English (US)
    try:
        import json
        def_dir = p_dir / "Default"
        def_dir.mkdir(parents=True, exist_ok=True)
        pref_file = def_dir / "Preferences"
        pref_data = {}
        if pref_file.exists():
            try:
                with open(pref_file, "r", encoding="utf-8") as f:
                    pref_data = json.load(f)
            except Exception:
                pref_data = {}
        if not isinstance(pref_data, dict):
            pref_data = {}
        pref_data.setdefault("intl", {})["accept_languages"] = "en-US,en"
        pref_data.setdefault("intl", {})["selected_languages"] = "en-US,en"
        pref_data.setdefault("spellcheck", {})["dictionaries"] = ["en-US"]
        pref_data.setdefault("spellcheck", {})["dictionary"] = "en-US"
        with open(pref_file, "w", encoding="utf-8") as f:
            json.dump(pref_data, f, indent=2)
    except Exception:
        pass

    chrome_exe = get_chrome_executable_path()
    raw_num = str(profile_data.get("number", profile_index)).replace("Profile", "").replace("#", "").strip()
    num_text = f"{int(raw_num):02d}" if raw_num.isdigit() else (raw_num or "01")
    prof_num_int = int(raw_num) if raw_num.isdigit() else 1

    # 1. Generate Smart Profile Badge Icon .ico
    ico_path = p_dir / "profile_icon.ico"
    color_name = profile_data.get("color", "SkyBlue")
    color_hex = "#38bdf8"
    try:
        from browser import generate_profile_icon_ico, create_profile_inspector_extension
    except ImportError:
        try:
            from core.browser import generate_profile_icon_ico, create_profile_inspector_extension
        except ImportError:
            def generate_profile_icon_ico(*a, **kw): return False
            def create_profile_inspector_extension(*a, **kw): return ""

    try:
        from config import COLOR_PALETTE
        color_hex = COLOR_PALETTE.get(color_name, "#38bdf8") if isinstance(COLOR_PALETTE, dict) else "#38bdf8"
    except Exception:
        pass

    try:
        generate_profile_icon_ico(num_text, ico_path, color_hex, prof_num_int)
    except Exception:
        pass

    badge_ext_path = ""
    try:
        badge_ext_path = create_profile_inspector_extension(p_dir, profile_data)
    except Exception:
        pass

    # Generate unique anti-detect fingerprint per profile
    fp = generate_profile_fingerprint(profile_data)
    log(f"  🛡️ Anti-Detect Fingerprint: Screen {fp['width']}x{fp['height']} | CPU Cores {fp['hardware_concurrency']} | RAM {fp['device_memory']}GB")

    args = [
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "--no-service-autorun",
        "--test-type",
        "--disable-infobars",
        "--disable-notifications",
        "--deny-permission-prompts",
        "--disable-popup-blocking",
        "--no-sandbox",
        "--lang=en-US",
        "--disable-save-password-bubble",
        "--credentials-enable-service=false",
        "--profile.password_manager_enabled=false",
        "--disable-single-click-autofill",
        "--password-store=basic",
        "--disable-blink-features=AutomationControlled",
        f"--user-agent={fp['user_agent']}",
        f"--window-size={fp['width']},{fp['height']}"
    ]

    launch_kwargs = {
        "user_data_dir": str(p_dir.resolve()),
        "headless": headless,
        "viewport": None,
        "args": args,
        "no_viewport": True
    }
    if chrome_exe and os.path.exists(chrome_exe):
        launch_kwargs["executable_path"] = chrome_exe

    log(f"  🚀 Launching srkBrowser Portable Chromium for '{pname}' (#{num_text})...")

    context = None
    page = None
    try:
        context = playwright_instance.chromium.launch_persistent_context(**launch_kwargs)
    except Exception as l_err:
        log(f"  ⚠️ Retrying persistent launch: {l_err}")
        time.sleep(1.0)
        lock_f = p_dir / "SingletonLock"
        if lock_f.exists():
            try: lock_f.unlink(missing_ok=True)
            except Exception: pass
        try:
            context = playwright_instance.chromium.launch_persistent_context(**launch_kwargs)
        except Exception as l_err2:
            log(f"  ❌ Launch failed: {l_err2}")
            return None, None

    if context:
        # Inject stealth anti-detect script across all pages and frames
        try:
            stealth_js = get_stealth_anti_detect_script(fp)
            context.add_init_script(stealth_js)
        except Exception:
            pass

        # 2. Hook Win32 Taskbar to display custom Number Badge Icon
        if ico_path.exists() and os.name == "nt":
            try:
                apply_smart_profile_window_icon_win32(user_data_dir, ico_path, num_text)
            except Exception:
                pass

        try:
            context.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})
        except Exception:
            pass
        page = context.pages[0] if context.pages else context.new_page()
        try:
            page.bring_to_front()
        except Exception:
            pass
        register_active_browser_session(context, profile_data)

    return context, page

# Global active process registry for instant nuclear shutdown
_ACTIVE_SESSIONS: List[Tuple[Any, Dict[str, Any]]] = []

def register_active_browser_session(context: Any, profile_data: Dict[str, Any]) -> None:
    _ACTIVE_SESSIONS.append((context, profile_data))

def unregister_active_browser_session(context: Any) -> None:
    global _ACTIVE_SESSIONS
    _ACTIVE_SESSIONS = [(c, p) for c, p in _ACTIVE_SESSIONS if c != context]

def get_active_browser_sessions_count() -> int:
    global _ACTIVE_SESSIONS
    return len(_ACTIVE_SESSIONS)

class GracefulShutdownWorker(QThread):
    """
    Background Asynchronous Shutdown Thread:
    Gracefully closes active Playwright contexts and terminates Chromium processes with pacing
    so the main Qt GUI never freezes or hangs ('Not Responding').
    """
    progress_signal = Signal(int, int, str)  # (current, total, profile_name)
    finished_signal = Signal(int)             # total_closed

    def __init__(self, profiles: Optional[List[Dict[str, Any]]] = None, parent: Optional[Any] = None):
        super().__init__(parent)
        self.profiles = profiles or []

    def run(self) -> None:
        global _ACTIVE_SESSIONS
        active_list = list(_ACTIVE_SESSIONS)
        _ACTIVE_SESSIONS.clear()

        # Build list of active items to close
        close_targets = []
        for ctx, pdata in active_list:
            pname = pdata.get("name", "Active Profile") if pdata else "Active Profile"
            close_targets.append((ctx, pdata, pname))

        # If no active browser sessions are registered, finish immediately in 0 ms
        if not close_targets:
            self.finished_signal.emit(0)
            return

        total = len(close_targets)
        closed_count = 0

        for idx, (ctx, pdata, pname) in enumerate(close_targets, start=1):
            self.progress_signal.emit(idx, total, f"Closing {pname} ({idx}/{total})...")
            
            # Close Playwright context
            if ctx:
                try:
                    if hasattr(ctx, "browser") and ctx.browser:
                        ctx.browser.close()
                    else:
                        ctx.close()
                except Exception:
                    pass

            # Terminate Chromium process
            if pdata:
                try:
                    u_dir = resolve_user_data_dir(pdata)
                    port = calculate_cdp_port(pdata)
                    kill_profile_chrome_process(u_dir, port)
                except Exception:
                    pass

            closed_count += 1
            time.sleep(0.08)

        self.finished_signal.emit(closed_count)

def kill_all_bot_browsers(profiles: Optional[List[Dict[str, Any]]] = None) -> None:
    """Instant synchronous termination helper."""
    global _ACTIVE_SESSIONS
    for ctx, pdata in list(_ACTIVE_SESSIONS):
        try:
            if hasattr(ctx, "browser") and ctx.browser:
                ctx.browser.close()
            else:
                ctx.close()
        except Exception:
            pass
        if pdata:
            try:
                user_dir = resolve_user_data_dir(pdata)
                cdp_p = calculate_cdp_port(pdata)
                kill_profile_chrome_process(user_dir, cdp_p)
            except Exception:
                pass

    _ACTIVE_SESSIONS.clear()
    if profiles:
        for p in profiles:
            try:
                u_dir = resolve_user_data_dir(p)
                port = calculate_cdp_port(p)
                kill_profile_chrome_process(u_dir, port)
            except Exception:
                pass

def close_native_profile_browser(context: Any, profile_data: Dict[str, Any]) -> None:
    """Closes Playwright CDP session and forcefully terminates the Chrome process on Windows."""
    unregister_active_browser_session(context)
    if context:
        try:
            if hasattr(context, "browser") and context.browser:
                context.browser.close()
            else:
                context.close()
        except Exception:
            pass

    if profile_data:
        try:
            user_dir = resolve_user_data_dir(profile_data)
            cdp_p = calculate_cdp_port(profile_data)
        except Exception:
            pass

def isolate_greenlet_context() -> None:
    """Isolates greenlet parent context for QThread / worker thread execution safety."""
    try:
        import greenlet
        g = greenlet.getcurrent()
        if hasattr(g, 'parent') and g.parent is not None:
            g.parent = None
    except Exception:
        pass

class BaseMasterBotThread(QThread):
    """
    Standard Base Worker Thread for all srkBrowser Automation Bots.
    Provides standard lifecycle, progress reporting, thread-safe cancellation, and logging.
    """
    log_emitted = Signal(str)
    progress_updated = Signal(int, int)
    stats_updated = Signal(int, int, int) # (success_count, failed_count, remaining_count)
    finished_signal = Signal(bool, str, dict)

    def __init__(
        self,
        profiles_to_run: List[Dict[str, Any]],
        max_concurrent_browsers: int = 1,
        headless: bool = False,
        bot_title: str = "Automation Bot",
        stagger_delay_sec: float = 2.0,
        parent: Optional[Any] = None
    ):
        super().__init__(parent)
        self.profiles_to_run = profiles_to_run
        self.max_concurrent_browsers = max(1, max_concurrent_browsers)
        self.headless = headless
        self.bot_title = bot_title
        self.stagger_delay_sec = max(0.5, float(stagger_delay_sec))
        self.is_running = True
        self.stop_requested = False
        self.report_rows: List[Dict[str, Any]] = []

    def emit_log(self, text: str) -> None:
        self.log_emitted.emit(text)

    def stop(self) -> None:
        self.stop_requested = True
        self.is_running = False
        kill_all_bot_browsers(self.profiles_to_run)

    def execute_profile_task(self, page: Any, context: Any, pdata: Dict[str, Any], idx: int, total: int) -> Tuple[bool, str, str]:
        """
        Executes Facebook Bulk ID Login for a single browser profile.
        Returns (success: bool, status_message: str, screenshot_path: str)
        """
        from fb_bulk_login_helpers import perform_facebook_login_flow
        return perform_facebook_login_flow(page, context, pdata, log_func=self.emit_log)

    def _run_single_profile(self, playwright_instance: Any, pdata: Dict[str, Any], idx: int, total: int) -> Tuple[bool, str, str]:
        pname = pdata.get("name", f"Profile_{idx:03d}")
        num = pdata.get("number", f"#{idx:02d}")
        self.emit_log(f"🚀 [{pname} ({num})] Launching srkBrowser Chromium Profile ({idx}/{total})...")

        context = None
        page = None
        t_start = time.time()
        ss_path = ""
        try:
            context, page = launch_native_profile_browser(
                playwright_instance=playwright_instance,
                profile_data=pdata,
                profile_index=idx,
                headless=self.headless,
                log_func=self.emit_log
            )
            if not page or not context:
                self.emit_log(f"❌ [{pname}] Failed to attach CDP session to browser.")
                return False, "Failed to connect CDP", ""

            if self.stop_requested:
                return False, "Stopped by user", ""

            # Execute automation task
            self.emit_log(f"⚡ [{pname}] Running Facebook Authentication Flow...")
            success, msg, ss_path = self.execute_profile_task(page, context, pdata, idx, total)
            if success:
                self.emit_log(f"✅ [{pname}] Finished: {msg}")
            else:
                if ss_path:
                    self.emit_log(f"⚠️ [{pname}] Failed: {msg} (📸 Screenshot saved: {Path(ss_path).name})")
                else:
                    self.emit_log(f"⚠️ [{pname}] Failed: {msg}")
            return success, msg, ss_path

        except Exception as err:
            self.emit_log(f"⚠️ [{pname}] Execution notice: {err}")
            return False, str(err), ss_path
        finally:
            dur = round(time.time() - t_start, 1)
            if context:
                close_native_profile_browser(context, pdata)

    def _run_single_profile_worker(self, pdata: Dict[str, Any], idx: int, total: int) -> Tuple[bool, str, str]:
        isolate_greenlet_context()
        try:
            with sync_playwright() as p:
                return self._run_single_profile(p, pdata, idx, total)
        except Exception as e:
            return False, str(e), ""

    def run(self) -> None:
        total = len(self.profiles_to_run)
        if total == 0:
            self.finished_signal.emit(True, "No profiles to run", {})
            return

        self.emit_log(f"🏁 Starting {self.bot_title} on {total} profile(s) with {self.max_concurrent_browsers} thread(s)...")
        completed = 0
        success_count = 0
        failed_count = 0
        self.report_rows = []

        # Initialize Instant Real-Time Reporter (saves each account to disk immediately)
        live_reporter = None
        try:
            from fb_bulk_login_helpers import LiveAutomationReporter
            live_reporter = LiveAutomationReporter(bot_title=self.bot_title)
            self.emit_log(f"📝 [Report Ready]: {Path(live_reporter.get_report_path()).name}")
        except Exception as e:
            self.emit_log(f"⚠️ [Live Reporter Notice]: {e}")

        # Emit initial stats
        self.stats_updated.emit(0, 0, total)

        try:
            if self.max_concurrent_browsers == 1:
                isolate_greenlet_context()
                with sync_playwright() as p:
                    for idx, pdata in enumerate(self.profiles_to_run, start=1):
                        if self.stop_requested:
                            break
                        t_pstart = time.time()
                        ok, msg, ss_file = self._run_single_profile(p, pdata, idx, total)
                        p_dur = round(time.time() - t_pstart, 1)

                        if ok:
                            success_count += 1
                        else:
                            failed_count += 1

                        completed += 1
                        rem = max(0, total - completed)
                        row_item = {
                            "index": idx,
                            "number": pdata.get("number", f"#{idx:02d}"),
                            "name": pdata.get("name", ""),
                            "status": "Success" if ok else "Failed",
                            "message": msg,
                            "screenshot_file": Path(ss_file).name if ss_file else "",
                            "duration": p_dur
                        }
                        self.report_rows.append(row_item)
                        if live_reporter:
                            live_reporter.append_row(row_item)
                        self.progress_updated.emit(completed, total)
                        self.stats_updated.emit(success_count, failed_count, rem)
            else:
                import threading
                lock = threading.Lock()

                def _handle_profile_done(fut, idx, pdata, t_pstart):
                    nonlocal completed, success_count, failed_count
                    ok, msg, ss_file = False, "Execution error", ""
                    try:
                        ok, msg, ss_file = fut.result()
                    except Exception as ex:
                        msg = str(ex)

                    with lock:
                        if ok:
                            success_count += 1
                        else:
                            failed_count += 1

                        completed += 1
                        rem = max(0, total - completed)
                        p_dur = round(time.time() - t_pstart, 1)
                        row_item = {
                            "index": idx,
                            "number": pdata.get("number", f"#{idx:02d}"),
                            "name": pdata.get("name", ""),
                            "status": "Success" if ok else "Failed",
                            "message": msg,
                            "screenshot_file": Path(ss_file).name if ss_file else "",
                            "duration": p_dur
                        }
                        self.report_rows.append(row_item)
                        if live_reporter:
                            live_reporter.append_row(row_item)
                        self.progress_updated.emit(completed, total)
                        self.stats_updated.emit(success_count, failed_count, rem)

                with ThreadPoolExecutor(max_workers=self.max_concurrent_browsers) as executor:
                    futures_list = []
                    for idx, pdata in enumerate(self.profiles_to_run, start=1):
                        if self.stop_requested:
                            break
                        fut = executor.submit(self._run_single_profile_worker, pdata, idx, total)
                        fut.add_done_callback(lambda f, i=idx, p=pdata, t=time.time(): _handle_profile_done(f, i, p, t))
                        futures_list.append(fut)
                        # Stagger concurrent browser launches gracefully
                        if idx < total and self.stagger_delay_sec > 0:
                            time.sleep(self.stagger_delay_sec)

                    for f in futures_list:
                        try:
                            f.result()
                        except Exception:
                            pass
        except Exception as p_err:
            self.emit_log(f"❌ Engine exception: {p_err}")

        # Retrieve report path from live reporter or fallback
        report_path = ""
        if live_reporter and live_reporter.get_report_path():
            report_path = live_reporter.get_report_path()
        else:
            try:
                from fb_bulk_login_helpers import save_automation_report_csv
                report_path = save_automation_report_csv(self.report_rows, self.bot_title)
            except Exception:
                pass

        if report_path:
            self.emit_log(f"📊 [Report Saved]: {Path(report_path).name}")

        result_payload = {
            "completed": completed,
            "success": success_count,
            "failed": failed_count,
            "total": total,
            "report_path": report_path
        }

        if self.stop_requested:
            self.emit_log("🛑 Automation stopped.")
            self.finished_signal.emit(False, "Stopped by user", result_payload)
        else:
            self.emit_log(f"🎉 All {total} profile tasks completed! (Success: {success_count}/{total}, Failed: {failed_count})")
            self.finished_signal.emit(True, "Completed", result_payload)


class FbBulkLoginWorkerThread(BaseMasterBotThread):
    """
    Dedicated Facebook Bulk Login Worker Thread:
    - Receives a list of account credentials (from Excel/CSV/Text).
    - For each account:
      1. Creates a clean, isolated srkBrowser profile inside target_group.
      2. Launches Portable Chromium with unique profile & taskbar branding.
      3. Performs Facebook login, solves 2FA TOTP code, dismisses popups.
      4. Saves fresh session cookies on success; captures failure screenshots.
      5. Emits live progress and updates metric chips.
    """
    def __init__(
        self,
        accounts_to_run: List[Dict[str, Any]],
        target_group: str = "Default",
        profile_mgr: Optional[Any] = None,
        max_concurrent_browsers: int = 1,
        headless: bool = False,
        bot_title: str = "Facebook Bulk ID Login Studio",
        stagger_delay_sec: float = 2.0,
        auto_convert_en: bool = False,
        parent: Optional[Any] = None
    ):
        super().__init__(
            profiles_to_run=[],
            max_concurrent_browsers=max_concurrent_browsers,
            headless=headless,
            bot_title=bot_title,
            stagger_delay_sec=stagger_delay_sec,
            parent=parent
        )
        self.accounts_to_run = accounts_to_run
        self.target_group = target_group or "Default"
        self.profile_mgr = profile_mgr
        self.auto_convert_en = auto_convert_en
        self.created_profiles: List[Dict[str, Any]] = []

    def _run_single_account(self, playwright_instance: Any, acc: Dict[str, Any], idx: int, total: int) -> Tuple[bool, str, str, str]:
        """
        Runs complete flow for single account directly inside srkBrowser:
        1. Creates profile directly via ProfileManager in the selected target_group.
        2. Launches Portable Chromium with custom CDP port.
        3. Connects Playwright over CDP and performs Facebook login.
        4. If Success:
           - Saves fresh cookies and metadata to profile.json & ProfileManager.
           - Keeps profile active in srkBrowser.
        5. If Failure:
           - Closes browser.
           - Calls ProfileManager.delete_profile(...) to remove it from srkBrowser.
        """
        uid = str(acc.get("uid", "")).strip()
        pwd = str(acc.get("password", "")).strip()
        two_fa = str(acc.get("two_factor", "")).strip()
        cookie = str(acc.get("cookie", "")).strip()
        pname = f"FB_{uid}" if uid else f"FB_Profile_{idx:03d}"

        # 1. Create Profile in srkBrowser
        pdata = None
        if self.profile_mgr and hasattr(self.profile_mgr, "create_profile"):
            try:
                pdata = self.profile_mgr.create_profile(
                    name=pname,
                    group=self.target_group,
                    uid=uid,
                    password=pwd,
                    secret_2fa=two_fa,
                    cookie=cookie,
                    notes=f"UID: {uid} | 2FA: {two_fa}",
                    color="#89b4fa",
                    save_db=True,
                    sync_cloud=False
                )
                self.created_profiles.append(pdata)
                self.emit_log(f"✨ [Profile Created] '{pname}' (#{pdata.get('number')}) in Group '{self.target_group}'.")
            except Exception as c_err:
                self.emit_log(f"⚠️ ProfileManager creation note: {c_err}")

        if not pdata:
            pdata = {
                "name": pname,
                "number": f"#{idx:02d}",
                "group": self.target_group,
                "uid": uid,
                "password": pwd,
                "fb_uid": uid,
                "fb_pass": pwd,
                "fb_2fa": two_fa,
                "two_factor": two_fa,
                "cookie": cookie,
                "cookies": cookie,
                "notes": f"FB UID: {uid}"
            }

        num = pdata.get("number", f"#{idx:02d}")
        self.emit_log(f"🚀 [{pname} ({num})] Launching srkBrowser Chromium Profile ({idx}/{total})...")

        context = None
        page = None
        t_start = time.time()
        ss_path = ""
        try:
            context, page = launch_native_profile_browser(
                playwright_instance=playwright_instance,
                profile_data=pdata,
                profile_index=idx,
                headless=self.headless,
                log_func=self.emit_log
            )
            if not page or not context:
                self.emit_log(f"❌ [{pname}] Failed to attach CDP session to browser.")
                if pdata.get("id") and self.profile_mgr and hasattr(self.profile_mgr, "delete_profile"):
                    try:
                        self.profile_mgr.delete_profile(pdata["id"], save_db=True, sync_cloud=False)
                    except Exception:
                        pass
                return False, "Failed to connect CDP", "", pname

            if self.stop_requested:
                if pdata.get("id") and self.profile_mgr and hasattr(self.profile_mgr, "delete_profile"):
                    try:
                        self.profile_mgr.delete_profile(pdata["id"], save_db=True, sync_cloud=False)
                    except Exception:
                        pass
                return False, "Stopped by user", "", pname

            # Execute Facebook login
            self.emit_log(f"⚡ [{pname}] Authenticating Facebook Account...")
            from fb_bulk_login_helpers import perform_facebook_login_flow
            success, msg, ss_path = perform_facebook_login_flow(
                page=page, 
                context=context, 
                pdata=pdata, 
                auto_convert_en=self.auto_convert_en, 
                log_func=self.emit_log
            )

            # Close browser context to flush SQLite DB and cookies to disk
            if context:
                close_native_profile_browser(context, pdata)
                context = None
                time.sleep(0.8)

            if success:
                self.emit_log(f"✅ [{pname}] Success: {msg}")
                # Save session cookies & profile metadata
                if self.profile_mgr:
                    try:
                        pid = pdata.get("id")
                        if pid and hasattr(self.profile_mgr, "update_profile"):
                            cookie_str = pdata.get("cookie", "") or cookie
                            final_uid = pdata.get("uid", "") or uid
                            clean_notes_parts = [f"FB UID: {final_uid}", f"Pass: {pwd}"]
                            clean_2fa = str(two_fa).strip() if two_fa and str(two_fa).strip().lower() not in ("none", "n/a", "null") else ""
                            if clean_2fa:
                                clean_notes_parts.append(f"2FA: {clean_2fa}")

                            update_data = {
                                "cookie": cookie_str,
                                "cookies": cookie_str,
                                "cookies_json": pdata.get("cookies_json", []),
                                "fb_uid": final_uid,
                                "fb_pass": pwd,
                                "fb_2fa": clean_2fa,
                                "assigned_scripts": ["fb_account_info", "fb_relogin"],
                                "notes": " | ".join(clean_notes_parts)
                            }
                            if final_uid:
                                update_data["uid"] = final_uid
                            self.profile_mgr.update_profile(pid, update_data)
                        elif hasattr(self.profile_mgr, "save_profiles"):
                            self.profile_mgr.save_profiles()
                        self.emit_log(f"  💾 [Profile Saved] Saved active session for '{pname}' with Info & Re-login scripts.")
                    except Exception as s_err:
                        self.emit_log(f"  ⚠️ Session save notice: {s_err}")
            else:
                if ss_path:
                    self.emit_log(f"⚠️ [{pname}] Failed: {msg} (📸 Screenshot: {Path(ss_path).name})")
                else:
                    self.emit_log(f"⚠️ [{pname}] Failed: {msg}")

                # Delete failed profile from srkBrowser
                if pdata.get("id") and self.profile_mgr and hasattr(self.profile_mgr, "delete_profile"):
                    try:
                        self.profile_mgr.delete_profile(pdata["id"], save_db=True, sync_cloud=False)
                        self.emit_log(f"  🗑️ [Auto-Cleaned] Removed failed profile '{pname}' from srkBrowser.")
                    except Exception as del_err:
                        self.emit_log(f"  ⚠️ Could not delete failed profile: {del_err}")

            pdata_result = {
                "number": pdata.get("number", f"#{idx:02d}"),
                "uid": uid,
                "password": pwd,
                "two_factor": two_fa,
                "cookie": pdata.get("cookie", cookie)
            }
            return success, msg, ss_path, pdata_result

        except Exception as err:
            self.emit_log(f"⚠️ [{pname}] Execution notice: {err}")
            if pdata.get("id") and self.profile_mgr and hasattr(self.profile_mgr, "delete_profile"):
                try:
                    self.profile_mgr.delete_profile(pdata["id"], save_db=True, sync_cloud=False)
                except Exception:
                    pass
            pdata_result = {
                "number": pdata.get("number", f"#{idx:02d}") if pdata else f"#{idx:02d}",
                "uid": uid,
                "password": pwd,
                "two_factor": two_fa,
                "cookie": cookie
            }
            return False, str(err), ss_path, pdata_result
        finally:
            dur = round(time.time() - t_start, 1)
            if context:
                close_native_profile_browser(context, pdata)

    def _run_single_account_worker(self, acc: Dict[str, Any], idx: int, total: int) -> Tuple[bool, str, str, Dict[str, Any]]:
        isolate_greenlet_context()
        try:
            with sync_playwright() as p:
                return self._run_single_account(p, acc, idx, total)
        except Exception as e:
            return False, str(e), "", {
                "number": f"#{idx:02d}",
                "uid": str(acc.get("uid", "")),
                "password": str(acc.get("password", "")),
                "two_factor": str(acc.get("two_factor", "")),
                "cookie": str(acc.get("cookie", ""))
            }

    def run(self) -> None:
        total = len(self.accounts_to_run)
        if total == 0:
            self.finished_signal.emit(True, "No accounts to process", {})
            return

        self.emit_log(f"🏁 Starting Facebook Bulk Login on {total} account(s) in Group '{self.target_group}' ({self.max_concurrent_browsers} thread(s))...")
        completed = 0
        success_count = 0
        failed_count = 0
        self.report_rows = []

        # Initialize Instant Real-Time Reporter (saves each account to disk immediately)
        live_reporter = None
        try:
            from fb_bulk_login_helpers import LiveAutomationReporter
            live_reporter = LiveAutomationReporter(bot_title=self.bot_title)
            self.emit_log(f"📝 [Report Ready]: {Path(live_reporter.get_report_path()).name}")
        except Exception as e:
            self.emit_log(f"⚠️ [Live Reporter Notice]: {e}")

        self.stats_updated.emit(0, 0, total)

        try:
            if self.max_concurrent_browsers == 1:
                isolate_greenlet_context()
                with sync_playwright() as p:
                    for idx, acc in enumerate(self.accounts_to_run, start=1):
                        if self.stop_requested:
                            break
                        t_start = time.time()
                        ok, msg, ss_file, pdata_res = self._run_single_account(p, acc, idx, total)
                        dur = round(time.time() - t_start, 1)

                        if ok:
                            success_count += 1
                        else:
                            failed_count += 1

                        completed += 1
                        rem = max(0, total - completed)
                        row_item = {
                            "Profile_Number": pdata_res.get("number", f"#{idx:02d}") if isinstance(pdata_res, dict) else f"#{idx:02d}",
                            "UID": pdata_res.get("uid", "") if isinstance(pdata_res, dict) else str(acc.get("uid", "")),
                            "Password": pdata_res.get("password", "") if isinstance(pdata_res, dict) else str(acc.get("password", "")),
                            "2FA_Secret": pdata_res.get("two_factor", "") if isinstance(pdata_res, dict) else str(acc.get("two_factor", "")),
                            "Cookie": pdata_res.get("cookie", "") if isinstance(pdata_res, dict) else str(acc.get("cookie", "")),
                            "Status": "Success" if ok else "Failed",
                            "Message": msg
                        }
                        self.report_rows.append(row_item)
                        if live_reporter:
                            live_reporter.append_row(row_item)
                        self.progress_updated.emit(completed, total)
                        self.stats_updated.emit(success_count, failed_count, rem)
            else:
                import threading
                lock = threading.Lock()

                def _handle_account_done(fut, idx, acc, t_start):
                    nonlocal completed, success_count, failed_count
                    ok, msg, ss_file, pdata_res = False, "Execution error", "", {}
                    try:
                        ok, msg, ss_file, pdata_res = fut.result()
                    except Exception as ex:
                        msg = str(ex)

                    with lock:
                        if ok:
                            success_count += 1
                        else:
                            failed_count += 1

                        completed += 1
                        rem = max(0, total - completed)
                        row_item = {
                            "Profile_Number": pdata_res.get("number", f"#{idx:02d}") if isinstance(pdata_res, dict) else f"#{idx:02d}",
                            "UID": pdata_res.get("uid", "") if isinstance(pdata_res, dict) else str(acc.get("uid", "")),
                            "Password": pdata_res.get("password", "") if isinstance(pdata_res, dict) else str(acc.get("password", "")),
                            "2FA_Secret": pdata_res.get("two_factor", "") if isinstance(pdata_res, dict) else str(acc.get("two_factor", "")),
                            "Cookie": pdata_res.get("cookie", "") if isinstance(pdata_res, dict) else str(acc.get("cookie", "")),
                            "Status": "Success" if ok else "Failed",
                            "Message": msg
                        }
                        self.report_rows.append(row_item)
                        if live_reporter:
                            live_reporter.append_row(row_item)
                        self.progress_updated.emit(completed, total)
                        self.stats_updated.emit(success_count, failed_count, rem)

                with ThreadPoolExecutor(max_workers=self.max_concurrent_browsers) as executor:
                    futures_list = []
                    for idx, acc in enumerate(self.accounts_to_run, start=1):
                        if self.stop_requested:
                            break
                        fut = executor.submit(self._run_single_account_worker, acc, idx, total)
                        fut.add_done_callback(lambda f, i=idx, a=acc, t=time.time(): _handle_account_done(f, i, a, t))
                        futures_list.append(fut)
                        if idx < total and self.stagger_delay_sec > 0:
                            time.sleep(self.stagger_delay_sec)

                    for f in futures_list:
                        try:
                            f.result()
                        except Exception:
                            pass

        except Exception as p_err:
            self.emit_log(f"❌ Engine exception: {p_err}")

        # Retrieve report path from live reporter or fallback
        report_path = ""
        if live_reporter and live_reporter.get_report_path():
            report_path = live_reporter.get_report_path()
        else:
            try:
                from fb_bulk_login_helpers import save_automation_report_csv
                report_path = save_automation_report_csv(self.report_rows, self.bot_title)
            except Exception:
                pass

        if report_path:
            self.emit_log(f"📊 [Report Saved]: {Path(report_path).name}")

        result_payload = {
            "completed": completed,
            "success": success_count,
            "failed": failed_count,
            "total": total,
            "report_path": report_path
        }

        if self.stop_requested:
            self.emit_log("🛑 Automation stopped.")
            self.finished_signal.emit(False, "Stopped by user", result_payload)
        else:
            self.emit_log(f"🎉 All {total} account logins completed! (Success: {success_count}/{total}, Failed: {failed_count})")
            self.finished_signal.emit(True, "Completed", result_payload)

