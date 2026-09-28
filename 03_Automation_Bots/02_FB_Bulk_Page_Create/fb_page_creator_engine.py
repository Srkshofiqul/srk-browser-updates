import os
import sys
import time
import random
import re
import json
import subprocess
import urllib.request
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import psutil
from PySide6.QtCore import QThread, Signal
from playwright.sync_api import sync_playwright

# Ensure main software paths are in sys.path
def ensure_core_paths():
    current_dir = Path(__file__).resolve().parent
    app_root = current_dir.parent.parent
    for p in [app_root, app_root / "01_Main_Software", app_root / "01_Main_Software" / "core"]:
        if p.exists() and str(p) not in sys.path:
            sys.path.insert(0, str(p))

ensure_core_paths()

# Import security and helpers from bot package
from fb_page_creator_security import get_app_root_dir, check_srbrowser_heartbeat, get_effective_bot_license
from fb_page_creator_helpers import (
    check_facebook_login_status,
    extract_facebook_tokens,
    create_facebook_page_graphql,
    export_created_pages_report,
    auto_relogin_facebook,
    dismiss_facebook_popup_notices,
    apply_bot_window_icon_win32,
    switch_facebook_to_page_profile,
    capture_diagnostic_screenshot
)
from fb_page_creator_proxy_bridge import LocalProxyBridge, parse_proxy_string

# Load canonical 1-Click Page Creator script from 06_Script_Store
SCRIPT_STORE_INJECT = Path(__file__).resolve().parent.parent.parent / "06_Script_Store" / "01_FB_Quick_Page_Create" / "quick_page_creator_inject.js"
LOCAL_INJECT = Path(__file__).resolve().parent / "page_creator_inject.js"

INJECT_SCRIPT_PATH = SCRIPT_STORE_INJECT if SCRIPT_STORE_INJECT.exists() else LOCAL_INJECT
INJECT_SCRIPT_CODE = ""
if INJECT_SCRIPT_PATH.exists():
    try:
        with open(INJECT_SCRIPT_PATH, "r", encoding="utf-8") as f:
            INJECT_SCRIPT_CODE = f.read()
    except Exception:
        INJECT_SCRIPT_CODE = ""

# Load Automated Core script (Method 2)
BOOKMARKLET_V5_PATH = Path(__file__).resolve().parent / "page_creator_bookmarklet_v5.js"
BOOKMARKLET_V5_CODE = ""
if BOOKMARKLET_V5_PATH.exists():
    try:
        with open(BOOKMARKLET_V5_PATH, "r", encoding="utf-8") as f:
            BOOKMARKLET_V5_CODE = f.read()
    except Exception:
        BOOKMARKLET_V5_CODE = ""


BRAND_PREFIXES = [
    "Tech", "Digital", "Smart", "Creative", "Prime", "Apex", "Global",
    "Elite", "NextGen", "Nova", "Vibe", "Alpha", "Hyper", "Zenith", "Ultra",
    "Future", "Epic", "Pro", "Pulse", "Cyber", "Matrix", "Fusion", "Nexus"
]

BRAND_SUFFIXES = [
    "Hub", "Studio", "Media", "Lab", "Network", "World", "Zone", "Station",
    "Point", "Spot", "Club", "Collective", "Space", "Forge", "Sphere", "HQ",
    "Solutions", "Arena", "Dynamics", "Vision", "Nexus", "Official"
]


def generate_random_page_name(profile_data: Optional[Dict[str, Any]] = None) -> str:
    """Generates a stylish, natural-sounding Facebook Page name that avoids spam filters."""
    if profile_data:
        prof_name = str(profile_data.get("name", "")).strip()
        num_str = str(profile_data.get("number", "")).strip()
        if prof_name.startswith("FB_") and len(prof_name) > 6:
            uid_tail = prof_name[-4:]
            return f"{random.choice(BRAND_PREFIXES)} {random.choice(BRAND_SUFFIXES)} {uid_tail}"
        elif num_str:
            clean_num = re.sub(r"\D", "", num_str)
            if clean_num:
                return f"{random.choice(BRAND_PREFIXES)} {random.choice(BRAND_SUFFIXES)} {clean_num}"
        elif prof_name and not prof_name.lower().startswith("profile"):
            return f"{prof_name} {random.choice(BRAND_SUFFIXES)}"

    return f"{random.choice(BRAND_PREFIXES)} {random.choice(BRAND_SUFFIXES)} {random.randint(10, 999)}"


def resolve_user_data_dir(profile_data: Dict[str, Any], profile_mgr: Optional[Any] = None) -> str:
    """Smart resolution of the exact profile folder for srkBrowser."""
    if profile_data.get("user_data_dir") and Path(profile_data["user_data_dir"]).exists():
        return str(Path(profile_data["user_data_dir"]).resolve())

    pid = profile_data.get("id")
    
    # 1. Try passed profile_mgr
    if profile_mgr and pid and hasattr(profile_mgr, "get_profile_folder"):
        try:
            p_f = profile_mgr.get_profile_folder(pid)
            if p_f and p_f.exists():
                return str(p_f.resolve())
        except Exception:
            pass

    # 2. Try ProfileManager from core
    if pid:
        try:
            from core.profile_manager import ProfileManager
            pm = ProfileManager()
            p_f = pm.get_profile_folder(pid)
            if p_f and p_f.exists():
                return str(p_f.resolve())
        except Exception:
            pass
        try:
            from profile_manager import ProfileManager
            pm = ProfileManager()
            p_f = pm.get_profile_folder(pid)
            if p_f and p_f.exists():
                return str(p_f.resolve())
        except Exception:
            pass

    # 3. Check users directories in 01_Main_Software/core/profiles/users/*
    app_root = get_app_root_dir()
    pnum = str(profile_data.get("number", profile_data.get("name", ""))).strip()

    core_users_dir = app_root / "01_Main_Software" / "core" / "profiles" / "users"
    if core_users_dir.exists() and pnum:
        for u_folder in core_users_dir.iterdir():
            if u_folder.is_dir():
                cand = u_folder / pnum
                if cand.exists() and cand.is_dir():
                    return str(cand.resolve())

    # 4. Fallback search
    profiles_base = app_root / "01_Main_Software" / "core" / "profiles"
    if not profiles_base.exists():
        profiles_base = app_root / "profiles"

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


def get_chrome_executable_path() -> Optional[str]:
    """
    Finds bundled Portable Chromium (matching srkBrowser core) executable.
    STRICT RULE: Prioritizes bundled Portable Chromium so DPAPI cookie encryption matches.
    """
    try:
        from utils import get_system_browsers
        browsers = get_system_browsers()
        if browsers:
            for label, exe_path in browsers.items():
                if os.path.exists(exe_path):
                    return exe_path
    except Exception:
        pass

    app_root = get_app_root_dir()
    portable_paths = [
        app_root / "chromium" / "chrome.exe",
        app_root / "01_Main_Software" / "chromium" / "chrome.exe",
        app_root / "_internal" / "chromium" / "chrome.exe",
        app_root / "01_Main_Software" / "chromium" / "chrome-win" / "chrome.exe",
        app_root / "dist" / "srkBrowser" / "chromium" / "chrome.exe",
        app_root / "bin" / "chromium" / "chrome.exe",
        app_root / "assets" / "chromium" / "chrome.exe"
    ]
    for p in portable_paths:
        if p.exists():
            return str(p.resolve())

    standard_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe")
    ]
    for p_str in standard_paths:
        if os.path.exists(p_str):
            return p_str

    return None


def calculate_cdp_port(profile_data: Dict[str, Any], idx: int = 1) -> int:
    """Matches srkBrowser core BrowserLauncher remote debugging port calculation."""
    try:
        raw_num = str(profile_data.get("number", idx)).replace("Profile", "").replace("#", "").strip()
        clean_digits = re.sub(r"\D", "", raw_num)
        n_val = int(clean_digits) if clean_digits else idx
        return 9200 + (n_val % 500)
    except Exception:
        return 9200 + (idx % 500)


def parse_cookie_string(cookie_str: str, default_domain: str = ".facebook.com") -> list:
    """Parses standard cookie string header into Playwright list of cookie dicts."""
    cookies = []
    if not cookie_str:
        return cookies
    for item in cookie_str.split(";"):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            k, v = k.strip(), v.strip()
            if k:
                cookies.append({"name": k, "value": v, "domain": default_domain, "path": "/"})
    return cookies


def ensure_facebook_subdomain_cookies(context: Any) -> None:
    """Ensures active Facebook session cookies are propagated to .facebook.com domain."""
    try:
        cookies = context.cookies()
        new_cookies = []
        for c in cookies:
            dom = c.get("domain", "")
            if "facebook.com" in dom and dom != ".facebook.com":
                ck_copy = dict(c)
                ck_copy["domain"] = ".facebook.com"
                new_cookies.append(ck_copy)
        if new_cookies:
            context.add_cookies(new_cookies)
    except Exception:
        pass


def kill_profile_chrome_process(user_data_dir: str, cdp_port: int = 0) -> None:
    """Forcefully terminates any Chrome / Chromium process for a given profile folder or CDP port."""
    if not user_data_dir and not cdp_port:
        return

    # Method 1: CDP close endpoint
    if cdp_port:
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{cdp_port}/json/close", data=b"")
            urllib.request.urlopen(req, timeout=0.3)
        except Exception:
            pass

    folder_name = Path(user_data_dir).name if user_data_dir else ""
    user_data_dir_str = str(Path(user_data_dir).resolve()).lower() if user_data_dir else ""
    if not folder_name and not user_data_dir_str:
        return

    # Method 2: Instant psutil termination (fast Win32 TerminateProcess API)
    try:
        import psutil
        for p in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                pname = (p.info.get('name') or '').lower()
                if 'chrome' in pname or 'browser' in pname:
                    cmd_list = p.info.get('cmdline') or []
                    cmd = " ".join(cmd_list).lower()
                    if (folder_name and folder_name.lower() in cmd) or (user_data_dir_str and user_data_dir_str in cmd):
                        p.kill()
            except Exception:
                pass
    except Exception:
        pass


def safely_close_profile_browser(
    context: Any = None,
    browser_cdp: Any = None,
    user_dir: str = "",
    cdp_port: int = 0,
    profile_id: Optional[str] = None,
    launcher: Optional[Any] = None,
    page: Any = None
) -> None:
    """
    Safely and thoroughly closes the browser session and terminates the Chromium process.
    Guarantees no orphan browser window remains open.
    """
    # 1. Graceful CDP Browser.close if connected
    if context and page:
        try:
            cdp_session = context.new_cdp_session(page)
            cdp_session.send("Browser.close")
            time.sleep(0.3)
        except Exception:
            pass

    # 2. Close Playwright context and CDP browser client
    if context:
        try:
            context.close()
        except Exception:
            pass
    if browser_cdp:
        try:
            browser_cdp.close()
        except Exception:
            pass

    # 3. Main software launcher close
    if launcher and profile_id and hasattr(launcher, "close_profile"):
        try:
            launcher.close_profile(profile_id)
        except Exception:
            pass

    # 4. Terminate process matching user_dir or cdp_port
    kill_profile_chrome_process(user_dir, cdp_port)

    # 5. Clean lock files
    if user_dir:
        for lock_name in ["SingletonLock", "lockfile"]:
            try:
                lf = Path(user_dir) / lock_name
                if lf.exists():
                    lf.unlink(missing_ok=True)
            except Exception:
                pass


# Global active process registry for instant nuclear shutdown
_ACTIVE_SESSIONS: List[Tuple[Any, Dict[str, Any]]] = []

def register_active_browser_session(context: Any, profile_data: Dict[str, Any]) -> None:
    global _ACTIVE_SESSIONS
    _ACTIVE_SESSIONS.append((context, profile_data))

def unregister_active_browser_session(context: Any) -> None:
    global _ACTIVE_SESSIONS
    _ACTIVE_SESSIONS = [(c, p) for c, p in _ACTIVE_SESSIONS if c != context]

def get_active_browser_sessions_count() -> int:
    global _ACTIVE_SESSIONS
    return len(_ACTIVE_SESSIONS)

def kill_all_bot_browsers(profiles: Optional[List[Dict[str, Any]]] = None) -> None:
    """Instant synchronous termination helper for all open bot browsers."""
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
        folder_targets = set()
        for p in profiles:
            try:
                u_dir = resolve_user_data_dir(p)
                if u_dir:
                    fn = Path(u_dir).name
                    if fn:
                        folder_targets.add(fn.lower())
            except Exception:
                pass

        if folder_targets:
            try:
                import psutil
                for p in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        pname = (p.info.get('name') or '').lower()
                        if 'chrome' in pname or 'browser' in pname:
                            cmd = " ".join(p.info.get('cmdline') or []).lower()
                            if any(tgt in cmd for tgt in folder_targets):
                                p.kill()
                    except Exception:
                        pass
            except Exception:
                pass


class PageCreatorWorkerThread(QThread):
    """
    Multi-threaded automation engine for creating Facebook Pages in bulk.
    Executes in 100% invisible stealth backend mode with no UI popups shown on browser.
    """

    log_emitted = Signal(str)
    progress_updated = Signal(int, int) # current, total
    stats_updated = Signal(int, int, int) # success, failed, remaining
    finished_signal = Signal(bool, str, str) # success, summary_text, report_path

    def __init__(
        self,
        profiles_list: List[Dict[str, Any]],
        page_names_list: Optional[List[str]] = None,
        creation_mode: str = "random",
        creation_method: str = "method1",
        category_id: str = "2347428775505624",
        category_name: str = "Digital Creator",
        bio_text: str = "",
        pages_per_account: int = 1,
        threads_count: int = 1,
        delay_sec: float = 2.0,
        headless: bool = False,
        auto_switch_page: bool = True,
        failed_group: Optional[str] = None,
        profile_mgr: Optional[Any] = None,
        browser_launcher: Optional[Any] = None,
        proxy_enabled: bool = False,
        proxy_string: str = "",
        proxy_mode: str = "dynamic",
        parent: Optional[Any] = None
    ) -> None:
        super().__init__(parent)
        self.profiles_list = profiles_list or []
        self.page_names_list = page_names_list or []
        self.creation_mode = creation_mode
        self.creation_method = (creation_method or "method1").lower()
        self.category_id = category_id
        self.category_name = category_name or "Digital Creator"
        self.bio_text = bio_text
        self.pages_per_account = max(1, pages_per_account)
        self.threads_count = max(1, min(20, threads_count))
        self.delay_sec = max(0.0, delay_sec)
        self.headless = headless
        self.auto_switch_page = auto_switch_page
        self.failed_group = failed_group if failed_group and str(failed_group).strip() not in ("NONE", "None", "") else None
        self.profile_mgr = profile_mgr
        self.browser_launcher = browser_launcher
        self.proxy_enabled = proxy_enabled
        self.proxy_string = (proxy_string or "").strip()
        self.proxy_list: List[str] = [
            l.strip() for l in self.proxy_string.splitlines()
            if l.strip() and not l.strip().startswith("#")
        ]
        self.proxy_mode = (proxy_mode or "dynamic").lower()
        self.proxy_bridge: Optional[LocalProxyBridge] = None

        self._is_stopped = False
        self.active_executor: Optional[ThreadPoolExecutor] = None
        self.success_count = 0
        self.failed_count = 0
        self.remaining_count = len(self.profiles_list)
        self.created_pages_results: List[Dict[str, Any]] = []
        self.all_profile_results: List[Dict[str, Any]] = []

    def _move_profile_to_failed_group(self, profile_data: Dict[str, Any]) -> None:
        """Safely re-assigns a failed profile to the user-selected failed group."""
        if not self.failed_group or self.failed_group in ("NONE", "None", ""):
            return

        prof_name = profile_data.get("name") or profile_data.get("number") or "Profile"
        prof_id = profile_data.get("id")
        profile_data["group"] = self.failed_group
        moved = False

        # 1. Update in active ProfileManager if available
        if self.profile_mgr and prof_id and hasattr(self.profile_mgr, "update_profile"):
            try:
                self.profile_mgr.update_profile(prof_id, {"group": self.failed_group})
                moved = True
            except Exception as e:
                self.log_emitted.emit(f"⚠️ [GROUP UPDATE NOTICE] {prof_name}: {str(e)}")

        # 2. Update profile.json directly on disk as fallback/guarantee
        try:
            user_dir = resolve_user_data_dir(profile_data, self.profile_mgr)
            p_json = Path(user_dir) / "profile.json"
            if p_json.exists():
                from utils import safe_read_json, safe_write_json
                p_dict = safe_read_json(p_json)
                if isinstance(p_dict, dict):
                    p_dict["group"] = self.failed_group
                    safe_write_json(p_json, p_dict)
                    moved = True
        except Exception:
            pass

        # 3. Directly ensure active master profiles.json has the updated group
        try:
            db_path = getattr(self.profile_mgr, "db_file", None)
            if not db_path or not Path(db_path).exists():
                from core.profile_manager import ProfileManager
                db_path = ProfileManager().db_file
            if db_path and Path(db_path).exists():
                from utils import safe_read_json, safe_write_json
                master_profs = safe_read_json(db_path)
                if isinstance(master_profs, list):
                    updated = False
                    for mp in master_profs:
                        if mp.get("id") == prof_id:
                            mp["group"] = self.failed_group
                            updated = True
                            break
                    if updated:
                        safe_write_json(db_path, master_profs)
                        moved = True
        except Exception:
            pass

        # 4. Fallback to singleton / global ProfileManager if instance was not passed
        if not moved and prof_id:
            try:
                from core.profile_manager import ProfileManager
                pm = ProfileManager()
                pm.update_profile(prof_id, {"group": self.failed_group})
                moved = True
            except Exception:
                pass

        if moved:
            self.log_emitted.emit(f"📦 [MOVED TO GROUP] Profile '{prof_name}' moved to group: '{self.failed_group}'")

    def stop(self) -> None:
        self._is_stopped = True
        self.log_emitted.emit("🛑 [STOPPING] Cancellation requested by user. Terminating all active browsers...")
        if self.proxy_bridge:
            try:
                self.proxy_bridge.stop()
            except Exception:
                pass
            self.proxy_bridge = None
        if hasattr(self, "active_executor") and self.active_executor:
            try:
                self.active_executor.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass
        kill_all_bot_browsers(self.profiles_list)

    def run(self) -> None:
        total = len(self.profiles_list)
        if total == 0:
            self.finished_signal.emit(False, "No profiles to process.", "")
            return

        fail_grp_info = f" | Fail Group: '{self.failed_group}'" if self.failed_group else " | Fail Move: Disabled"
        proxy_info = ""
        if self.proxy_enabled and self.proxy_list:
            proxy_info = f" | Proxy: {self.proxy_mode.upper()} ({len(self.proxy_list)} IP{'s' if len(self.proxy_list) > 1 else ''})"
        self.log_emitted.emit(f"🚀 [INITIALIZED] Starting FB Page Creator with {total} profiles across {self.threads_count} thread(s){fail_grp_info}{proxy_info}...")

        # Initialize Local Proxy Gateway if proxy enabled
        if self.proxy_enabled and self.proxy_list:
            try:
                init_m = "UPSTREAM" if self.proxy_mode == "full" else "DIRECT"
                self.proxy_bridge = LocalProxyBridge(upstream_proxy=self.proxy_list[0], initial_mode=init_m)
                b_port = self.proxy_bridge.start()
                self.log_emitted.emit(f"🛡️ [PROXY INITIALIZED] Local Gateway active on port {b_port} (Mode: {self.proxy_mode.upper()}, {len(self.proxy_list)} IP{'s' if len(self.proxy_list) > 1 else ''} loaded)")
            except Exception as pe:
                self.log_emitted.emit(f"⚠️ [PROXY WARNING] Failed to start local gateway: {pe}. Running direct.")
                self.proxy_bridge = None

        # Prepare session Excel report path for real-time live updates
        rep_folder = Path(__file__).resolve().parent / "reports"
        rep_folder.mkdir(parents=True, exist_ok=True)
        session_report_name = f"FB_Pages_Report_{time.strftime('%Y%m%d_%H%M%S')}.xlsx"
        self.session_report_path = str(rep_folder / session_report_name)

        processed = 0

        # Execute worker pool without blocking on shutdown
        executor = ThreadPoolExecutor(max_workers=self.threads_count)
        self.active_executor = executor
        future_to_prof = {}

        try:
            for idx, prof in enumerate(self.profiles_list):
                if self._is_stopped:
                    break
                fut = executor.submit(self._process_single_profile, prof, idx + 1)
                future_to_prof[fut] = prof

            for future in as_completed(future_to_prof):
                if self._is_stopped:
                    break

                prof = future_to_prof[future]
                processed += 1
                try:
                    res_success, res_msg, pages_data = future.result()
                    if res_success:
                        self.success_count += 1
                        for p in pages_data:
                            self.created_pages_results.append(p)
                            self.all_profile_results.append(p)
                    else:
                        self.failed_count += 1
                        for p in pages_data:
                            self.all_profile_results.append(p)
                except Exception as e:
                    self.failed_count += 1
                    self.log_emitted.emit(f"❌ [CRITICAL ERROR] Profile {prof.get('name')}: {str(e)}")
                    self._move_profile_to_failed_group(prof)
                    prof_num_val = str(prof.get("number") or prof.get("name") or "Unknown").strip()
                    uid_val = str(prof.get("fb_uid") or prof.get("uid") or "").strip()
                    pwd_val = str(prof.get("fb_pass") or prof.get("password") or "").strip()
                    s2fa_val = str(prof.get("secret_2fa") or prof.get("fb_2fa") or prof.get("two_factor") or prof.get("two_factor_secret") or prof.get("2fa") or "").strip()
                    ck_val = str(prof.get("cookie") or prof.get("cookies") or "").strip()
                    if not ck_val and isinstance(prof.get("cookies_json"), list):
                        try:
                            ck_val = "; ".join(f"{c.get('name')}={c.get('value')}" for c in prof["cookies_json"] if isinstance(c, dict) and c.get("name") and c.get("value"))
                        except Exception:
                            pass
                    self.all_profile_results.append({
                        "profile_number": prof_num_val,
                        "uid": uid_val,
                        "password": pwd_val,
                        "secret_2fa": s2fa_val,
                        "cookie": ck_val,
                        "status": "Fail",
                        "failure_reason": f"Critical Error: {str(e)}",
                        "page_name": "N/A",
                        "page_id": "",
                        "page_link": "",
                        "page_url": "",
                        "creator_uid": uid_val,
                        "category": getattr(self, "category_name", "Digital Creator"),
                        "screenshot_path": "",
                        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "group": prof.get("group", "Default")
                    })

                self.remaining_count = max(0, total - processed)
                self.progress_updated.emit(processed, total)
                self.stats_updated.emit(self.success_count, self.failed_count, self.remaining_count)

                # Real-Time Instant Live Excel Update on every single profile completion!
                if self.all_profile_results:
                    try:
                        export_created_pages_report(self.all_profile_results, self.session_report_path, format_type="xlsx")
                    except Exception:
                        pass

                if self.delay_sec > 0 and not self._is_stopped:
                    time.sleep(self.delay_sec)
        finally:
            if self._is_stopped:
                for f in future_to_prof:
                    if not f.done():
                        f.cancel()
                try:
                    executor.shutdown(wait=False, cancel_futures=True)
                except Exception:
                    pass
                kill_all_bot_browsers(self.profiles_list)
            else:
                try:
                    executor.shutdown(wait=True)
                except Exception:
                    pass
            self.active_executor = None

            if self.proxy_bridge:
                try:
                    self.proxy_bridge.stop()
                except Exception:
                    pass
                self.proxy_bridge = None

        # Refresh database if profiles were moved
        if self.failed_group and self.profile_mgr and hasattr(self.profile_mgr, "load_profiles"):
            try:
                self.profile_mgr.load_profiles()
            except Exception:
                pass

        # Finalize export report
        report_path = self.session_report_path if Path(self.session_report_path).exists() else ""
        if not report_path and self.all_profile_results:
            ok, final_path = export_created_pages_report(self.all_profile_results, self.session_report_path, format_type="xlsx")
            if ok:
                report_path = final_path
        if report_path:
            self.log_emitted.emit(f"📑 [EXPORT COMPLETED] Live Excel report saved: {report_path}")

        if self._is_stopped:
            summary = f"Stopped by user! Created: {len(self.created_pages_results)} pages | Success IDs: {self.success_count} | Failed: {self.failed_count}"
        else:
            summary = f"Completed! Created: {len(self.created_pages_results)} pages | Success IDs: {self.success_count} | Failed: {self.failed_count}"
        self.log_emitted.emit(f"🏁 [SUMMARY] {summary}")
        self.finished_signal.emit(not self._is_stopped, summary, report_path)

    def _generate_page_name(self, profile_data: Dict[str, Any], index: int) -> str:
        if self.creation_mode == "custom" and self.page_names_list:
            # Strictly use user-provided page names (cycling gracefully if more profiles than names)
            return self.page_names_list[(index - 1) % len(self.page_names_list)].strip()

        # Random Mode or fallback
        return generate_random_page_name(profile_data)

    def _resolve_category(self) -> Tuple[str, str]:
        if self.category_id and str(self.category_id).strip():
            return self.category_id, self.category_name

        categories_pool = [
            ("Digital Creator", "2347428775505624"),
            ("Personal Blog", "2700"),
            ("Health/beauty", "2214"),
            ("Beauty, Cosmetic & Care", "139225689474222"),
            ("News & Media Website", "2709"),
            ("Shopping & Retail", "200600219953504"),
            ("Gaming Video Creator", "1350536325044173"),
            ("Clothing (Brand)", "2209"),
            ("Education", "2250"),
            ("Entertainment Website", "2705"),
            ("Entrepreneur", "1617"),
            ("Musician/band", "180164648685982"),
            ("Product/service", "2201"),
            ("Public Figure", "1602"),
            ("Community", "2612"),
            ("Photographer", "181475575221097")
        ]
        return random.choice(categories_pool)

    def _process_single_profile(self, profile_data: Dict[str, Any], index: int) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """Processes a single profile: opens browser, verifies login, creates page invisibly."""
        if self._is_stopped:
            return False, "Automation stopped by user", []

        prof_name = profile_data.get("name") or profile_data.get("number") or f"Profile #{index}"
        prof_num_val = str(profile_data.get("number") or profile_data.get("name") or f"Profile #{index}").strip()
        prof_uid = str(profile_data.get("fb_uid") or profile_data.get("uid") or "").strip()
        prof_pass = str(profile_data.get("fb_pass") or profile_data.get("password") or "").strip()
        prof_2fa = str(profile_data.get("secret_2fa") or profile_data.get("fb_2fa") or profile_data.get("two_factor") or profile_data.get("two_factor_secret") or profile_data.get("2fa") or "").strip()
        prof_cookie = str(profile_data.get("cookie") or profile_data.get("cookies") or "").strip()
        if not prof_cookie and isinstance(profile_data.get("cookies_json"), list):
            try:
                prof_cookie = "; ".join(f"{c.get('name')}={c.get('value')}" for c in profile_data["cookies_json"] if isinstance(c, dict) and c.get("name") and c.get("value"))
            except Exception:
                pass

        self.log_emitted.emit(f"⏳ [CHECKING] Profile: {prof_name}...")

        user_dir = resolve_user_data_dir(profile_data, self.profile_mgr)
        chrome_exe = get_chrome_executable_path()
        cdp_port = calculate_cdp_port(profile_data, index)
        cdp_url = f"http://127.0.0.1:{cdp_port}"

        pages_created = []
        context = None
        browser_cdp = None
        page = None
        connected_via_cdp = False
        launched_via_launcher = False
        launcher = self.browser_launcher
        captured_fb_error = ""

        p_bridge: Optional[LocalProxyBridge] = None
        proxy_idx_num = 1
        rot_tag = ""
        if self.proxy_enabled and self.proxy_list:
            proxy_idx_num = ((index - 1) % len(self.proxy_list)) + 1
            chosen_proxy = self.proxy_list[(index - 1) % len(self.proxy_list)]
            try:
                init_m = "UPSTREAM" if self.proxy_mode == "full" else "DIRECT"
                p_bridge = LocalProxyBridge(upstream_proxy=chosen_proxy, initial_mode=init_m)
                p_bridge.start()
                rot_tag = f" [Proxy #{proxy_idx_num}/{len(self.proxy_list)}]" if len(self.proxy_list) > 1 else ""
                self.log_emitted.emit(f"🛡️ [PROXY INITIALIZED] Profile '{prof_name}'{rot_tag}: Gateway port {p_bridge.port}")
            except Exception as pe:
                self.log_emitted.emit(f"⚠️ [PROXY NOTICE] Profile '{prof_name}': {pe}")
                p_bridge = None

        try:
            with sync_playwright() as p:
                if self._is_stopped:
                    return False, "Automation stopped by user", []

                # 1. Smart CDP Connection: Connect seamlessly if browser is ALREADY OPEN in srkBrowser GUI
                try:
                    browser_cdp = p.chromium.connect_over_cdp(cdp_url)
                    if browser_cdp and browser_cdp.contexts:
                        context = browser_cdp.contexts[0]
                        connected_via_cdp = True
                        self.log_emitted.emit(f"🔗 [SMART CDP] Connected to ALREADY OPEN browser for '{prof_name}' (Port {cdp_port})!")
                except Exception:
                    connected_via_cdp = False
                    browser_cdp = None

                # 2. Main Software Launch: If not already open, launch through srkBrowser's official BrowserLauncher
                if not context:
                    if self._is_stopped:
                        return False, "Automation stopped by user", []

                    if not launcher:
                        try:
                            from core.browser import BrowserLauncher
                            launcher = BrowserLauncher()
                        except ImportError:
                            try:
                                from browser import BrowserLauncher
                                launcher = BrowserLauncher()
                            except ImportError:
                                launcher = None

                    if launcher and chrome_exe and not self.headless:
                        try:
                            prof_data_for_launch = dict(profile_data)
                            if p_bridge and p_bridge.is_running and p_bridge.port > 0:
                                prof_data_for_launch["proxy_type"] = "HTTP"
                                prof_data_for_launch["proxy_host"] = "127.0.0.1"
                                prof_data_for_launch["proxy_port"] = str(p_bridge.port)
                            ok_l, msg_l = launcher.launch_profile(chrome_exe, Path(user_dir), prof_data_for_launch)
                            if ok_l:
                                self.log_emitted.emit(f"🚀 [MAIN SOFTWARE LAUNCHER] Opened profile '{prof_name}' via srkBrowser engine.")
                                for _ in range(25):
                                    if self._is_stopped:
                                        safely_close_profile_browser(context, browser_cdp, user_dir, cdp_port, profile_data.get("id"), launcher, page)
                                        return False, "Automation stopped by user", []
                                    time.sleep(0.3)
                                    try:
                                        browser_cdp = p.chromium.connect_over_cdp(cdp_url)
                                        if browser_cdp and browser_cdp.contexts:
                                            context = browser_cdp.contexts[0]
                                            connected_via_cdp = True
                                            launched_via_launcher = True
                                            break
                                    except Exception:
                                        pass
                        except Exception as l_err:
                            self.log_emitted.emit(f"⚠️ BrowserLauncher notice: {l_err}")

                    # Fallback to direct Playwright launch if headless or if launcher was not available
                    if not context:
                        if self._is_stopped:
                            return False, "Automation stopped by user", []

                        # Clean up stale SingletonLock to prevent profile collision
                        lock_file = Path(user_dir) / "SingletonLock"
                        if lock_file.exists():
                            try:
                                lock_file.unlink(missing_ok=True)
                            except Exception:
                                pass

                        launch_args = [
                            "--disable-blink-features=AutomationControlled",
                            "--disable-infobars",
                            "--test-type",
                            "--disable-notifications",
                            "--no-default-browser-check",
                            "--disable-dev-shm-usage",
                            f"--remote-debugging-port={cdp_port}",
                            "--remote-allow-origins=*"
                        ]
                        if p_bridge and p_bridge.is_running and p_bridge.port > 0:
                            launch_args.append(f"--proxy-server=http://127.0.0.1:{p_bridge.port}")
                        context = p.chromium.launch_persistent_context(
                            user_data_dir=user_dir,
                            executable_path=chrome_exe,
                            headless=self.headless,
                            args=launch_args,
                            viewport={"width": 1280, "height": 800}
                        )

                    if not context:
                        fail_rec = [{
                            "profile_number": prof_num_val,
                            "uid": prof_uid,
                            "password": prof_pass,
                            "secret_2fa": prof_2fa,
                            "cookie": prof_cookie,
                            "status": "Fail",
                            "failure_reason": "Failed to launch or attach browser process",
                            "page_name": "N/A",
                            "page_id": "",
                            "page_link": "",
                            "page_url": "",
                            "creator_uid": prof_uid,
                            "category": getattr(self, "category_name", "Digital Creator"),
                            "screenshot_path": "",
                            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "group": profile_data.get("group", "Default")
                        }]
                        return False, "Failed to launch or attach browser", fail_rec

                    if self._is_stopped:
                        safely_close_profile_browser(context, browser_cdp, user_dir, cdp_port, profile_data.get("id"), launcher, page)
                        return False, "Automation stopped by user", []

                    register_active_browser_session(context, profile_data)

                    # Pre-inject session cookies from profile data into Playwright context
                    cookies_to_add = []
                    if profile_data.get("cookies_json"):
                        for ck in profile_data["cookies_json"]:
                            if isinstance(ck, dict) and ck.get("name") and ck.get("value"):
                                dom = ck.get("domain", ".facebook.com")
                                cookies_to_add.append({
                                    "name": ck["name"],
                                    "value": ck["value"],
                                    "domain": dom if dom.startswith(".") or "facebook" in dom else f".{dom}",
                                    "path": ck.get("path", "/"),
                                    "secure": bool(ck.get("secure", True)),
                                    "httpOnly": bool(ck.get("httpOnly", False))
                                })
                    elif profile_data.get("cookie"):
                        cookies_to_add = parse_cookie_string(profile_data["cookie"], default_domain=".facebook.com")
                    elif profile_data.get("notes"):
                        for line in str(profile_data["notes"]).split("\n"):
                            if line.strip().startswith("Cookie:"):
                                raw_c = line.strip().replace("Cookie:", "").strip()
                                cookies_to_add = parse_cookie_string(raw_c, default_domain=".facebook.com")
                                break

                    if cookies_to_add:
                        try:
                            context.add_cookies(cookies_to_add)
                        except Exception:
                            pass

                    ensure_facebook_subdomain_cookies(context)

                # Set custom numbered profile icon on Windows taskbar and window
                try:
                    num_str = str(profile_data.get("number") or profile_data.get("name") or "").replace("Profile", "").replace("#", "").strip()
                    ico_path = Path(user_dir) / "profile_icon.ico"
                    if ico_path.exists():
                        apply_bot_window_icon_win32(ico_path, num_str)
                except Exception:
                    pass

                # Locate or open Facebook page
                if connected_via_cdp and context.pages:
                    for pg in context.pages:
                        if "facebook.com" in (pg.url or ""):
                            page = pg
                            break

                if not page:
                    page = context.pages[0] if context.pages else context.new_page()
                    self.log_emitted.emit(f"🌐 [NAVIGATION] Loading Facebook on profile '{prof_name}'...")
                    page.goto("https://web.facebook.com/", timeout=45000, wait_until="domcontentloaded")
                    time.sleep(2.0)
                else:
                    try:
                        page.bring_to_front()
                    except Exception:
                        pass
                    if "facebook.com" not in (page.url or "").lower() or "pages/creation" in (page.url or "").lower():
                        try:
                            self.log_emitted.emit(f"🌐 [NAVIGATION] Navigating to Facebook on profile '{prof_name}'...")
                            page.goto("https://web.facebook.com/", timeout=45000, wait_until="domcontentloaded")
                            time.sleep(2.0)
                        except Exception:
                            pass
                    time.sleep(1.0)

                # Auto dismiss Remember password, Cookie and notification popups
                dismiss_facebook_popup_notices(page)

                is_logged_in, login_status = check_facebook_login_status(page, timeout_sec=5.0)
                relogin_msg = ""
                if not is_logged_in:
                    if login_status == "CHECKPOINT":
                        self.log_emitted.emit(f"🔴 [CHECKPOINT / SUSPENDED] Profile '{prof_name}' is locked in Facebook Security Checkpoint ('Confirm you're human').")
                        ss_path = ""
                        try:
                            ss_path = capture_diagnostic_screenshot(
                                page=page,
                                profile_name=prof_name,
                                label="checkpoint",
                                uid=str(profile_data.get("fb_uid") or profile_data.get("uid") or ""),
                                extra_info="Facebook Security Checkpoint"
                            )
                            if ss_path:
                                self.log_emitted.emit(f"📸 [DIAGNOSTIC SCREENSHOT] Saved: {Path(ss_path).name}")
                        except Exception:
                            pass
                        self.log_emitted.emit(f"🛑 [CLOSING BROWSER] Closing browser for checkpoint profile '{prof_name}'...")
                        safely_close_profile_browser(context, browser_cdp, user_dir, cdp_port, profile_data.get("id"), launcher, page)
                        self._move_profile_to_failed_group(profile_data)
                        fail_rec = [{
                            "profile_number": prof_num_val,
                            "uid": prof_uid,
                            "password": prof_pass,
                            "secret_2fa": prof_2fa,
                            "cookie": prof_cookie,
                            "status": "Fail",
                            "failure_reason": "Facebook Security Checkpoint ('Confirm you're human')",
                            "page_name": "N/A",
                            "page_id": "",
                            "page_link": "",
                            "page_url": "",
                            "creator_uid": prof_uid,
                            "category": getattr(self, "category_name", "Digital Creator"),
                            "screenshot_path": ss_path,
                            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "group": profile_data.get("group", "Default")
                        }]
                        return False, "Facebook Security Checkpoint", fail_rec
                    else:
                        # Attempt Auto Re-login with UID + Pass + 2FA + Cookies
                        self.log_emitted.emit(f"🔄 [AUTO RE-LOGIN] Attempting re-login for profile '{prof_name}'...")
                        relogin_ok, relogin_msg = auto_relogin_facebook(
                            page=page,
                            context=context,
                            profile_data=profile_data,
                            user_data_dir=user_dir,
                            log_func=self.log_emitted.emit
                        )
                        if relogin_ok:
                            self.log_emitted.emit(f"🟢 [RE-LOGIN SUCCESS] Profile '{prof_name}' logged in successfully! Proceeding directly to Page Creation...")
                            is_logged_in = True
                        else:
                            self.log_emitted.emit(f"⚠️ [RE-LOGIN FAILED] Profile '{prof_name}': {relogin_msg}")

                if not is_logged_in:
                    ss_path = ""
                    try:
                        ss_path = capture_diagnostic_screenshot(
                            page=page,
                            profile_name=prof_name,
                            label="relogin_failed",
                            uid=str(profile_data.get("fb_uid") or profile_data.get("uid") or ""),
                            extra_info=relogin_msg or "Not logged into Facebook"
                        )
                        if ss_path:
                            self.log_emitted.emit(f"📸 [DIAGNOSTIC SCREENSHOT] Saved: {Path(ss_path).name}")
                    except Exception:
                        pass
                    self.log_emitted.emit(f"⚠️ [CLOSING BROWSER] Profile '{prof_name}' is not logged into Facebook. Closing browser...")
                    safely_close_profile_browser(context, browser_cdp, user_dir, cdp_port, profile_data.get("id"), launcher, page)
                    self._move_profile_to_failed_group(profile_data)
                    fail_rec = [{
                        "profile_number": prof_num_val,
                        "uid": prof_uid,
                        "password": prof_pass,
                        "secret_2fa": prof_2fa,
                        "cookie": prof_cookie,
                        "status": "Fail",
                        "failure_reason": f"Login / Re-login failed: {relogin_msg or 'Not logged in'}",
                        "page_name": "N/A",
                        "page_id": "",
                        "page_link": "",
                        "page_url": "",
                        "creator_uid": prof_uid,
                        "category": getattr(self, "category_name", "Digital Creator"),
                        "screenshot_path": ss_path,
                        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "group": profile_data.get("group", "Default")
                    }]
                    return False, "Not logged into Facebook", fail_rec

                # Extract tokens
                tokens = extract_facebook_tokens(page)
                raw_uid = tokens.get("c_user") or profile_data.get("fb_uid") or profile_data.get("uid") or "Unknown"
                uid_clean = str(raw_uid).strip()
                if uid_clean.endswith(".0"):
                    uid_clean = uid_clean[:-2]
                if uid_clean.upper().startswith("FB_"):
                    uid_clean = uid_clean[3:]
                uid = uid_clean
                if not prof_uid or prof_uid == "Unknown":
                    prof_uid = uid

                # Capture fresh session cookies from browser if available
                if context:
                    try:
                        live_cks = context.cookies()
                        if live_cks:
                            fb_live = [f"{c['name']}={c['value']}" for c in live_cks if "facebook.com" in c.get("domain", "")]
                            if fb_live:
                                prof_cookie = "; ".join(fb_live)
                    except Exception:
                        pass

                self.log_emitted.emit(f"🔑 [AUTH READY] Profile '{prof_name}' (UID: {uid}) authenticated!")

                # Generate Page Name & Resolve Category
                target_name = self._generate_page_name(profile_data, index)
                eff_category_id, eff_category_name = self._resolve_category()
                self.log_emitted.emit(f"⚡ [CREATING PAGE] Profile '{prof_name}' -> '{target_name}' (Category: {eff_category_name} | Mode: {self.creation_mode.upper()})...")

                created_ok = False
                created_page_id = ""
                created_page_link = ""
                captured_network_page_ids: List[str] = []

                # Install Playwright Network Response Listener to capture real Page ID
                def _handle_network_response(resp):
                    nonlocal captured_fb_error
                    try:
                        r_url = resp.url or ""
                        if any(k in r_url for k in ("graphql", "api", "page", "creation", "profile")):
                            txt = resp.text()
                            if txt:
                                clean_txt = txt.replace("for (;;);", "").strip()
                                # 1. Try parsing JSON directly
                                try:
                                    j_data = json.loads(clean_txt)
                                    if "errors" in j_data and isinstance(j_data["errors"], list) and j_data["errors"]:
                                        err_m = j_data["errors"][0].get("message") or ""
                                        if err_m and not captured_fb_error:
                                            captured_fb_error = err_m
                                    app_c = j_data.get("data", {}).get("additional_profile_plus_create", {})
                                    pid = (
                                        app_c.get("additional_profile", {}).get("id") or
                                        app_c.get("profile_plus", {}).get("id") or
                                        app_c.get("created_page", {}).get("id") or
                                        app_c.get("additional_profile_id")
                                    )
                                    if pid and str(pid).isdigit() and str(pid) != str(uid) and str(pid) != "2829896277312679":
                                        if str(pid) not in captured_network_page_ids:
                                            captured_network_page_ids.append(str(pid))
                                except Exception:
                                    pass

                                # 2. Targeted regex specifically for additional_profile / profile_plus (ignoring doc_id / actor_id)
                                f_ids = re.findall(r'"(?:additional_profile|profile_plus|created_page)"\s*:\s*\{[^}]*?"id"\s*:\s*"(\d{14,16})"', txt)
                                if not f_ids:
                                    f_ids = re.findall(r'"(?:additional_profile_id)"\s*:\s*"(\d{14,16})"', txt)
                                for fid in f_ids:
                                    if fid != str(uid) and fid != "2829896277312679" and fid not in captured_network_page_ids:
                                        captured_network_page_ids.append(fid)
                    except Exception:
                        pass

                page.on("response", _handle_network_response)

                # --- STEP 1: Page Creation via Method 1 or Method 2 ---
                if self.creation_method == "method2" and BOOKMARKLET_V5_CODE:
                    # === METHOD 2 (API): Automated Core Engine Bookmarklet ===
                    self.log_emitted.emit(f"✨ [METHOD 2 (API)] Executing Automated Core Engine for '{prof_name}'...")
                    try:
                        # 0. Install Network Response Capture Hook in JS
                        page.evaluate(r"""() => {
                            window.__captured_created_page_id = "";
                            window.__captured_created_page_url = "";

                            const origFetch = window.fetch;
                            window.fetch = async function(...args) {
                                const resp = await origFetch.apply(this, args);
                                try {
                                    const clone = resp.clone();
                                    clone.text().then(txt => {
                                        if (txt.includes('additional_profile') || txt.includes('profile_plus') || txt.includes('created_page') || txt.includes('AdditionalProfilePlusCreationMutation')) {
                                            const m = txt.match(/"id"\s*:\s*"(\d{10,})"/);
                                            if (m && m[1] && m[1] !== '2829896277312679') {
                                                window.__captured_created_page_id = m[1];
                                                window.__captured_created_page_url = "https://www.facebook.com/profile.php?id=" + m[1];
                                            }
                                        }
                                    }).catch(()=>{});
                                } catch(e){}
                                return resp;
                            };
                        }""")

                        # 1. Pre-inject STEALTH CSS to guarantee #vip-dash is 100% invisible on screen
                        self.log_emitted.emit(f"🛡️ [STEALTH ACTIVATED] Enabling invisible stealth mode for profile '{prof_name}'...")
                        page.evaluate("""() => {
                            if (!document.getElementById('__stealth_hide_vip__')) {
                                const style = document.createElement('style');
                                style.id = '__stealth_hide_vip__';
                                style.textContent = `
                                    #vip-dash, #vip-dash *, div[id*="vip-dash"], [id^="vip-"] {
                                        position: fixed !important;
                                        left: -99999px !important;
                                        top: -99999px !important;
                                        width: 1px !important;
                                        height: 1px !important;
                                        opacity: 0 !important;
                                        pointer-events: none !important;
                                        z-index: -999999 !important;
                                        clip: rect(0, 0, 0, 0) !important;
                                        transform: translate(-99999px, -99999px) !important;
                                    }
                                `;
                                (document.head || document.documentElement).appendChild(style);
                            }
                        }""")

                        # 2. Inject script via page.evaluate (bypasses Facebook CSP completely)
                        self.log_emitted.emit(f"💉 [SCRIPT INJECTION] Initializing Core Engine on profile '{prof_name}'...")
                        page.evaluate(f"() => {{\n{BOOKMARKLET_V5_CODE}\n}}")

                        # 3. Wait for #vip-dash container to mount in DOM (invisible to user)
                        dash_ready = False
                        for _ in range(25):
                            time.sleep(0.4)
                            if page.evaluate("() => !!document.querySelector('#vip-dash')"):
                                dash_ready = True
                                break

                        if not dash_ready:
                            self.log_emitted.emit("⚠️ [METHOD 2] Retrying script injection...")
                            page.evaluate(f"() => {{\n{BOOKMARKLET_V5_CODE}\n}}")
                            for _ in range(15):
                                time.sleep(0.4)
                                if page.evaluate("() => !!document.querySelector('#vip-dash')"):
                                    dash_ready = True
                                    break

                        if not dash_ready:
                            raise RuntimeError("Core Engine modal failed to mount in DOM.")

                        # 4. Human pacing delay: 2.0s - 3.0s
                        d1 = round(random.uniform(2.0, 3.0), 2)
                        self.log_emitted.emit(f"⏱️ [HUMAN PACING] Delay {d1}s before menu selection...")
                        time.sleep(d1)

                        # 5. Click #nav-ppp (PAGE & PROFILE TOOL) in pure background stealth
                        self.log_emitted.emit("🖱️ [NAVIGATION] Selecting 'PAGE & PROFILE TOOL'...")
                        clicked_nav = page.evaluate("""() => {
                            const el = document.querySelector('#nav-ppp');
                            if (el) { el.click(); return true; }
                            return false;
                        }""")
                        if not clicked_nav:
                            raise RuntimeError("Could not locate or click #nav-ppp in Core Engine.")

                        # 6. Human pacing delay: 2.0s - 3.0s
                        d2 = round(random.uniform(2.0, 3.0), 2)
                        self.log_emitted.emit(f"⏱️ [HUMAN PACING] Delay {d2}s before tool selection...")
                        time.sleep(d2)

                        # 7. Click #ppp-page-creator (PAGE CREATOR TOOLS) in pure background stealth
                        self.log_emitted.emit("🖱️ [NAVIGATION] Opening 'PAGE CREATOR TOOLS'...")
                        clicked_card = page.evaluate("""() => {
                            const el = document.querySelector('#ppp-page-creator');
                            if (el) { el.click(); return true; }
                            return false;
                        }""")
                        if not clicked_card:
                            raise RuntimeError("Could not locate or click #ppp-page-creator in Core Engine.")

                        # 8. Human pacing delay: 2.0s - 3.0s
                        d3 = round(random.uniform(2.0, 3.0), 2)
                        self.log_emitted.emit(f"⏱️ [HUMAN PACING] Delay {d3}s before submission...")
                        time.sleep(d3)

                        # 9. Wait for #ppp-name and #run-page-create in DOM
                        for _ in range(20):
                            time.sleep(0.3)
                            if page.evaluate("() => !!document.querySelector('#ppp-name') && !!document.querySelector('#run-page-create')"):
                                break

                        if self.creation_mode == "custom" and target_name:
                            page.evaluate("""(customName) => {
                                const input = document.querySelector('#ppp-name');
                                if (input) {
                                    input.value = customName;
                                    input.dispatchEvent(new Event('input', { bubbles: true }));
                                    input.dispatchEvent(new Event('change', { bubbles: true }));
                                }
                            }""", target_name)
                            self.log_emitted.emit(f"✏️ [CUSTOM IDENTITY] Injected Custom Page Name into Core Engine: '{target_name}'")
                        else:
                            script_name = page.evaluate("() => document.querySelector('#ppp-name')?.value || ''").strip()
                            if script_name:
                                target_name = script_name
                            self.log_emitted.emit(f"📝 [IDENTITY] Generated Page Name: '{target_name}'")

                        # Dynamic proxy activation
                        if p_bridge and self.proxy_mode == "dynamic":
                            p_bridge.set_mode("UPSTREAM")
                            self.log_emitted.emit(f"🛡️ [DYNAMIC PROXY] Profile '{prof_name}'{rot_tag}: Connected to Residential IP for page creation...")

                        # 10. Click #run-page-create (CREATE PAGE NOW) in pure background stealth
                        self.log_emitted.emit(f"🚀 [SUBMITTING] Clicking 'CREATE PAGE NOW' (#run-page-create)...")
                        page.evaluate("""() => {
                            const btn = document.querySelector('#run-page-create');
                            if (btn) btn.click();
                        }""")

                        # 11. Monitor status for up to 30s
                        for _ in range(30):
                            time.sleep(1.0)
                            cap = page.evaluate("""() => ({
                                id: window.__captured_created_page_id || '',
                                url: window.__captured_created_page_url || ''
                            })""")
                            cap_id = cap.get("id") or ""
                            if cap_id and cap_id.isdigit() and cap_id != "2829896277312679" and cap_id != str(uid):
                                created_ok = True
                                created_page_id = cap_id
                                created_page_link = cap.get("url") or f"https://www.facebook.com/profile.php?id={created_page_id}"
                                self.log_emitted.emit(f"⚡ [CAPTURED] Facebook generated Page ID: {created_page_id}")
                                break

                            if captured_network_page_ids:
                                created_ok = True
                                created_page_id = captured_network_page_ids[-1]
                                created_page_link = f"https://www.facebook.com/profile.php?id={created_page_id}"
                                self.log_emitted.emit(f"⚡ [CAPTURED VIA NETWORK] Page ID: {created_page_id}")
                                break

                            modal_err = page.evaluate("""() => {
                                const el = document.querySelector('#vip-dash');
                                return el ? (el.innerText || '') : '';
                            }""")
                            if any(k in modal_err.lower() for k in ("creation policy violation", "failed", "limit exceeded", "error")):
                                for l in modal_err.split("\n"):
                                    l_c = l.strip()
                                    if any(k in l_c.lower() for k in ("creation policy violation", "failed", "limit", "error")):
                                        if not captured_fb_error:
                                            captured_fb_error = l_c
                                        break

                        # 12. Clean up #vip-dash and stealth styles completely from DOM
                        page.evaluate("""() => {
                            document.querySelector('#vip-dash')?.remove();
                            document.querySelector('#__stealth_hide_vip__')?.remove();
                        }""")

                    except Exception as m2_err:
                        self.log_emitted.emit(f"⚠️ [METHOD 2 NOTICE] Error during execution: {str(m2_err)}")
                        if not captured_fb_error:
                            captured_fb_error = str(m2_err)
                    finally:
                        if p_bridge and self.proxy_mode == "dynamic":
                            p_bridge.set_mode("DIRECT")
                            self.log_emitted.emit(f"🌐 [DYNAMIC PROXY] Profile '{prof_name}': Creation cycle finished. Reverted to Direct PC IP.")

                elif INJECT_SCRIPT_CODE:
                    try:
                        # 0. Install Network Response Capture Hook in JS
                        page.evaluate(r"""() => {
                            window.__captured_created_page_id = "";
                            window.__captured_created_page_url = "";

                            const origFetch = window.fetch;
                            window.fetch = async function(...args) {
                                const resp = await origFetch.apply(this, args);
                                try {
                                    const clone = resp.clone();
                                    clone.text().then(txt => {
                                        if (txt.includes('additional_profile') || txt.includes('profile_plus') || txt.includes('created_page') || txt.includes('AdditionalProfilePlusCreationMutation')) {
                                            const m = txt.match(/"id"\s*:\s*"(\d{10,})"/);
                                            if (m && m[1] && m[1] !== '2829896277312679') {
                                                window.__captured_created_page_id = m[1];
                                                window.__captured_created_page_url = "https://www.facebook.com/profile.php?id=" + m[1];
                                            }
                                        }
                                    }).catch(()=>{});
                                } catch(e){}
                                return resp;
                            };
                        }""")

                        # CRITICAL STEALTH: Pre-inject CSS style so #jsi-box and #jsi-overlay NEVER appear on the browser screen!
                        page.evaluate("""() => {
                            if (!document.getElementById('__stealth_hide_jsi__')) {
                                const style = document.createElement('style');
                                style.id = '__stealth_hide_jsi__';
                                style.textContent = `
                                    #jsi-box, #jsi-overlay, div[id*="jsi-"], div[class*="jsi-"], [id^="jsi-"] {
                                        position: fixed !important;
                                        top: -99999px !important;
                                        left: -99999px !important;
                                        width: 1px !important;
                                        height: 1px !important;
                                        opacity: 0 !important;
                                        visibility: hidden !important;
                                        pointer-events: none !important;
                                        z-index: -99999 !important;
                                        transform: translate(-99999px, -99999px) !important;
                                        clip: rect(0, 0, 0, 0) !important;
                                    }
                                `;
                                (document.head || document.documentElement).appendChild(style);
                            }
                            if (!window.__hide_jsi_interval) {
                                window.__hide_jsi_interval = setInterval(() => {
                                    const b = document.querySelector('#jsi-box');
                                    const o = document.querySelector('#jsi-overlay');
                                    if (b) {
                                        b.style.setProperty('position', 'fixed', 'important');
                                        b.style.setProperty('top', '-99999px', 'important');
                                        b.style.setProperty('left', '-99999px', 'important');
                                        b.style.setProperty('opacity', '0', 'important');
                                        b.style.setProperty('pointer-events', 'none', 'important');
                                        b.style.setProperty('z-index', '-99999', 'important');
                                    }
                                    if (o) {
                                        o.style.setProperty('position', 'fixed', 'important');
                                        o.style.setProperty('top', '-99999px', 'important');
                                        o.style.setProperty('left', '-99999px', 'important');
                                        o.style.setProperty('opacity', '0', 'important');
                                        o.style.setProperty('pointer-events', 'none', 'important');
                                        o.style.setProperty('z-index', '-99999', 'important');
                                    }
                                }, 60);
                            }
                        }""")

                        # 1. Inject canonical 1-Click Script
                        self.log_emitted.emit("⚡ [1-CLICK SCRIPT] Running 1-Click Page Creator in pure background...")
                        page.evaluate(INJECT_SCRIPT_CODE)

                        # 2. Wait up to 10s for #jsi-box container to mount in DOM
                        box_ready = False
                        for _ in range(20):
                            time.sleep(0.4)
                            box_ready = page.evaluate("() => !!document.querySelector('#jsi-box')")
                            if box_ready:
                                break

                        if not box_ready:
                            page.evaluate(INJECT_SCRIPT_CODE)
                            for _ in range(10):
                                time.sleep(0.4)
                                if page.evaluate("() => !!document.querySelector('#jsi-box')"):
                                    box_ready = True
                                    break

                        # 3. Click "CREATE FACEBOOK PAGE" button
                        clicked_create = False
                        for _ in range(12):
                            clicked_create = page.evaluate("""() => {
                                const btns = Array.from(document.querySelectorAll('#jsi-box button, #jsi-box div, #jsi-box a, #jsi-box span'));
                                for (const b of btns) {
                                    const txt = (b.innerText || b.textContent || '').trim().toUpperCase();
                                    if (txt.includes('CREATE FACEBOOK PAGE')) {
                                        b.click();
                                        return true;
                                    }
                                }
                                return false;
                            }""")
                            if clicked_create:
                                break
                            time.sleep(0.4)

                        # 4. Wait for #pc-name input and #pc-go button to mount in DOM
                        for _ in range(15):
                            time.sleep(0.4)
                            if page.evaluate("() => !!document.querySelector('#pc-name') && !!document.querySelector('#pc-go')"):
                                break

                        # 5. Set Name, Category and Trigger Backend Creation via #pc-go
                        if p_bridge and self.proxy_mode == "dynamic":
                            p_bridge.set_mode("UPSTREAM")
                            self.log_emitted.emit(f"🛡️ [DYNAMIC PROXY] Profile '{prof_name}'{rot_tag}: Connected to Residential IP for page creation...")

                        self.log_emitted.emit(f"⚡ [1-CLICK SCRIPT] Submitting '{target_name}' (Category: {eff_category_name} | ID: {eff_category_id})...")
                        page.evaluate("""({name, catId}) => {
                            window.__selected_category_id = catId;
                            const inp = document.querySelector('#pc-name');
                            if (inp) {
                                inp.value = name;
                                inp.dispatchEvent(new Event('input', { bubbles: true }));
                                inp.dispatchEvent(new Event('change', { bubbles: true }));
                            }
                            const catSelect = document.querySelector('#pc-category, #pc-cat, select');
                            if (catSelect) {
                                catSelect.value = catId;
                                catSelect.dispatchEvent(new Event('change', { bubbles: true }));
                            }
                            const goBtn = document.querySelector('#pc-go');
                            if (goBtn) {
                                goBtn.click();
                            }
                        }""", {"name": target_name, "catId": str(eff_category_id)})

                        # 6. Monitor status for up to 25 seconds
                        for _ in range(25):
                            time.sleep(1.0)
                            # Check window network capture hook
                            cap = page.evaluate("""() => ({
                                id: window.__captured_created_page_id || '',
                                url: window.__captured_created_page_url || ''
                            })""")
                            cap_id = cap.get("id") or ""
                            if cap_id and cap_id.isdigit() and cap_id != "2829896277312679" and cap_id != str(uid):
                                created_ok = True
                                created_page_id = cap_id
                                created_page_link = cap.get("url") or f"https://www.facebook.com/profile.php?id={created_page_id}"
                                self.log_emitted.emit(f"⚡ [CAPTURED] Facebook generated Page ID: {created_page_id}")
                                break

                            # Check Playwright network listener
                            if captured_network_page_ids:
                                created_ok = True
                                created_page_id = captured_network_page_ids[-1]
                                created_page_link = f"https://www.facebook.com/profile.php?id={created_page_id}"
                                self.log_emitted.emit(f"⚡ [CAPTURED VIA NETWORK] Page ID: {created_page_id}")
                                break

                            # Check #jsi-log for success, completion, or failure reason
                            log_text = page.evaluate("""() => {
                                const el = document.querySelector('#jsi-log');
                                return el ? (el.innerText || el.textContent || '') : '';
                            }""")
                            if "Page created" in log_text or "created:" in log_text.lower():
                                created_ok = True
                                break
                            if any(k in log_text.lower() for k in ("error", "failed", "limit", "too many", "cannot", "rejected", "blocked")):
                                for line in log_text.split("\n"):
                                    l_clean = line.strip().lstrip(">").strip()
                                    if any(k in l_clean.lower() for k in ("error", "failed", "limit", "too many", "cannot", "rejected", "blocked")):
                                        if not captured_fb_error:
                                            captured_fb_error = l_clean
                                        break

                        # Check if log HTML or text contained any valid ID
                        if not created_page_id:
                            captured_info = page.evaluate("""() => {
                                const el = document.querySelector('#jsi-log');
                                const html = el ? el.innerHTML : '';
                                const txt = el ? el.innerText : '';
                                return {
                                    id: window.__captured_created_page_id || '',
                                    url: window.__captured_created_page_url || '',
                                    log_html: html,
                                    log_txt: txt
                                };
                            }""")
                            if captured_info.get("id") and captured_info["id"] != "2829896277312679" and captured_info["id"] != str(uid):
                                created_page_id = captured_info["id"]
                                created_page_link = captured_info.get("url") or f"https://www.facebook.com/profile.php?id={created_page_id}"
                            else:
                                full_log = (captured_info.get("log_html", "") + " " + captured_info.get("log_txt", ""))
                                m_log = re.findall(r'(\d{14,16})', full_log)
                                for mid in m_log:
                                    if mid != str(uid) and mid != "2829896277312679":
                                        created_page_id = mid
                                        created_page_link = f"https://www.facebook.com/profile.php?id={created_page_id}"
                                        break

                        # 7. Clean up injected elements completely from DOM and clear interval
                        page.evaluate("""() => {
                            if (window.__hide_jsi_interval) clearInterval(window.__hide_jsi_interval);
                            document.querySelector('#jsi-overlay')?.remove();
                            document.querySelector('#jsi-box')?.remove();
                            document.querySelector('#__stealth_hide_jsi__')?.remove();
                        }""")

                    except Exception as inj_err:
                        self.log_emitted.emit(f"⚠️ [INJECT NOTICE] Script evaluation: {str(inj_err)}")
                    finally:
                        if p_bridge and self.proxy_mode == "dynamic":
                            p_bridge.set_mode("DIRECT")
                            self.log_emitted.emit(f"🌐 [DYNAMIC PROXY] Profile '{prof_name}': Creation cycle finished. Reverted to Direct PC IP.")


                # Extract Page Link and ID from captured network traffic if still missing
                if (not created_page_id or not created_page_id.isdigit()) and captured_network_page_ids:
                    created_page_id = captured_network_page_ids[-1]
                    created_page_link = f"https://www.facebook.com/profile.php?id={created_page_id}"

                # Extract from current URL
                if not created_page_id or not created_page_id.isdigit():
                    curr_url = page.url or ""
                    m_id = re.search(r'facebook\.com/(?:pages/)?(?:profile\.php\?id=)?(\d{14,16})', curr_url)
                    if m_id and m_id.group(1) != "2829896277312679" and m_id.group(1) != str(uid):
                        created_page_id = m_id.group(1)
                        created_page_link = f"https://www.facebook.com/profile.php?id={created_page_id}"

                # Fallback discovery from Your Pages list if ID is still not found
                if not created_page_id or not created_page_id.isdigit():
                    try:
                        page.goto("https://web.facebook.com/pages/?category=your_pages", timeout=25000, wait_until="domcontentloaded")
                        time.sleep(3.5)
                        discovered_id = page.evaluate(r"""(tName) => {
                            const links = Array.from(document.querySelectorAll('a[href*="profile.php"], a[href*="/pages/"], a[role="link"]'));
                            for (const a of links) {
                                const text = (a.innerText || a.textContent || '').trim();
                                if (text === tName || text.includes(tName)) {
                                    const href = a.getAttribute('href') || '';
                                    const m = href.match(/(?:id=|\/)(\d{14,16})/);
                                    if (m) return m[1];
                                }
                            }
                            return '';
                        }""", target_name)
                        if discovered_id and discovered_id != "2829896277312679" and discovered_id != str(uid):
                            created_page_id = discovered_id
                            created_page_link = f"https://www.facebook.com/profile.php?id={created_page_id}"
                    except Exception:
                        pass

                # Strict Verification: Success requires a genuine 14-16 digit Page ID
                is_genuine_success = bool(
                    created_page_id and 
                    str(created_page_id).isdigit() and 
                    len(str(created_page_id)) >= 14 and 
                    str(created_page_id) != "2829896277312679" and 
                    str(created_page_id) != str(uid)
                )

                if is_genuine_success:
                    page_record = {
                        "profile_number": prof_num_val,
                        "uid": uid or prof_uid,
                        "password": prof_pass,
                        "secret_2fa": prof_2fa,
                        "cookie": prof_cookie,
                        "status": "Success",
                        "page_name": target_name,
                        "page_id": created_page_id,
                        "page_link": created_page_link,
                        "page_url": created_page_link,
                        "creator_uid": uid or prof_uid,
                        "category": eff_category_name,
                        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "group": profile_data.get("group", "Default")
                    }
                    pages_created.append(page_record)
                    self.log_emitted.emit(f"🟢 [SUCCESS] Page '{target_name}' created successfully! (ID: {created_page_id} | Link: {created_page_link})")

                    # ALWAYS navigate to the created page and show it on browser as instructed by user
                    target_page_url = f"https://web.facebook.com/profile.php?id={created_page_id}"
                    try:
                        self.log_emitted.emit(f"🌐 [PAGE LOAD] Displaying created page '{target_page_url}' on browser...")
                        page.goto(target_page_url, timeout=30000, wait_until="domcontentloaded")
                    except Exception:
                        pass

                    # Wait 2.5 - 3.0 seconds on the page
                    time.sleep(2.5)

                    # Auto-switch execution: seamlessly switch Facebook active voice to the newly created Page
                    if self.auto_switch_page:
                        self.log_emitted.emit(f"🔄 [AUTO-SWITCH] Switching Facebook active profile to newly created Page '{target_name}'...")
                        sw_ok, sw_msg = switch_facebook_to_page_profile(page, created_page_id, target_name)
                        if sw_ok:
                            self.log_emitted.emit(f"🟢 [SWITCH SUCCESS] {sw_msg}")
                        else:
                            self.log_emitted.emit(f"ℹ️ [SWITCH STATUS] Profile '{prof_name}': {sw_msg}")

                        # Keep newly switched page active and visible for 3 seconds
                        time.sleep(3.0)
                    else:
                        time.sleep(3.0)

                    # Always close the browser when profile page creation task is complete
                    self.log_emitted.emit(f"🔒 [TASK COMPLETE] Successfully finished profile '{prof_name}'. Closing browser...")
                    safely_close_profile_browser(context, browser_cdp, user_dir, cdp_port, profile_data.get("id"), launcher, page)

                else:
                    # STRICT USER DIRECTIVE: When page creation fails, IMMEDIATELY terminate & close the browser!
                    err_detail = f" - Reason: {captured_fb_error}" if captured_fb_error else " (No genuine Page ID generated)"
                    self.log_emitted.emit(f"🔴 [FAILED] Facebook rejected page creation for profile '{prof_name}'{err_detail}.")
                    ss_path = ""
                    try:
                        ss_path = capture_diagnostic_screenshot(
                            page=page,
                            profile_name=prof_name,
                            label="page_creation_failed",
                            uid=uid,
                            extra_info=captured_fb_error or "Facebook rejected creation / Limit reached"
                        )
                        if ss_path:
                            self.log_emitted.emit(f"📸 [DIAGNOSTIC SCREENSHOT] Saved: {Path(ss_path).name}")
                    except Exception:
                        pass
                    self.log_emitted.emit(f"🛑 [CLOSING BROWSER] Page creation failed. Terminating browser for profile '{prof_name}'...")
                    safely_close_profile_browser(context, browser_cdp, user_dir, cdp_port, profile_data.get("id"), launcher, page)
                    self._move_profile_to_failed_group(profile_data)
                    fail_rec = [{
                        "profile_number": prof_num_val,
                        "uid": uid or prof_uid,
                        "password": prof_pass,
                        "secret_2fa": prof_2fa,
                        "cookie": prof_cookie,
                        "status": "Fail",
                        "failure_reason": captured_fb_error or "Facebook rejected creation / Limit reached",
                        "page_name": target_name,
                        "page_id": "",
                        "page_link": "",
                        "page_url": "",
                        "creator_uid": uid or prof_uid,
                        "category": eff_category_name,
                        "screenshot_path": ss_path,
                        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "group": profile_data.get("group", "Default")
                    }]
                    return False, "Failed to create pages", fail_rec

                if pages_created:
                    return True, "Pages created successfully", pages_created
                return False, "Failed to create pages", []

        except Exception as err:
            self.log_emitted.emit(f"❌ [EXCEPTION] Profile '{prof_name}': {str(err)}")
            ss_path = ""
            try:
                if page and not page.is_closed():
                    ss_path = capture_diagnostic_screenshot(
                        page=page,
                        profile_name=prof_name,
                        label="exception",
                        uid=str(profile_data.get("fb_uid") or profile_data.get("uid") or ""),
                        extra_info=str(err)
                    )
                    if ss_path:
                        self.log_emitted.emit(f"📸 [DIAGNOSTIC SCREENSHOT] Saved: {Path(ss_path).name}")
            except Exception:
                pass
            self.log_emitted.emit(f"🛑 [CLOSING BROWSER] Exception occurred. Terminating browser for profile '{prof_name}'...")
            safely_close_profile_browser(context, browser_cdp, user_dir, cdp_port, profile_data.get("id"), launcher, page)
            self._move_profile_to_failed_group(profile_data)
            fail_rec = [{
                "profile_number": prof_num_val,
                "uid": prof_uid,
                "password": prof_pass,
                "secret_2fa": prof_2fa,
                "cookie": prof_cookie,
                "status": "Fail",
                "failure_reason": f"Exception: {str(err)}",
                "page_name": "N/A",
                "page_id": "",
                "page_link": "",
                "page_url": "",
                "creator_uid": prof_uid,
                "category": getattr(self, "category_name", "Digital Creator"),
                "screenshot_path": ss_path,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "group": profile_data.get("group", "Default")
            }]
            return False, f"Exception: {str(err)}", fail_rec
        finally:
            if p_bridge:
                try:
                    p_bridge.stop()
                except Exception:
                    pass
            if context:
                unregister_active_browser_session(context)
            if not pages_created or self._is_stopped:
                # Guaranteed failsafe: Never leave browser open if page creation failed or user stopped
                safely_close_profile_browser(context, browser_cdp, user_dir, cdp_port, profile_data.get("id"), launcher, page)
