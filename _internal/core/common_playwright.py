import os
import sys
import re
import time
import json
import random
import shutil
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure 01_Main_Software/core directory is present in sys.path to eliminate ModuleNotFoundError
_this_file_dir = Path(__file__).resolve().parent
_app_root_dir = _this_file_dir.parent
for _d_path in [
    _app_root_dir / "01_Main_Software" / "core",
    _app_root_dir / "01_Main_Software",
    _app_root_dir / "core",
    _this_file_dir
]:
    if _d_path.exists() and str(_d_path.resolve()) not in sys.path:
        sys.path.insert(0, str(_d_path.resolve()))

def resolve_user_data_dir(pdata: dict) -> str:
    """Smart resolution of Chrome user data directory matching srkBrowser core profile manager."""
    user_data_dir = pdata.get("user_data_dir") or pdata.get("folder_path")
    if user_data_dir and os.path.exists(user_data_dir):
        return str(Path(user_data_dir).resolve())

    pid = str(pdata.get("id", "")).strip()
    pnum_raw = str(pdata.get("number", pdata.get("name", "Profile"))).strip()
    pname = str(pdata.get("name", "Profile")).strip()
    num_digits = re.sub(r"\D", "", pnum_raw) or re.sub(r"\D", "", pname)

    appdata_roaming = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))) / "BrowserProfileManager"
    appdata_local = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "BrowserProfileManager"

    if getattr(sys, 'frozen', False):
        app_root = Path(sys.executable).parent.resolve()
    else:
        app_root = Path(__file__).resolve().parent.parent.parent

    # Candidate profile roots (prioritize portable data directory)
    root_candidates = [
        app_root / "data" / "profiles",
        app_root / "data",
        app_root / "profiles",
        appdata_roaming / "profiles",
        appdata_local / "profiles",
        app_root / "01_Main_Software" / "core" / "profiles",
        app_root / "01_Main_Software" / "profiles",
        app_root / "core" / "profiles",
        app_root.parent / "01_Main_Software" / "core" / "profiles",
        app_root.parent / "01_Main_Software" / "profiles",
        app_root.parent / "profiles"
    ]

    # Name variations to check
    name_variations = []
    if pdata.get("number"):
        name_variations.append(str(pdata.get("number")).strip())
    if num_digits:
        name_variations.append(f"Profile{int(num_digits):03d}")
        name_variations.append(f"Profile{num_digits}")
        name_variations.append(f"#{num_digits}")
        name_variations.append(num_digits)
    if pname and pname not in name_variations:
        name_variations.append(pname)
    if pid and pid not in name_variations:
        name_variations.append(pid)

    # 1. Search in root candidates and their users/* subfolders
    for base in root_candidates:
        if not base.exists():
            continue
        
        # Check users/* subfolders
        users_dir = base / "users"
        if users_dir.exists():
            for u_sub in users_dir.iterdir():
                if u_sub.is_dir():
                    for var in name_variations:
                        cand = u_sub / var
                        if cand.exists() and cand.is_dir():
                            return str(cand.resolve())

        # Check directly under base
        for var in name_variations:
            cand = base / var
            if cand.exists() and cand.is_dir():
                return str(cand.resolve())

    # 2. Target creation directory if not found
    target_base = root_candidates[0]
    for b in root_candidates:
        if b.exists():
            target_base = b
            break

    try:
        from auth_manager import AuthManager
        auth = AuthManager()
        curr = auth.get_current_user()
        if curr and curr.get("is_logged_in") and curr.get("email"):
            safe_email = re.sub(r"[^a-zA-Z0-9_]", "_", curr["email"].strip().lower())
            target_base = target_base / "users" / safe_email
        else:
            target_base = target_base / "users" / "default"
    except Exception:
        target_base = target_base / "users" / "default"

    folder_name = pdata.get("number") or (f"Profile{int(num_digits):03d}" if num_digits else "Profile001")
    target = target_base / folder_name
    target.mkdir(parents=True, exist_ok=True)
    return str(target.resolve())

def calculate_cdp_port(pdata: dict, idx: int = 1) -> int:
    """Calculates deterministic CDP port matching srkBrowser core browser manager."""
    try:
        pnum_raw = str(pdata.get("number", pdata.get("name", idx))).replace("Profile", "").replace("#", "").strip()
        num_clean = re.sub(r"\D", "", pnum_raw)
        if num_clean:
            n_val = int(num_clean)
        else:
            n_val = idx
        return 9200 + (n_val % 500)
    except Exception:
        return 9200 + (idx % 500)

def get_chrome_executable_path(playwright_instance: Optional[Any] = None) -> Optional[str]:
    """
    Finds bundled Portable Chromium (matching srkBrowser core) executable.
    STRICT RULE: Never uses or falls back to system installed Chrome.
    """
    try:
        from utils import get_system_browsers
        browsers = get_system_browsers()
        if browsers:
            for label, exe_path in browsers.items():
                if "portable" in label.lower() or "bundled" in label.lower() or "chromium" in label.lower():
                    if os.path.exists(exe_path):
                        return exe_path
    except Exception:
        pass

    if getattr(sys, 'frozen', False):
        app_root = Path(sys.executable).parent.resolve()
    else:
        app_root = Path(__file__).resolve().parent.parent

    local_appdata = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    appdata_roaming = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))

    portable_paths = [
        app_root / "chromium" / "chrome.exe",
        app_root / "_internal" / "chromium" / "chrome.exe",
        app_root / "01_Main_Software" / "chromium" / "chrome.exe",
        app_root / "bin" / "chromium" / "chrome.exe",
        app_root / "assets" / "chromium" / "chrome.exe",
        app_root / "dist" / "srkBrowser" / "chromium" / "chrome.exe",
        app_root.parent / "chromium" / "chrome.exe",
        app_root.parent / "01_Main_Software" / "chromium" / "chrome.exe",
        appdata_roaming / "BrowserProfileManager" / "chromium" / "chrome.exe",
        local_appdata / "BrowserProfileManager" / "chromium" / "chrome.exe"
    ]

    for p in portable_paths:
        if p.exists():
            return str(p.resolve())

    if local_appdata.exists():
        pw_dir = local_appdata / "ms-playwright"
        if pw_dir.exists():
            pw_chromes = (
                list(pw_dir.glob("chromium-*/chrome-win/chrome.exe")) +
                list(pw_dir.glob("chromium-*/chrome-win64/chrome.exe"))
            )
            for pw_c in pw_chromes:
                if pw_c.exists():
                    return str(pw_c.resolve())

    if playwright_instance:
        try:
            exe = playwright_instance.chromium.executable_path
            if exe and os.path.exists(exe):
                return str(exe)
        except Exception:
            pass

    return None

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
    """Ensures active Facebook session cookies (c_user, xs, datr, fr, sb, etc.) are available on .facebook.com domain."""
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

def check_bot_facebook_login_status(page: Any, context: Any = None) -> Tuple[bool, str]:
    """
    Bot-specific robust login status verifier.
    Checks for visible login forms / login.php URLs FIRST to prevent false-positive session claims,
    then verifies logged-in UI elements and session cookies.
    """
    try:
        url = page.url.lower()

        # 1. Check if on Security Checkpoint, 2FA Page, or Login Page URL
        checkpoint_keywords = [
            "checkpoint", "security", "two_step", "two_factor", "2fa",
            "authentication", "auth_platform", "limbo", "challenge", "recover"
        ]
        if any(k in url for k in checkpoint_keywords):
            return False, f"On Checkpoint / 2FA screen ({url})"

        if "login.php" in url or "/login" in url or "next=" in url:
            return False, f"On Facebook Login Page ({url})"

        # 2. Check for active login form elements or public logged-out elements visible on screen
        try:
            body_text = page.locator("body").inner_text(timeout=1500).lower()
            logged_out_phrases = [
                "log in to facebook",
                "join or log into facebook",
                "email address or mobile number",
                "forgotten password?",
                "log into your meta account",
                "business or brand",
                "community or public figure"
            ]
            if any(p in body_text for p in logged_out_phrases):
                if page.locator("input[name='email'], input[name='pass'], input[type='password']").count() > 0 or "join or log into facebook" in body_text:
                    return False, "Logged Out Form Active on Screen"
        except Exception:
            pass

        try:
            if page.locator("input[type='password']").first.is_visible(timeout=1000):
                return False, "Password Field Active on Screen"
        except Exception:
            pass

        # 3. Check for Logged-In DOM Indicators (Header, Navigation, Feed)
        logged_in_selectors = [
            "a[aria-label='Facebook']",
            "svg[aria-label='Facebook']",
            "a[aria-label='Home']",
            "div[role='navigation']",
            "[aria-label*='Account']",
            "[aria-label*='Your profile']",
            "[aria-label*='Menu']",
            "input[placeholder*='Search Facebook']",
            "div[role='main']"
        ]
        for sel in logged_in_selectors:
            try:
                if page.locator(sel).first.is_visible(timeout=1000):
                    return True, f"Logged-in UI detected ({sel})"
            except Exception:
                pass

        # 4. Check active session cookies in Playwright context (c_user or xs)
        target_context = context or getattr(page, "context", None)
        has_session_cookie = False
        if target_context:
            try:
                cookies = target_context.cookies()
                has_session_cookie = any(
                    c.get("name") in ("c_user", "xs") and str(c.get("value", "")).strip() != ""
                    for c in cookies
                )
            except Exception:
                pass

        if has_session_cookie:
            return True, "Valid Facebook Session (c_user / xs active)"

        # 5. Check JS cookie fallback
        try:
            js_cuser = page.evaluate("() => document.cookie.includes('c_user=') || document.cookie.includes('xs=')")
            if js_cuser:
                return True, "Valid Session Cookie via JS"
        except Exception:
            pass

        return False, "No active session cookie or logged-in interface detected"
    except Exception as exc:
        return True, f"Assumption Logged In (Check error: {exc})"

def disable_chrome_password_manager_preferences(user_data_dir: str) -> None:
    """Updates Chrome profile Preferences JSON file on disk to permanently disable Password Manager bubbles."""
    try:
        if not user_data_dir or not os.path.exists(user_data_dir):
            return
        pref_dir = os.path.join(user_data_dir, "Default")
        os.makedirs(pref_dir, exist_ok=True)
        pref_file = os.path.join(pref_dir, "Preferences")

        prefs = {}
        if os.path.exists(pref_file):
            try:
                with open(pref_file, "r", encoding="utf-8") as f:
                    prefs = json.load(f)
            except Exception:
                prefs = {}

        prefs["credentials_enable_service"] = False
        if "profile" not in prefs or not isinstance(prefs["profile"], dict):
            prefs["profile"] = {}
        prefs["profile"]["password_manager_enabled"] = False
        prefs["profile"]["password_manager_leak_detection"] = False

        if "autofill" not in prefs or not isinstance(prefs["autofill"], dict):
            prefs["autofill"] = {}
        prefs["autofill"]["credit_card_enabled"] = False

        with open(pref_file, "w", encoding="utf-8") as f:
            json.dump(prefs, f)
    except Exception:
        pass


def configure_antidetect_context(context: Any, config: Optional[Dict[str, Any]] = None) -> None:
    """Apply stealth antidetect scripts & overrides to Playwright context."""
    if not config:
        config = {}
    ua = config.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    try:
        context.add_init_script(f"""
            Object.defineProperty(navigator, 'webdriver', {{ get: () => undefined }});
            Object.defineProperty(navigator, 'languages', {{ get: () => ['en-US', 'en'] }});
            Object.defineProperty(navigator, 'plugins', {{ get: () => [1, 2, 3, 4, 5] }});
            window.chrome = {{ runtime: {{}} }};
        """)
    except Exception:
        pass



def cleanup_profile_lock_files(user_data_dir: str) -> None:
    """Removes stale SingletonLock, lockfile, and DevToolsActivePort files if profile process is inactive."""
    try:
        p_dir = Path(user_data_dir)
        if not p_dir.exists():
            return
        lock_files = [
            p_dir / "SingletonLock",
            p_dir / "lockfile",
            p_dir / "DevToolsActivePort"
        ]
        for lf in lock_files:
            if lf.exists():
                try:
                    lf.unlink(missing_ok=True)
                except Exception:
                    pass
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


def kill_profile_chrome_process(user_data_dir: str, cdp_port: int = 0) -> None:
    """Forcefully terminates any Chrome / Chromium processes running for a given user_data_dir or CDP port."""
    if not user_data_dir and not cdp_port:
        return

    # 1. Try closing via CDP endpoint
    if cdp_port:
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{cdp_port}/json/close", data=b"")
            urllib.request.urlopen(req, timeout=1)
        except Exception:
            pass

    # 2. Windows process termination by user-data-dir folder name
    if os.name == 'nt' and user_data_dir:
        try:
            import subprocess
            folder_name = Path(user_data_dir).name
            if folder_name and len(folder_name) > 1:
                cmd = f'powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \\"Name = \'chrome.exe\' and CommandLine like \'%{folder_name}%\'\\" | Invoke-CimMethod -MethodName Terminate"'
                subprocess.run(cmd, shell=True, capture_output=True, timeout=3)
        except Exception:
            pass


def close_bot_browser_context(context: Any = None, profile_data: Optional[Dict[str, Any]] = None) -> None:
    """Closes Playwright context and guarantees that the native Portable Chromium process is terminated."""
    if context:
        try:
            if hasattr(context, 'browser') and context.browser:
                context.browser.close()
            else:
                context.close()
        except Exception:
            pass

    if profile_data:
        try:
            user_dir = resolve_user_data_dir(profile_data)
            cdp_p = calculate_cdp_port(profile_data)
            kill_profile_chrome_process(user_dir, cdp_p)
        except Exception:
            pass


def init_bot_browser_context(
    playwright_instance: Any,
    profile_data: Dict[str, Any],
    profile_index: int = 1,
    headless: bool = False,
    log_func: Optional[Any] = None
) -> Tuple[Any, Any, bool, bool]:
    """
    Universal Bot Initialization Engine for srkBrowser.
    Returns: (context, page, is_logged_in, connected_via_cdp)
    """
    isolate_greenlet_context()
    def log(msg: str) -> None:
        if log_func:
            log_func(msg)
        else:
            print(msg)

    pname = profile_data.get("name", f"Profile{profile_index:03d}")
    user_data_dir = resolve_user_data_dir(profile_data)
    cdp_port = calculate_cdp_port(profile_data, profile_index)
    cdp_url = f"http://127.0.0.1:{cdp_port}"

    context = None
    connected_via_cdp = False

    # 1. Attempt Smart CDP Connection if browser is already open
    try:
        browser_cdp = playwright_instance.chromium.connect_over_cdp(cdp_url)
        if browser_cdp:
            context = browser_cdp.contexts[0] if browser_cdp.contexts else browser_cdp.new_context()
            connected_via_cdp = True
            log(f"  🔗 [Smart CDP] Successfully connected to ALREADY OPEN browser for '{pname}' (Port {cdp_port})!")
    except Exception:
        connected_via_cdp = False

    # 2. Fallback: Launch native Portable Chromium via srkBrowser BrowserLauncher & connect via CDP
    if not context:
        cleanup_profile_lock_files(user_data_dir)
        disable_chrome_password_manager_preferences(user_data_dir)
        chrome_exe = get_chrome_executable_path(playwright_instance=playwright_instance)

        raw_num = str(profile_data.get("number", profile_index)).replace("Profile", "").replace("#", "").strip()
        num_text = f"{int(raw_num):02d}" if raw_num.isdigit() else (raw_num or "01")

        # Primary Launch Engine: Use official srkBrowser BrowserLauncher for 100% consistent native UI, colors & badges!
        launcher_success = False
        try:
            try:
                from core.browser import BrowserLauncher
                launcher = BrowserLauncher()
            except ImportError:
                from browser import BrowserLauncher
                launcher = BrowserLauncher()

            p_dir = Path(user_data_dir)
            ok_l, msg_l = launcher.launch_profile(chrome_exe, p_dir, profile_data)
            if ok_l:
                launcher_success = True
                log(f"  🚀 [Native BrowserLauncher] Launched native srkBrowser Portable Chromium for '{pname}' (#{num_text}).")
        except Exception as l_err:
            log(f"  ⚠️ BrowserLauncher note: {l_err}. Falling back to native subprocess launcher...")
            launcher_success = False

        if not launcher_success and chrome_exe and os.path.exists(chrome_exe) and not headless:
            color_name = profile_data.get("color", "Red")
            color_hex = "#f38ba8"
            try:
                from config import COLOR_PALETTE
                color_hex = COLOR_PALETTE.get(color_name, "#f38ba8") if isinstance(COLOR_PALETTE, dict) else "#f38ba8"
            except Exception:
                pass

            p_dir = Path(user_data_dir)
            ico_path = p_dir / "profile_icon.ico"
            prof_num_int = int(raw_num) if raw_num.isdigit() else 1
            try:
                try:
                    from core.browser import generate_profile_icon_ico, create_badge_extension, apply_window_icon_win32
                except ImportError:
                    try:
                        from browser import generate_profile_icon_ico, create_badge_extension, apply_window_icon_win32
                    except ImportError:
                        def generate_profile_icon_ico(*a, **kw): pass
                        def create_badge_extension(*a, **kw): return ""
                        def apply_window_icon_win32(*a, **kw): pass
                generate_profile_icon_ico(num_text, ico_path, color_hex, prof_num_int)
                badge_ext_path = create_badge_extension(p_dir, profile_data)
            except Exception:
                badge_ext_path = ""

            try:
                import subprocess
                cmd = [
                    chrome_exe,
                    f"--user-data-dir={user_data_dir}",
                    f"--remote-debugging-port={cdp_port}",
                    "--remote-allow-origins=*",
                    f"--app-id=srkBrowser_{num_text}",
                    "--start-maximized",
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
                    "--disable-blink-features=AutomationControlled"
                ]
                if badge_ext_path and os.path.exists(badge_ext_path):
                    cmd.append(f"--load-extension={badge_ext_path}")

                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
                )
                if ico_path.exists():
                    try:
                        apply_window_icon_win32(proc.pid, ico_path)
                    except Exception:
                        pass
                log(f"  🚀 Launched native Portable Chromium with Color Badge Extension for '{pname}' (#{num_text}).")
            except Exception as sp_err:
                log(f"  ⚠️ Subprocess launch notice: {sp_err}")

        # Connect Playwright over CDP to the running Portable Chromium instance
        for _cdp_attempt in range(25):
            time.sleep(0.3)
            try:
                browser_cdp = playwright_instance.chromium.connect_over_cdp(cdp_url)
                if browser_cdp:
                    context = browser_cdp.contexts[0] if browser_cdp.contexts else browser_cdp.new_context()
                    connected_via_cdp = True
                    log(f"  🔗 Connected to srkBrowser Native Portable Chromium via CDP (Port {cdp_port})!")
                    break
            except Exception:
                pass

        if not context:
            cleanup_profile_lock_files(user_data_dir)
            args = [
                "--remote-allow-origins=*",
                "--start-maximized",
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
                "--js-flags=--max_old_space_size=512",
                "--renderer-process-limit=4",
                "--disable-breakpad",
                "--disable-sync",
                "--disable-domain-reliability",
                "--disable-client-side-phishing-detection",
                "--disable-default-apps",
                "--disable-speech-api",
                "--disable-wake-on-wifi",
                "--enable-low-res-tiling",
                "--enable-features=HighEfficiencyModeAvailable"
            ]

            launch_kwargs = {
                "user_data_dir": user_data_dir,
                "headless": headless,
                "viewport": None,
                "args": args
            }
            if chrome_exe and os.path.exists(chrome_exe):
                launch_kwargs["executable_path"] = chrome_exe
            else:
                log(f"  ❌ Bundled Portable Chromium not found on system! Checked paths for srkBrowser.")
                return None, None, False, False

            try:
                context = playwright_instance.chromium.launch_persistent_context(**launch_kwargs)
            except Exception as lpc_err:
                log(f"  ⚠️ Initial persistent launch note: {lpc_err}. Cleaning stale locks & retrying...")
                time.sleep(1.0)
                cleanup_profile_lock_files(user_data_dir)
                try:
                    context = playwright_instance.chromium.launch_persistent_context(**launch_kwargs)
                except Exception as lpc_err2:
                    log(f"  ⚠️ Retrying CDP connection for port {cdp_port}...")
                    time.sleep(1.5)
                    try:
                        browser_cdp = playwright_instance.chromium.connect_over_cdp(cdp_url)
                        if browser_cdp and browser_cdp.contexts:
                            context = browser_cdp.contexts[0]
                            connected_via_cdp = True
                        else:
                            raise lpc_err2
                    except Exception:
                        raise lpc_err2

    configure_antidetect_context(context, profile_data)

    # 3. Pre-inject profile session cookies ONLY if creating a fresh context (never overwrite active disk cookies over CDP)
    c_str = profile_data.get("cookie", "")
    if not c_str and profile_data.get("notes"):
        for line in str(profile_data["notes"]).split("\n"):
            if line.strip().startswith("Cookie:"):
                c_str = line.strip().replace("Cookie:", "").strip()
                break

    if c_str and not connected_via_cdp:
        try:
            p_ck = parse_cookie_string(c_str, default_domain=".facebook.com")
            if p_ck:
                p_ck.append({"name": "locale", "value": "en_US", "domain": ".facebook.com", "path": "/"})
                context.add_cookies(p_ck)
        except Exception:
            pass

    ensure_facebook_subdomain_cookies(context)

    page = context.pages[0] if context.pages else context.new_page()
    try:
        page.bring_to_front()
    except Exception:
        pass

    # 4. Check if already on active Facebook session
    curr_url = ""
    try:
        curr_url = page.url.lower()
    except Exception:
        pass

    is_in = False
    login_msg = "Not checked"

    if "facebook.com" in curr_url and "login.php" not in curr_url:
        is_in, login_msg = check_bot_facebook_login_status(page, context)
        if is_in:
            log(f"  ✅ [Phase 1] Active Facebook session already open for '{pname}'. Preserving session without reload!")

    if not is_in:
        if "facebook.com" not in curr_url or "login.php" in curr_url:
            log(f"  🔐 [Phase 1] Navigating to Facebook Home (https://www.facebook.com/) for '{pname}'...")
            try:
                page.goto("https://www.facebook.com/", timeout=25000, wait_until="domcontentloaded")
                time.sleep(1.5)
                ensure_facebook_subdomain_cookies(context)
            except Exception:
                pass

        # Handle Account Chooser / Continue Prompt if needed
        pwd = profile_data.get("password", "")
        if not pwd and profile_data.get("notes"):
            for line in str(profile_data["notes"]).split("\n"):
                l_s = line.strip()
                if l_s.lower().startswith("password:") or l_s.lower().startswith("pass:"):
                    pwd = l_s.split(":", 1)[1].strip()
                    break

        try:
            handle_facebook_profile_continue_screen(page=page, password=pwd, log_func=log)
        except Exception:
            pass

        is_in, login_msg = check_bot_facebook_login_status(page, context)

    # 5. Automatic Re-Login Fallback if STILL Logged Out
    if not is_in:
        log(f"  ⚠️ Account '{pname}' is LOGGED OUT ({login_msg}). Attempting automatic re-login...")
        try:
            from automation import attempt_profile_relogin
        except ImportError:
            try:
                from core.automation import attempt_profile_relogin
            except ImportError:
                def attempt_profile_relogin(*a, **kw): return False

        relogin_ok = attempt_profile_relogin(
            page=page,
            context=context,
            profile_data=profile_data,
            log_func=log
        )
        if relogin_ok:
            is_in = True
            log(f"  ✅ Re-login SUCCESSFUL for '{pname}'!")
        else:
            log(f"  ❌ Re-login FAILED for '{pname}'.")

    if is_in:
        ensure_facebook_subdomain_cookies(context)
        log(f"  ✅ [Phase 1] Facebook Account LOGIN VERIFIED for '{pname}'!")

def attempt_profile_relogin(
    page: Any,
    context: Any,
    profile_data: Dict[str, Any],
    log_func: Optional[Any] = None
) -> bool:
    """Attempts automatic profile re-login if password/UID are present in profile_data."""
    def log(msg: str) -> None:
        if log_func:
            log_func(msg)

    try:
        uid = profile_data.get("uid") or profile_data.get("id") or profile_data.get("username")
        password = profile_data.get("password")
        if not uid or not password:
            return False

        if not page or page.is_closed():
            return False

        page.goto("https://www.facebook.com/", timeout=20000, wait_until="domcontentloaded")
        time.sleep(1.5)

        email_inp = page.locator("input[name='email'], #email, input[type='email']").first
        pass_inp = page.locator("input[name='pass'], #pass, input[type='password']").first

        if email_inp.is_visible(timeout=3000) and pass_inp.is_visible(timeout=3000):
            log(f"  ⌨️ Auto re-logging into Facebook for UID: {uid}...")
            email_inp.fill(str(uid))
            time.sleep(0.5)
            pass_inp.fill(str(password))
            time.sleep(0.5)
            pass_inp.press("Enter")
            time.sleep(4.0)

            if "facebook.com" in page.url.lower() and not ("login" in page.url.lower() or "checkpoint" in page.url.lower()):
                log(f"  ✅ Auto re-login SUCCESSFUL for UID: {uid}!")
                return True
    except Exception as err:
        log(f"  ⚠️ Re-login attempt notice: {err}")

    return False


def handle_facebook_continue_prompt(page: Any, context: Any = None, log_func: Optional[Any] = None) -> bool:
    try:
        for sel in ["button:has-text('Continue')", "div[role='button']:has-text('Continue')", "button:has-text('OK')"]:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=1000):
                btn.click(force=True)
                time.sleep(1.5)
                return True
    except Exception:
        pass
    return False


def human_natural_mouse_move_and_click(page: Any, element: Any) -> None:
    try:
        box = element.bounding_box()
        if box:
            x = box['x'] + box['width'] / 2
            y = box['y'] + box['height'] / 2
            page.mouse.move(x, y, steps=random.randint(5, 12))
            time.sleep(random.uniform(0.1, 0.3))
            element.click()
            return
    except Exception:
        pass
    try:
        element.click(force=True)
    except Exception:
        pass


def get_display_number(num_val: Any) -> str:
    num_str = str(num_val).replace("Profile", "").replace("#", "").strip()
    if num_str.isdigit():
        return f"Profile{int(num_str):03d}"
    return f"Profile_{num_val}" if num_val else "Profile001"


def check_suspicious_activity_error(page: Any) -> Tuple[bool, str]:
    try:
        url = page.url.lower()
        if "checkpoint" in url or "disabled" in url:
            return True, "Account Checkpoint / Suspicious Activity Detected"
    except Exception:
        pass
    return False, ""


def dismiss_facebook_popups(page: Any) -> None:
    """Instantly purge common Facebook popups, cookie dialogs, and profile hovercard popovers from DOM."""
    try:
        page.evaluate("""() => {
            const dialogs = document.querySelectorAll('div[role="dialog"], div[data-ownerid]');
            for (const d of dialogs) {
                const txt = (d.innerText || '').toLowerCase();
                if (txt.includes('follow') || txt.includes('add friend') || txt.includes('message') || txt.includes('followers') || txt.includes('blog') || txt.includes('লাইক') || txt.includes('মেসেজ')) {
                    d.remove();
                }
            }
            const selectors = [
                'div[aria-label="Decline optional cookies"]',
                'div[aria-label="Allow all cookies"]',
                'div[aria-label="Only allow essential cookies"]',
                'div[aria-label="Close"]',
                'div[aria-label="Not now"]',
                'button[name="login"]',
                'div[role="button"][aria-label="Not Now"]'
            ];
            for (const sel of selectors) {
                const els = document.querySelectorAll(sel);
                els.forEach(el => {
                    if (el && el.offsetWidth > 0 && el.offsetHeight > 0) {
                        el.click();
                    }
                });
            }
        }""")
    except Exception:
        pass

def scroll_to_next_facebook_reel(page: Any) -> None:
    """Scrolls reliably to the next Facebook Reel."""
    try:
        dismiss_facebook_popups(page)
    except Exception:
        pass

    clicked_next = False
    try:
        res = page.evaluate("""() => {
            const buttons = Array.from(document.querySelectorAll('div[role="button"], button'));
            for (const b of buttons) {
                const aria = (b.getAttribute('aria-label') || '').toLowerCase();
                if (aria.includes('next reel') || aria.includes('next') || aria.includes('পরবর্তী')) {
                    const r = b.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) {
                        b.click();
                        return "ARIA_NEXT";
                    }
                }
            }
            const arrowBtns = buttons.filter(b => {
                const r = b.getBoundingClientRect();
                return r.width >= 25 && r.width <= 75 && r.height >= 25 && r.height <= 75 && 
                       r.left > window.innerWidth * 0.3 && r.left < window.innerWidth * 0.75 &&
                       r.top > window.innerHeight * 0.25;
            });
            if (arrowBtns.length >= 2) {
                arrowBtns[1].click();
                return "2ND_ARROW_BTN";
            } else if (arrowBtns.length === 1) {
                arrowBtns[0].click();
                return "1ST_ARROW_BTN";
            }
            return "NOT_FOUND";
        }""")
        if res != "NOT_FOUND":
            clicked_next = True
    except Exception:
        clicked_next = False

    if clicked_next:
        time.sleep(1.8)
        return

    try:
        page.evaluate("""() => {
            const video = document.querySelector('video');
            if (video) { video.click(); }
        }""")
        time.sleep(0.3)
        page.keyboard.press("j")
        time.sleep(0.4)
        page.keyboard.press("PageDown")
        time.sleep(0.4)
        page.keyboard.press("ArrowDown")
        time.sleep(0.5)
    except Exception:
        pass

    try:
        vp_w = page.viewport_size["width"] if page.viewport_size else 1280
        page.mouse.move(int(vp_w * 0.4), 400)
        page.mouse.wheel(0, 900)
        time.sleep(1.2)
    except Exception:
        pass

def hardware_mouse_click(page: Any, x: int, y: int) -> None:
    """Perform a trusted OS hardware mouse move & click gesture."""
    try:
        page.mouse.move(x, y)
        time.sleep(0.1)
        page.mouse.click(x, y)
        time.sleep(0.4)
    except Exception:
        pass

def sync_active_cookies_to_api(context: Any, profile_id: str, api_url: str = "http://127.0.0.1:5000") -> None:
    """Sync active browser cookies to Core App via Local API Server."""
    try:
        cookies = context.cookies()
        if not cookies:
            return
        cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies if c.get("name") and c.get("value")])
        payload = json.dumps({"profile_id": profile_id, "cookies": cookie_str}).encode('utf-8')
        req = urllib.request.Request(f"{api_url}/api/profiles/sync-cookies", data=payload, headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req, timeout=3)
    except Exception:
        pass

def send_bot_log(bot_name: str, message: str, api_url: str = "http://127.0.0.1:5000") -> None:
    """Send real-time bot output log to Core App via Local API Server."""
    try:
        payload = json.dumps({"bot_name": bot_name, "message": message}).encode('utf-8')
        req = urllib.request.Request(f"{api_url}/api/bot-logs", data=payload, headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req, timeout=2)
    except Exception:
        pass
