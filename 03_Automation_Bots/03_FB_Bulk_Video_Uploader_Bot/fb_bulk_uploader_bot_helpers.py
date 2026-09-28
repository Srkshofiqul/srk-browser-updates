# -*- coding: utf-8 -*-
"""
Helper utilities for Facebook Bulk Video / Reel Uploader Bot:
- Native Portable Chromium & srkBrowser Profile directory resolution
- Color theme badge & extension injector
- Real-time Facebook login verification & 2FA auto re-login
- Profile number parsing & Group filtering
- Video folder scanning & metadata pairing
- Text document loading (.txt)
- Report generation (CSV)
- Anti-detect human interaction simulation
"""

import os
import sys
import re
import csv
import time
import json
import random
import string
import struct
import hmac
import hashlib
import base64
import threading
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional, Callable
import requests

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False


def ensure_core_paths():
    """Ensure core software paths are in sys.path."""
    current_dir = Path(__file__).resolve().parent
    app_root = current_dir.parent.parent
    for p in [app_root, app_root / "01_Main_Software", app_root / "01_Main_Software" / "core"]:
        if p.exists() and str(p) not in sys.path:
            sys.path.insert(0, str(p))

ensure_core_paths()


def get_app_root_dir() -> Path:
    """Resolve the root folder of the modular app."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent.resolve()
    return Path(__file__).resolve().parent.parent.parent


def get_chrome_executable_path() -> Optional[str]:
    """Finds srkBrowser's bundled Portable Chromium executable."""
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
        app_root / "01_Main_Software" / "chromium" / "chrome-win" / "chrome.exe",
        app_root / "01_Main_Software" / "dist" / "srkBrowser" / "_internal" / "chromium" / "chrome.exe",
        app_root / "01_Main_Software" / "core" / "chrome" / "chrome.exe",
        app_root / "chrome" / "chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "BrowserProfileManager" / "chromium" / "chrome.exe",
        Path(os.environ.get("APPDATA", "")) / "BrowserProfileManager" / "chromium" / "chrome.exe",
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return str(c.resolve())

    # Standard system fallbacks
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


def resolve_user_data_dir(profile_data: Dict[str, Any], profile_mgr: Optional[Any] = None) -> str:
    """Smart resolution of the exact profile folder for srkBrowser with full login cookies."""
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

    for base in [
        app_root / "01_Main_Software" / "core" / "profiles" / "users",
        app_root / "profiles" / "users",
        Path(os.environ.get("APPDATA", "")) / "BrowserProfileManager" / "profiles" / "users"
    ]:
        if base.exists() and pnum:
            for u_folder in base.iterdir():
                if u_folder.is_dir():
                    cand = u_folder / pnum
                    if cand.exists() and cand.is_dir():
                        return str(cand.resolve())

    # 4. Fallback search in standard profiles directories
    for profiles_base in [
        app_root / "01_Main_Software" / "core" / "profiles",
        app_root / "profiles",
        Path(os.environ.get("APPDATA", "")) / "BrowserProfileManager" / "profiles"
    ]:
        if not profiles_base.exists():
            continue
        clean_digits = re.sub(r"\D", "", pnum)
        candidates = [pnum]
        if clean_digits:
            n_val = int(clean_digits)
            candidates.extend([f"Profile{n_val:03d}", f"Profile{n_val}", str(n_val)])

        for cand in candidates:
            p_dir = profiles_base / cand
            if p_dir.exists() and p_dir.is_dir():
                return str(p_dir.resolve())

    fallback = Path(os.environ.get("APPDATA", "")) / "BrowserProfileManager" / "profiles" / (pnum or "Profile001")
    fallback.mkdir(parents=True, exist_ok=True)
    return str(fallback.resolve())


def get_2fa_totp_code(secret_key: str) -> Optional[str]:
    """Generates standard 6-digit TOTP code using RFC 6238 HMAC-SHA1 algorithm with 2fa.live fallback."""
    if not secret_key:
        return None
    cleaned_key = re.sub(r'[\s\-]', '', str(secret_key)).strip().upper()
    try:
        pad_len = (8 - (len(cleaned_key) % 8)) % 8
        padded_key = cleaned_key + ('=' * pad_len)
        key_bytes = base64.b32decode(padded_key, casefold=True)
        counter = int(time.time() // 30)
        counter_bytes = struct.pack(">Q", counter)
        mac = hmac.new(key_bytes, counter_bytes, hashlib.sha1).digest()
        offset = mac[-1] & 0x0F
        code_int = struct.unpack(">I", mac[offset:offset+4])[0] & 0x7FFFFFFF
        totp = f"{code_int % 1000000:06d}"
        if len(totp) == 6 and totp.isdigit():
            return totp
    except Exception:
        pass

    # Method 2: Fallback 2fa.live API
    try:
        url = f"https://2fa.live/tok/{urllib.parse.quote(cleaned_key)}"
        req = urllib.request.Request(url, headers={'User-Agent': 'srkBrowser/2.0'})
        with urllib.request.urlopen(req, timeout=6) as response:
            res_data = json.loads(response.read().decode())
            token = str(res_data.get("token", "")).strip()
            if len(token) == 6 and token.isdigit():
                return token
    except Exception:
        pass

    return None


def check_facebook_login_status(driver_or_page: Any, timeout_sec: float = 5.0) -> Tuple[bool, str]:
    """
    Checks if the active browser session is genuinely logged into Facebook and healthy (not checkpointed or locked).
    Returns: (is_healthy_login, status_code) where status_code is 'OK', 'CHECKPOINT', or 'LOGGED_OUT'.
    """
    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        try:
            # Playwright Page instance
            if hasattr(driver_or_page, "evaluate"):
                curr_url = (driver_or_page.url or "").lower()
                
                # Check for explicit Checkpoint / Suspend URLs
                if any(k in curr_url for k in ("/checkpoint/", "/identity/", "/two_step_verification/", "/disabled/", "/help/contact/", "/recover/", "/auth_platform/", "/afad/")):
                    return False, "CHECKPOINT"

                # Check for Checkpoint DOM markers
                is_checkpoint = driver_or_page.evaluate("""() => {
                    const text = (document.body?.innerText || '').toLowerCase();
                    return (
                        text.includes("confirm you're human") ||
                        text.includes("confirm your identity") ||
                        text.includes("your account has been suspended") ||
                        text.includes("help us confirm it's you") ||
                        text.includes("account disabled") ||
                        text.includes("check your other device") ||
                        text.includes("waiting for approval") ||
                        text.includes("open the notification on your other device") ||
                        text.includes("approve from another device") ||
                        text.includes("আপনাকে যাচাই করুন") ||
                        text.includes("আমরা সন্দেহজনক কার্যকলাপ") ||
                        text.includes("অন্য ডিভাইস")
                    );
                }""")
                if is_checkpoint:
                    return False, "CHECKPOINT"

                has_login_form = driver_or_page.evaluate("""() => {
                    return !!(
                        document.querySelector('input[name="email"]') && 
                        document.querySelector('input[name="pass"]')
                    );
                }""")
                if has_login_form or "login" in curr_url:
                    return False, "LOGGED_OUT"

                has_continue_screen = driver_or_page.evaluate("""() => {
                    const text = (document.body?.innerText || '');
                    const hasBtn = Array.from(document.querySelectorAll("div[role='button'], button, a")).some(b => {
                        const t = (b.innerText || '').trim();
                        return t === 'Continue' || t.startsWith('Continue as') || t.includes('Use another profile') || t.includes('Log In As') || t.includes('চালিয়ে যান') || t.includes('চালিয়ে যান');
                    });
                    const hasPassModal = !!document.querySelector("div[role='dialog'] input[type='password'], input#pass, input[name='pass']");
                    const hasAvatar = !!document.querySelector("img[alt*='profile'], img[src*='profile'], div[aria-label*='Profile photo'], div._aa_");
                    return hasBtn || (hasPassModal && hasAvatar) || text.includes("Use another profile") || text.includes("Create new account");
                }""")
                if has_continue_screen:
                    return False, "LOGGED_OUT"

                try:
                    cookies = driver_or_page.context.cookies()
                    c_user = any(c.get("name") == "c_user" and c.get("value") for c in cookies)
                except Exception:
                    c_user = False

                has_feed = driver_or_page.evaluate("""() => {
                    return !!(
                        document.querySelector('[role="feed"]') || 
                        document.querySelector('[role="navigation"]') || 
                        document.querySelector('input[placeholder*="Search"]') ||
                        document.querySelector('input[placeholder*="সার্চ"]') ||
                        document.querySelector('[aria-label*="Your profile"]') ||
                        document.querySelector('[aria-label*="আপনার প্রোফাইল"]') ||
                        document.querySelector('[data-pagelet="LeftRail"]') ||
                        document.querySelector('div[aria-label*="Stories"]') ||
                        document.querySelector('div[aria-label*="Create a post"]')
                    );
                }""")
                if (c_user or has_feed) and not has_login_form and not has_continue_screen:
                    return True, "OK"

            # Selenium WebDriver instance fallback
            elif hasattr(driver_or_page, "execute_script"):
                curr_url = (driver_or_page.current_url or "").lower()
                if any(k in curr_url for k in ("/checkpoint/", "/identity/", "/two_step_verification/", "/disabled/", "/help/contact/", "/recover/", "/auth_platform/", "/afad/")):
                    return False, "CHECKPOINT"
                has_continue = driver_or_page.execute_script("""
                    return Array.from(document.querySelectorAll("div[role='button'], button, a")).some(b => {
                        const t = (b.innerText || '').trim();
                        return t === 'Continue' || t.startsWith('Continue as') || t.includes('Use another profile') || t.includes('Log In As') || t.includes('চালিয়ে যান') || t.includes('চালিয়ে যান');
                    });
                """)
                if has_continue:
                    return False, "LOGGED_OUT"
                has_feed = driver_or_page.execute_script("""
                    return !!(document.querySelector('[role="feed"]') || document.querySelector('[role="navigation"]') || document.querySelector('[data-pagelet="LeftRail"]'));
                """)
                if has_feed:
                    return True, "OK"
        except Exception:
            pass
        time.sleep(0.5)

    return False, "LOGGED_OUT"


def dismiss_facebook_popup_notices(page: Any) -> None:
    """Dismisses Facebook popups, Remember password dialogs, and cookie banners."""
    dismiss_selectors = [
        "div[role='button']:has-text('Not now')",
        "div[role='button']:has-text('Not Now')",
        "div[role='button']:has-text('এখন নয়')",
        "button:has-text('Not now')",
        "button:has-text('Not Now')",
        "button:has-text('OK')",
        "button:has-text('Ok')",
        "div[aria-label='Close']",
        "div[aria-label='বন্ধ করুন']",
        "button[data-cookiebanner='accept_button']",
        "button:has-text('Allow all cookies')",
        "button:has-text('Decline optional cookies')"
    ]
    for sel in dismiss_selectors:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=350):
                btn.click()
                time.sleep(0.2)
        except Exception:
            pass


def is_continue_button_present(page: Any) -> bool:
    """Checks if the Facebook Continue / Account Chooser button is visible on page."""
    for sel in [
        "div[role='button']:has-text('Continue')",
        "button:has-text('Continue')",
        "div[role='button']:has-text('চালিয়ে যান')",
        "button:has-text('চালিয়ে যান')",
        "div[role='button']:has-text('চালিয়ে যান')",
        "button:has-text('চালিয়ে যান')",
        "div[role='button']:has-text('Continuer')",
        "button[value='Continue']",
        "a[role='button']:has-text('Continue')"
    ]:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=600):
                return True
        except Exception:
            pass
    return False


def is_device_approval_screen(page: Any) -> bool:
    """
    Checks if Facebook is prompting 'Check your other device' / tap number on another device.
    This is an unrecoverable on-device challenge that requires physical owner action.
    """
    try:
        curr_url = (page.url or "").lower()
        if "auth_platform" in curr_url or "afad" in curr_url:
            return True
        is_approval = page.evaluate("""() => {
            const text = (document.body?.innerText || '').toLowerCase();
            return (
                text.includes("check your other device") ||
                text.includes("open the notification on your other device") ||
                text.includes("waiting for approval") ||
                text.includes("approve from another device") ||
                (text.includes("tap ") && text.includes("to verify it's you")) ||
                (text.includes("try another way") && text.includes("approval")) ||
                text.includes("অন্য ডিভাইস") ||
                text.includes("অনুমোদনের জন্য অপেক্ষা")
            );
        }""")
        return bool(is_approval)
    except Exception:
        return False


def clean_uid_str(val: Any) -> str:
    """Strip trailing .0, spaces, and formatting from UID/username strings."""
    s = str(val or "").strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def kill_profile_chrome_process(user_data_dir: str) -> None:
    """Forcefully terminates any Chrome / Chromium process for a given profile folder."""
    if not user_data_dir:
        return
    folder_name = Path(user_data_dir).name
    if not folder_name:
        return

    # Method 1: Instant psutil termination
    try:
        import psutil
        for p in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmd = " ".join(p.info.get('cmdline') or [])
                if folder_name in cmd:
                    p.kill()
            except Exception:
                pass
    except Exception:
        pass

    # Method 2: Windows WMIC & PowerShell fallback
    if os.name == 'nt' and len(folder_name) > 1:
        try:
            cmd_wmic = f'wmic process where "name=\'chrome.exe\' and commandline like \'%%{folder_name}%%\'" call terminate'
            subprocess.run(cmd_wmic, shell=True, capture_output=True, timeout=2)
            cmd_ps = f'powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \\"Name = \'chrome.exe\' and CommandLine like \'%{folder_name}%\'\\" | Invoke-CimMethod -MethodName Terminate"'
            subprocess.run(cmd_ps, shell=True, capture_output=True, timeout=2)
        except Exception:
            pass


def check_is_meta_error_page(page: Any) -> bool:
    """Checks if the current Meta Business Suite page is displaying an error or crash page."""
    try:
        title = (page.title() or "").lower()
        if "error" in title:
            return True
        err = page.evaluate(r"""() => {
            let t = document.body ? (document.body.innerText || document.body.textContent || '') : '';
            t = t.toLowerCase();
            return t.includes("sorry, something went wrong") || 
                   t.includes("working on getting this fixed") ||
                   t.includes("page isn't available") ||
                   t.includes("link you followed may be broken");
        }""")
        return bool(err)
    except Exception:
        return False


def extract_asset_id_from_context(context: Any) -> Optional[str]:
    """Extract active Facebook Page asset_id from any open Meta Business Suite page."""
    if not context:
        return None
    for pg in context.pages:
        u = pg.url or ""
        # Check current URL for asset_id (avoid personal business_id which causes error)
        m = re.search(r'[?&]asset_id=(\d+)', u)
        if m and "business_id" not in u:
            return m.group(1)

    for pg in context.pages:
        u = (pg.url or "").lower()
        if "business.facebook.com" in u:
            try:
                aid = pg.evaluate(r"""() => {
                    let m = window.location.href.match(/[?&]asset_id=(\d+)/);
                    if (m) return m[1];
                    // Look specifically for page switcher or navigation links that represent Facebook Pages
                    let pageLink = document.querySelector('a[href*="/latest/home?asset_id="], [data-page-id]');
                    if (pageLink) {
                        let m2 = (pageLink.href || '').match(/[?&]asset_id=(\d+)/);
                        if (m2) return m2[1];
                    }
                    return null;
                }""")
                if aid:
                    return str(aid)
            except Exception:
                pass
    return None


def parse_cookie_string(cookie_str: str, default_domain: str = ".facebook.com") -> List[Dict[str, Any]]:
    """Convert raw semicolon/pipe/JSON cookie strings into Playwright cookie list."""
    if not cookie_str or not str(cookie_str).strip():
        return []

    cookies = []
    clean_str = str(cookie_str).strip()

    # Format 1: JSON array string [{"name": "c_user", "value": "..."}, ...]
    if clean_str.startswith("[") and clean_str.endswith("]"):
        try:
            json_arr = json.loads(clean_str)
            for c in json_arr:
                if isinstance(c, dict) and "name" in c and "value" in c:
                    ck = {
                        "name": str(c["name"]).strip(),
                        "value": str(c["value"]).strip(),
                        "domain": c.get("domain", default_domain),
                        "path": c.get("path", "/")
                    }
                    cookies.append(ck)
            if cookies:
                return cookies
        except Exception:
            pass

    # Format 2: Semicolon or pipe separated string: "c_user=123; xs=abc; datr=xyz" or "c_user=123|xs=abc"
    pairs = [p.strip() for p in clean_str.split(";") if p.strip()]
    if len(pairs) == 1 and "|" in pairs[0] and "=" not in pairs[0]:
        pairs = pairs[0].split("|")
    elif len(pairs) == 1 and "|" in pairs[0]:
        pairs = [p.strip() for p in pairs[0].split("|") if p.strip()]

    for pair in pairs:
        if "=" in pair:
            parts = pair.split("=", 1)
            name = parts[0].strip()
            val = parts[1].strip()
            if name and val:
                cookies.append({
                    "name": name,
                    "value": val,
                    "domain": default_domain,
                    "path": "/"
                })

    return cookies


def save_fresh_cookies_to_profile(context: Any, profile_data: Dict[str, Any], user_data_dir: str = "", profile_mgr: Optional[Any] = None) -> None:
    """Extracts fresh cookies from context and persists them into profile_data, profile.json, and software database."""
    if not context:
        return
    try:
        fresh_cookies = context.cookies()
        if not fresh_cookies:
            return

        cookie_pairs = []
        for ck in fresh_cookies:
            c_name = ck.get("name", "")
            c_val = ck.get("value", "")
            c_domain = ck.get("domain", "")
            if "facebook.com" in c_domain and c_name and c_val:
                cookie_pairs.append(f"{c_name}={c_val}")

        if cookie_pairs:
            cookie_str = "; ".join(cookie_pairs)
            profile_data["cookie"] = cookie_str
            profile_data["cookies"] = cookie_str

            # Also persist to profile.json on disk if directory known
            if user_data_dir:
                p_file = Path(user_data_dir) / "profile.json"
                if p_file.exists():
                    try:
                        disk_p = {}
                        with open(p_file, "r", encoding="utf-8") as f:
                            disk_p = json.load(f)
                        if isinstance(disk_p, dict):
                            disk_p["cookie"] = cookie_str
                            disk_p["cookies"] = cookie_str
                            with open(p_file, "w", encoding="utf-8") as f:
                                json.dump(disk_p, f, indent=2)
                    except Exception:
                        pass

            # Update software database via profile_mgr if available
            profile_id = profile_data.get("id") or str(profile_data.get("number", "1"))
            if profile_mgr and hasattr(profile_mgr, "update_profile"):
                try:
                    profile_mgr.update_profile(
                        profile_id,
                        cookie=cookie_str,
                        start_url="https://www.facebook.com"
                    )
                except Exception:
                    pass

            # Synchronize to Chromium profile files & injector extension
            try:
                p_folder = None
                if profile_mgr and hasattr(profile_mgr, "get_profile_folder"):
                    p_folder = profile_mgr.get_profile_folder(profile_id)
                elif user_data_dir:
                    p_folder = Path(user_data_dir)

                if p_folder and Path(p_folder).exists():
                    try:
                        from browser import inject_cookies_to_chromium_profile, create_cookie_injector_extension
                        inject_cookies_to_chromium_profile(p_folder, cookie_str)
                        updated_p = profile_mgr.get_profile_by_id(profile_id) if profile_mgr else profile_data
                        if updated_p:
                            create_cookie_injector_extension(p_folder, updated_p)
                    except Exception:
                        pass
            except Exception:
                pass
    except Exception:
        pass


def generate_totp_2fa_code(secret_key: str) -> str:
    """Pure Python RFC-6238 TOTP Generator without external dependencies."""
    cleaned = str(secret_key).strip().replace(" ", "").replace("-", "").upper()
    if not cleaned:
        return ""
    missing_padding = len(cleaned) % 8
    if missing_padding:
        cleaned += "=" * (8 - missing_padding)
    try:
        key = base64.b32decode(cleaned)
        counter = int(time.time() // 30)
        counter_bytes = struct.pack(">Q", counter)
        mac = hmac.new(key, counter_bytes, hashlib.sha1).digest()
        offset = mac[-1] & 0x0F
        code_int = struct.unpack(">I", mac[offset:offset+4])[0] & 0x7FFFFFFF
        return f"{code_int % 1000000:06d}"
    except Exception as err:
        print(f"[FBRL TOTP ERROR]: {err}")
        return ""


get_2fa_totp_code = generate_totp_2fa_code


def human_type(locator: Any, text: str, min_delay_ms: int = 45, max_delay_ms: int = 125, clear_first: bool = False) -> None:
    """Simulates natural human typing cadence."""
    try:
        locator.click(timeout=3000)
        time.sleep(random.uniform(0.15, 0.35))
        if clear_first:
            locator.fill("")
            time.sleep(0.1)
        for ch in str(text):
            locator.type(ch, delay=random.randint(min_delay_ms, max_delay_ms))
    except Exception:
        try:
            locator.fill(str(text))
        except Exception:
            pass


def detect_facebook_tab_state(page: Any) -> Tuple[str, str]:
    """
    Detects current Facebook page state (ON_CHECKPOINT, 2FA_REQUIRED, CONTINUE_SCREEN, LOGIN_FORM_READY, LOGGED_IN).
    Strict Priority:
      1. Checkpoint / Suspended Account Check
      2. 2FA Two-Factor Challenge Check
      3. Continue / Account Switcher Screen Check (e.g. "Continue as", [Continue] button, avatar)
      4. Standard Login Form Check (email/pass fields)
      5. Genuinely Logged-in Home Feed Check (requires actual feed/post/profile elements, NEVER generic role='main')
    """
    try:
        url = (page.url or "").lower()

        # 1. Checkpoint / Security Lock
        if any(k in url for k in ("/checkpoint/", "/identity/", "/two_step_verification/", "/disabled/", "/help/contact/", "/recover/", "/auth_platform/", "/afad/")):
            return "ON_CHECKPOINT", "Facebook Security Checkpoint URL"

        checkpoint_selectors = [
            "div:has-text('Your account has been locked')",
            "div:has-text('Account locked')",
            "div:has-text('Help us confirm it')",
            "div:has-text('Suspicious activity detected')",
            "div:has-text('Confirm you\\'re human')",
            "div:has-text('Your account has been suspended')",
            "div#checkpointSubmitButton"
        ]
        for sel in checkpoint_selectors:
            if page.locator(sel).first.is_visible(timeout=350):
                return "ON_CHECKPOINT", "Facebook Security Checkpoint"

        # 2. 2FA Two-Factor Authentication Check
        two_fa_selectors = [
            "input[name='approvals_code']",
            "input#approvals_code",
            "input[name='code']",
            "input[id*='code']",
            "div:has-text('Two-factor authentication')",
            "div:has-text('Enter login code')",
            "div:has-text('Check your notifications on another device')"
        ]
        for sel in two_fa_selectors:
            if page.locator(sel).first.is_visible(timeout=350):
                return "2FA_REQUIRED", "Two-Factor Authentication Prompt"

        # 3. Continue / Profile Avatar Screen Check (MUST be checked BEFORE Logged-In check!)
        continue_btn = page.locator("div[role='button']:has-text('Continue'), button:has-text('Continue'), div[role='button']:has-text('Log In As'), div[role='button']:has-text('Continue as'), a:has-text('Continue'), div:has-text('Use another profile'), a:has-text('Use another profile')").first
        if continue_btn.is_visible(timeout=500):
            return "CONTINUE_SCREEN", "Continue Profile Screen Detected"

        pass_input_continue = page.locator("input#pass, input[name='pass'], input[type='password']").first
        avatar_img = page.locator("img[alt*='profile'], img[src*='profile'], div[aria-label*='Profile photo'], div._aa_").first
        if pass_input_continue.is_visible(timeout=400) and (avatar_img.is_visible(timeout=400) or continue_btn.is_visible(timeout=400)):
            return "CONTINUE_SCREEN", "Continue Password Screen with Avatar"

        # 4. Standard Login Form Ready
        email_inp = page.locator("input#email, input[name='email']").first
        if email_inp.is_visible(timeout=400):
            return "LOGIN_FORM_READY", "Standard Login Form Ready"

        if "login" in url or "recover" in url:
            return "LOGIN_FORM_READY", "Facebook Login URL"

        # 5. Genuinely Logged-in Home Feed Check
        # STRICT RULE: NEVER include generic 'div[role="main"]' as it exists on login/continue pages!
        feed_selectors = [
            "div[role='feed']",
            "div[aria-label*='Stories']",
            "div[aria-label*='Create a post']",
            "div[aria-label*='একটি পোস্ট তৈরি করুন']",
            "div[data-pagelet='LeftRail']",
            "input[placeholder*='Search Facebook']",
            "input[placeholder*='ফেসবুক সার্চ']",
            "svg[aria-label='Your profile']",
            "div[aria-label*='Account controls']",
            "a[href*='/friends/']"
        ]
        for sel in feed_selectors:
            if page.locator(sel).first.is_visible(timeout=400):
                return "LOGGED_IN", "Active Home Feed Verified"

        # Check cookies in context
        try:
            for ck in page.context.cookies():
                if ck.get("name") in ("c_user", "cuser") and str(ck.get("value", "")).isdigit():
                    if "login" not in url and "checkpoint" not in url:
                        if not continue_btn.is_visible(timeout=300):
                            return "LOGGED_IN", f"Authenticated (c_user={ck.get('value')})"
        except Exception:
            pass

        return "UNKNOWN_OR_LOADING", "Page loading or unrecognized screen"
    except Exception as err:
        return "ERROR", str(err)


def handle_2fa_challenge(
    page: Any, 
    twofa_secret: str, 
    log_func: Optional[Any] = None
) -> bool:
    """Detects and solves Facebook 2FA challenge via TOTP."""
    def log(m: str):
        if log_func:
            log_func(m)

    curr_url = (page.url or "").lower()
    body_text = ""
    try:
        body_text = (page.locator("body").inner_text(timeout=1500) or "").lower()
    except Exception:
        pass

    has_2fa = (
        any(term in curr_url for term in ["two_step_verification", "two_factor", "login_approvals"]) or
        any(term in body_text for term in ["two-factor", "two factor", "approvals_code", "enter login code", "6-digit code", "authentication code", "লগইন কোড"])
    )

    if not has_2fa:
        return False

    if not twofa_secret:
        log("⚠️ 2FA required by Facebook, but no 2FA Secret Key is saved in database!")
        return False

    log("🛡️ 2FA Checkpoint detected. Generating 6-digit TOTP code...")
    totp_code = generate_totp_2fa_code(twofa_secret)
    if not totp_code:
        log("❌ Failed to calculate TOTP code from secret key.")
        return False

    log(f"🔑 Submitting 2FA TOTP Code [{totp_code}]...")
    otp_selectors = [
        'input[name="approvals_code"]',
        'input#approvals_code',
        'input[placeholder*="Code"]',
        'input[placeholder*="code"]',
        'input[placeholder*="6-digit"]',
        'input[type="number"]',
        'input[autocomplete="one-time-code"]',
        'input[type="text"]'
    ]
    otp_filled = False
    for osel in otp_selectors:
        try:
            oinp = page.locator(osel).first
            if oinp.is_visible(timeout=1200):
                human_type(oinp, totp_code, clear_first=True)
                otp_filled = True
                break
        except Exception:
            pass

    if otp_filled:
        time.sleep(0.6)
        submit_2fa_btns = [
            '#checkpointSubmitButton',
            'button[value="Continue"]',
            'button:has-text("Continue")',
            'button:has-text("Submit")',
            'button[type="submit"]',
            'button:has-text("Confirm")',
            'button:has-text("জমা দিন")'
        ]
        s_clicked = False
        for s_sel in submit_2fa_btns:
            try:
                s_b = page.locator(s_sel).first
                if s_b.is_visible(timeout=1000):
                    s_b.click()
                    s_clicked = True
                    break
            except Exception:
                pass
        if not s_clicked:
            page.keyboard.press("Enter")

        time.sleep(4.0)
        dismiss_facebook_popup_notices(page)

        # Handle "Trust this device" prompt
        trust_btns = [
            "button:has-text('Trust this device')",
            "button:has-text('Trust')",
            "button:has-text('Always confirm it’s me')",
            "button:has-text('Always confirm')",
            "div[role='button']:has-text('Trust')",
            "button:has-text('Continue')"
        ]
        for tsel in trust_btns:
            try:
                tb = page.locator(tsel).first
                if tb.is_visible(timeout=1500):
                    tb.click()
                    time.sleep(2.0)
                    break
            except Exception:
                pass
        return True

    return False


def handle_facebook_continue_and_login(
    page: Any, 
    password: str, 
    twofa_secret: str = "",
    log_func: Optional[Any] = None,
    popup_wait_sec: float = 16.0,
    auth_wait_sec: float = 15.0
) -> Tuple[bool, str]:
    """
    Handles Facebook's Remembered Account / Account Chooser screen:
    1. Detects and clicks the 'Continue' (or 'Continue as...') button.
    2. Patiently waits for the password popup/modal to appear (handles Facebook lag without reloading).
    3. Enters the password and submits.
    4. Patiently waits 8-10 seconds for authentication response (does NOT reload or navigate away!).
    5. Automatically solves 2FA if prompted.
    6. Returns (is_authenticated, message).
    """
    def log(m: str):
        if log_func:
            log_func(m)

    continue_selectors = [
        "div[role='button']:has-text('Continue')",
        "button:has-text('Continue')",
        "div[role='button']:has-text('চালিয়ে যান')",
        "button:has-text('চালিয়ে যান')",
        "div[role='button']:has-text('চালিয়ে যান')",
        "button:has-text('চালিয়ে যান')",
        "div[role='button']:has-text('Continuer')",
        "button:has-text('Continuer')",
        "button[value='Continue']",
        "div[aria-label*='Continue']",
        "div[aria-label*='চালিয়ে যান']",
        "a[role='button']:has-text('Continue')"
    ]

    continue_btn = None
    for sel in continue_selectors:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=800):
                continue_btn = loc
                break
        except Exception:
            pass

    direct_pass = None
    for p_sel in ["div[role='dialog'] input[type='password']", "input[type='password']", "input#pass", "input[name='pass']"]:
        try:
            p_loc = page.locator(p_sel).first
            if p_loc.is_visible(timeout=400):
                direct_pass = p_loc
                break
        except Exception:
            pass

    if not direct_pass:
        if not continue_btn:
            try:
                clicked = page.evaluate("""() => {
                    const btns = Array.from(document.querySelectorAll("div[role='button'], button, a"));
                    for (const b of btns) {
                        const t = (b.innerText || '').trim();
                        if (t === 'Continue' || t.startsWith('Continue as') || t.includes('Log In As') || t.includes('চালিয়ে যান') || t.includes('চালিয়ে যান')) {
                            b.click();
                            return true;
                        }
                    }
                    return false;
                }""")
                if not clicked:
                    return False, "Continue button not visible"
            except Exception:
                return False, "Continue button not visible"
        else:
            log("👉 [CONTINUE DETECTED] Facebook remembered profile found. Clicking 'Continue'...")
            try:
                continue_btn.click()
            except Exception:
                try:
                    page.evaluate("(sel) => document.querySelector(sel)?.click()", "div[role='button']:has-text('Continue'), button:has-text('Continue')")
                except Exception:
                    pass

        # Wait 5-7 seconds for password popup to render as requested by user
        log("⏳ Clicked 'Continue'. Waiting 5-7 seconds for password popup to render...")
        time.sleep(5.5)

    password_selectors = [
        "div[role='dialog'] input[type='password']",
        "div[role='dialog'] input[name='pass']",
        "input[type='password']",
        "input[name='pass']",
        "input#pass",
        "input[placeholder*='Password']",
        "input[placeholder*='password']",
        "input[placeholder*='পাসওয়ার্ড']",
        "input[aria-label*='Password']",
        "input[aria-label*='পাসওয়ার্ড']"
    ]

    pass_input = None
    # Check if already authenticated or find password field
    is_in, _ = check_facebook_login_status(page, timeout_sec=0.5)
    if is_in:
        log("🎉 Instantly authenticated after clicking Continue!")
        return True, "Authenticated via Continue"

    start_find = time.time()
    while time.time() - start_find < 6.0:
        for p_sel in password_selectors:
            try:
                p_loc = page.locator(p_sel).first
                if p_loc.is_visible(timeout=400):
                    pass_input = p_loc
                    break
            except Exception:
                pass
        if pass_input:
            break
        time.sleep(0.5)

    if not pass_input:
        # Check one more time if logged in directly
        is_in, _ = check_facebook_login_status(page, timeout_sec=1.5)
        if is_in:
            log("🎉 Authenticated after Continue!")
            return True, "Authenticated via Continue"
        return False, "Password popup did not appear"

    if not password:
        return False, "Password popup appeared, but no password found in profile database"

    log("🔑 [PASSWORD POPUP] Password popup detected! Entering password...")
    try:
        time.sleep(0.6)
        pass_input.click()
        time.sleep(0.4)
        pass_input.fill(str(password))
        time.sleep(0.8)

        # Submit password
        submit_selectors = [
            "div[role='dialog'] button[type='submit']",
            "div[role='dialog'] button:has-text('Log In')",
            "div[role='dialog'] button:has-text('Log in')",
            "div[role='dialog'] button:has-text('লগ ইন')",
            "div[role='dialog'] div[role='button']:has-text('Log In')",
            "div[role='dialog'] div[role='button']:has-text('Log in')",
            "div[role='dialog'] div[role='button']:has-text('লগ ইন')",
            "button[name='login']",
            "button[type='submit']",
            "div[role='button']:has-text('Log In')",
            "div[role='button']:has-text('Log in')"
        ]
        clicked_sub = False
        for s_sel in submit_selectors:
            try:
                s_loc = page.locator(s_sel).first
                if s_loc.is_visible(timeout=800):
                    s_loc.click()
                    clicked_sub = True
                    break
            except Exception:
                pass
        if not clicked_sub:
            page.keyboard.press("Enter")

        # Wait solid 8-10 seconds for next page to load with NO actions in between!
        log("⏳ Password submitted. Waiting 8-10 seconds for next page to load (no actions in between)...")
        time.sleep(8.5)

        dismiss_facebook_popup_notices(page)

        # 0. Check for unrecoverable Device Approval ("Check your other device" / Tap number)
        if is_device_approval_screen(page):
            log("⚠️ [DEVICE APPROVAL DETECTED] Facebook requested physical device approval ('Check your other device'). This account cannot be automated. Exiting immediately...")
            return False, "Device Approval Required (Check other device)"

        # 1. Check if logged in
        is_in, _ = check_facebook_login_status(page, timeout_sec=1.5)
        if is_in:
            log("🎉 Facebook Login successfully verified via Continue popup!")
            return True, "Login successful"

        # 2. Check for 2FA challenge
        if handle_2fa_challenge(page, twofa_secret, log_func):
            time.sleep(3.0)
            is_in, _ = check_facebook_login_status(page, timeout_sec=3.0)
            if is_in:
                log("🎉 Facebook Login successfully verified after 2FA!")
                return True, "Login successful"

        # 3. Check for errors
        body_text = ""
        try:
            body_text = (page.locator("body").inner_text(timeout=1000) or "").lower()
        except Exception:
            pass
        if "incorrect password" in body_text or "wrong password" in body_text or "ভুল পাসওয়ার্ড" in body_text:
            log("❌ Facebook reported: Incorrect password.")
            return False, "Incorrect Password"
        if "suspended" in body_text or "account is locked" in body_text or "account was locked" in body_text:
            log("🔴 Facebook reported: Account Locked / Suspended.")
            return False, "Account Checkpoint / Locked"

        # 4. Final verification
        is_in, status_c = check_facebook_login_status(page, timeout_sec=3.0)
        if is_in:
            log("🎉 Facebook Login successfully verified via Continue popup!")
            return True, "Login successful"

        return False, f"Continue login did not complete ({status_c})"

    except Exception as e_sub:
        log(f"⚠️ Exception in continue login flow: {e_sub}")
        return False, f"Continue exception: {str(e_sub)}"


def auto_relogin_facebook(
    page: Any,
    context: Optional[Any] = None,
    profile_data: Optional[Dict[str, Any]] = None,
    profile_mgr: Optional[Any] = None,
    user_data_dir: str = "",
    log_func: Optional[Any] = None,
    timeout_sec: float = 30.0,
    uid: str = "",
    password: str = "",
    twofa_secret: str = "",
    **kwargs
) -> Tuple[bool, str]:
    """
    1-Click FB Auto Re-login (FBRL engine):
    - Connects to current live page
    - Inspects active tab state (CONTINUE_SCREEN, 2FA, LOGIN_FORM, etc.)
    - Handles Continue Screen directly (types password, clicks Login, no unnecessary reloads)
    - Automatically solves 2FA TOTP challenges
    - Injects session cookies if standard login form or new tab
    - Verifies genuine LOGGED_IN state with c_user
    - Persists fresh cookies to database & profile files
    """
    def log(m: str):
        if log_func:
            log_func(m)

    pdata = profile_data or {}
    pname = pdata.get("name", "Profile")
    profile_id = pdata.get("id") or str(pdata.get("number", "1"))

    # Extract credentials
    email = str(uid or pdata.get("fb_uid") or pdata.get("email") or pdata.get("uid") or pdata.get("username") or "").strip()
    if not email and "fb_" in str(pname).lower():
        m = re.search(r"\d{10,20}", str(pname))
        if m:
            email = m.group(0)
    password = str(password or pdata.get("fb_pass") or pdata.get("password") or pdata.get("pass") or "").strip()
    two_factor = str(twofa_secret or pdata.get("fb_2fa") or pdata.get("2fa_secret") or pdata.get("two_factor") or pdata.get("secret_2fa") or pdata.get("2fa") or "").strip()
    cookies_raw = pdata.get("cookies") or pdata.get("fb_cookie") or pdata.get("cookie") or ""

    # Parse credentials from notes if present
    notes = str(pdata.get("notes") or "").strip()
    if notes:
        m_uid = re.search(r'(?:uid|fb\s*uid|id|user):\s*([0-9a-zA-Z\._\-]+)', notes, re.IGNORECASE)
        m_pwd = re.search(r'(?:pass|password|pwd):\s*([^\s\|]+)', notes, re.IGNORECASE)
        m_2fa = re.search(r'(?:2fa|totp|secret):\s*([0-9a-zA-Z\s]+)', notes, re.IGNORECASE)
        if m_uid and not email: email = m_uid.group(1).strip()
        if m_pwd and not password: password = m_pwd.group(1).strip()
        if m_2fa and not two_factor: two_factor = m_2fa.group(1).strip()

        if "|" in notes and (not email or not password):
            parts = [p.strip() for p in notes.split("|")]
            if len(parts) >= 2:
                if not email: email = parts[0]
                if not password: password = parts[1]
                if len(parts) >= 3 and not two_factor: two_factor = parts[2]
                if len(parts) >= 4 and not cookies_raw: cookies_raw = parts[3]

    log(f"🔑 [AUTO RE-LOGIN] Authenticating profile '{pname}'...")

    try:
        # Check current tab state
        current_state, state_desc = detect_facebook_tab_state(page)
        log(f"  🔍 Tab State: [{current_state}] - {state_desc}")

        if current_state == "LOGGED_IN":
            return True, "Already logged in"

        # -------------------------------------------------------------
        # CASE A: CONTINUE SCREEN ALREADY VISIBLE
        # DO NOT reload! DO NOT inject cookies! Directly type password!
        # -------------------------------------------------------------
        if current_state == "CONTINUE_SCREEN":
            log("  🎯 Continue Screen detected! Initiating 1-Click Continue Re-login...")
            ok, msg = handle_facebook_continue_and_login(
                page=page,
                password=password,
                twofa_secret=two_factor,
                log_func=log
            )
            if ok:
                save_fresh_cookies_to_profile(context or getattr(page, 'context', None), pdata, user_data_dir, profile_mgr=profile_mgr)
                return True, f"Re-login SUCCESSFUL for [{pname}] via Continue Screen!"
            else:
                return False, f"Continue re-login failed: {msg}"

        # -------------------------------------------------------------
        # CASE B: NOT ON FB OR LOGIN FORM
        # -------------------------------------------------------------
        elif current_state not in ("LOGGED_IN", "2FA_REQUIRED"):
            curr_url = (page.url or "").lower()
            if "facebook.com" not in curr_url or "login" in curr_url or current_state == "LOGIN_FORM_READY":
                if cookies_raw and context:
                    cks = parse_cookie_string(str(cookies_raw))
                    if cks:
                        log(f"  🍪 Injecting {len(cks)} saved session cookie(s)...")
                        try:
                            context.add_cookies(cks)
                        except Exception:
                            pass

                log("  🌐 Loading facebook.com...")
                try:
                    page.goto("https://www.facebook.com/", timeout=25000, wait_until="domcontentloaded")
                except Exception:
                    pass
                time.sleep(2.5)

                current_state, state_desc = detect_facebook_tab_state(page)
                log(f"  🔍 Post-Navigation State: [{current_state}] - {state_desc}")

                if current_state == "CONTINUE_SCREEN":
                    log("  🎯 Continue Screen detected post-navigation! Initiating 1-Click Continue Re-login...")
                    ok, msg = handle_facebook_continue_and_login(
                        page=page,
                        password=password,
                        twofa_secret=two_factor,
                        log_func=log
                    )
                    if ok:
                        save_fresh_cookies_to_profile(context or getattr(page, 'context', None), pdata, user_data_dir, profile_mgr=profile_mgr)
                        return True, f"Re-login SUCCESSFUL for [{pname}] via Continue Screen!"
                    else:
                        return False, f"Continue re-login failed: {msg}"

                elif current_state == "LOGIN_FORM_READY" and email and password:
                    log(f"  🔑 Entering UID [{email[:15]}...] and Password...")
                    e_inp = page.locator("input#email, input[name='email']").first
                    if e_inp.is_visible(timeout=1500):
                        human_type(e_inp, email, clear_first=True)
                    time.sleep(0.4)
                    p_inp = page.locator("input#pass, input[name='pass'], input[type='password']").first
                    if p_inp.is_visible(timeout=1500):
                        human_type(p_inp, password, clear_first=True)
                    time.sleep(0.5)
                    page.keyboard.press("Enter")
                    time.sleep(3.5)

        # -------------------------------------------------------------
        # STEP 2: 2FA TOTP AUTO-SOLVER
        # -------------------------------------------------------------
        current_state, state_desc = detect_facebook_tab_state(page)
        if current_state == "2FA_REQUIRED":
            log("  🔐 2FA Challenge detected on screen!")
            if two_factor:
                totp_code = generate_totp_2fa_code(two_factor)
                if totp_code:
                    log(f"  ⚡ Generated Live TOTP Code: [{totp_code}]. Submitting...")
                    code_inp = page.locator("input[name='approvals_code'], input#approvals_code, input[name='code'], input[type='number'], input[type='text']").first
                    if code_inp.is_visible(timeout=2000):
                        human_type(code_inp, totp_code, clear_first=True)
                        time.sleep(0.5)
                        page.keyboard.press("Enter")
                        time.sleep(3.0)

                        for btn_text in ["Save Browser", "Trust", "Continue", "Don't Save", "Remember"]:
                            btn = page.locator(f"button:has-text('{btn_text}'), div[role='button']:has-text('{btn_text}')").first
                            if btn.is_visible(timeout=1000):
                                btn.click()
                                time.sleep(1.5)
                                break
            else:
                log("  ⚠️ 2FA required by Facebook, but no 2FA secret key was found in profile.")

        # -------------------------------------------------------------
        # STEP 3: FINAL VERIFICATION & FRESH COOKIE PERSISTENCE
        # -------------------------------------------------------------
        time.sleep(2.0)
        dismiss_facebook_popup_notices(page)
        current_state, state_desc = detect_facebook_tab_state(page)
        log(f"  🏁 Final Verification State: [{current_state}] - {state_desc}")

        if current_state == "LOGGED_IN":
            ctx = context or getattr(page, "context", None)
            if ctx:
                try:
                    fresh_cookies = ctx.cookies()
                    if fresh_cookies:
                        cookie_pairs = [f"{c['name']}={c['value']}" for c in fresh_cookies if c.get("name") and c.get("value")]
                        fresh_cookie_str = "; ".join(cookie_pairs)

                        pdata["cookie"] = fresh_cookie_str
                        pdata["cookies"] = fresh_cookie_str

                        if user_data_dir:
                            p_file = Path(user_data_dir) / "profile.json"
                            if p_file.exists():
                                try:
                                    disk_p = {}
                                    with open(p_file, "r", encoding="utf-8") as f:
                                        disk_p = json.load(f)
                                    if isinstance(disk_p, dict):
                                        disk_p["cookie"] = fresh_cookie_str
                                        disk_p["cookies"] = fresh_cookie_str
                                        with open(p_file, "w", encoding="utf-8") as f:
                                            json.dump(disk_p, f, indent=2)
                                except Exception:
                                    pass

                        if profile_mgr and hasattr(profile_mgr, "update_profile"):
                            try:
                                profile_mgr.update_profile(
                                    profile_id,
                                    cookie=fresh_cookie_str,
                                    start_url="https://www.facebook.com"
                                )
                                log("  💾 Updated fresh session cookies in software database!")
                            except Exception as pe:
                                log(f"  ⚠️ Database update notice: {pe}")

                        try:
                            p_folder = None
                            if profile_mgr and hasattr(profile_mgr, "get_profile_folder"):
                                p_folder = profile_mgr.get_profile_folder(profile_id)
                            elif user_data_dir:
                                p_folder = Path(user_data_dir)

                            if p_folder and Path(p_folder).exists():
                                try:
                                    from browser import inject_cookies_to_chromium_profile, create_cookie_injector_extension
                                    inject_cookies_to_chromium_profile(p_folder, fresh_cookie_str)
                                    updated_p = profile_mgr.get_profile_by_id(profile_id) if profile_mgr else profile_data
                                    if updated_p:
                                        create_cookie_injector_extension(p_folder, updated_p)
                                    log("  💾 Synchronized fresh cookies to Chromium profile files & injector extension!")
                                except Exception:
                                    pass
                        except Exception:
                            pass
                except Exception:
                    pass

            return True, f"Re-login SUCCESSFUL for [{pname}]! Active Facebook session restored."

        elif current_state == "ON_CHECKPOINT":
            return False, f"Account on Security Checkpoint ({state_desc})"

        elif current_state == "CONTINUE_SCREEN":
            return False, "Facebook rejected the credentials on Continue screen."

        else:
            return False, f"Re-login incomplete ({state_desc})"

    except Exception as e:
        return False, f"Login exception: {str(e)}"



def apply_bot_window_icon_win32(ico_path: Path, num_text: str = "") -> None:
    """Applies the custom numbered profile icon (.ico) to the active browser window and taskbar."""
    if os.name != "nt" or not ico_path.exists():
        return

    main_pid = os.getpid()

    def _worker():
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

        for _ in range(15):
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

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
            user32.EnumWindows(WNDENUMPROC(EnumWindowsProc), 0)

            if found_hwnds:
                for hwnd in found_hwnds:
                    try:
                        user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hIcon)
                        user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hIcon)
                        if num_text:
                            user32.SetPropW(hwnd, "AppUserModelID", f"srkBrowser.Profile.{num_text}")
                    except Exception:
                        pass
                break

    import threading
    threading.Thread(target=_worker, daemon=True).start()


def parse_profile_numbers_input(raw_input: str, all_profiles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Parse comma/dash/space separated profile numbers (e.g. '540', '1-5', '#540', 'Profile540', '540, 541')
    and match accurately against profile number digits, profile name, or UID.
    """
    if not raw_input or not str(raw_input).strip():
        return []

    cleaned = str(raw_input).replace("#", "").replace("Profile", "").replace("profile", "")
    target_nums = set()
    raw_strings = set()

    parts = re.split(r"[,;\s]+", cleaned)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            sub = part.split("-", 1)
            s_raw, e_raw = re.sub(r"\D", "", sub[0]), re.sub(r"\D", "", sub[1])
            if s_raw.isdigit() and e_raw.isdigit():
                s_val, e_val = int(s_raw), int(e_raw)
                for n in range(min(s_val, e_val), max(s_val, e_val) + 1):
                    target_nums.add(n)
        else:
            n_clean = re.sub(r"\D", "", part)
            if n_clean.isdigit():
                target_nums.add(int(n_clean))
            else:
                raw_strings.add(part.lower())

    matched = []
    seen_ids = set()

    for p in all_profiles:
        pid = p.get("id") or str(p)
        if pid in seen_ids:
            continue

        raw_num = str(p.get("number", ""))
        num_clean = re.sub(r"\D", "", raw_num)

        # 1. Match by integer profile number (e.g. '540' matches 'Profile540' or '#540')
        if num_clean.isdigit() and int(num_clean) in target_nums:
            matched.append(p)
            seen_ids.add(pid)
            continue

        # 2. Match by exact name or UID
        p_name = str(p.get("name", "")).strip().lower()
        p_uid = re.sub(r"\.0$", "", str(p.get("uid", p.get("fb_uid", "")))).strip().lower()

        if raw_strings:
            if p_name in raw_strings or p_uid in raw_strings:
                matched.append(p)
                seen_ids.add(pid)

    return matched


def filter_profiles_by_target(
    all_profiles: List[Dict[str, Any]],
    mode: str,
    group_name: str = "",
    numbers_text: str = ""
) -> List[Dict[str, Any]]:
    """Filter profiles based on selection mode ('group' vs 'numbers')."""
    if not all_profiles:
        return []

    if mode == "group":
        grp_clean = str(group_name or "").strip().lower()
        if not grp_clean or grp_clean in ("all profiles", "all groups", "all", ""):
            return list(all_profiles)
        return [
            p for p in all_profiles 
            if str(p.get("group", "Default")).strip().lower() == grp_clean
        ]
    elif mode == "numbers":
        return parse_profile_numbers_input(numbers_text, all_profiles)

    return list(all_profiles)


def scan_video_folder(folder_path: str) -> List[Path]:
    """Scan directory and return naturally sorted list of video files."""
    if not folder_path or not os.path.isdir(folder_path):
        return []

    supported_exts = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
    folder = Path(folder_path)
    video_files = []

    try:
        for f in folder.iterdir():
            if f.is_file() and f.suffix.lower() in supported_exts:
                video_files.append(f)
    except Exception:
        return []

    def natural_sort_key(p: Path):
        return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', p.name)]

    video_files.sort(key=natural_sort_key)
    return video_files


def load_lines_from_txt_file(file_path: str) -> List[str]:
    """Load clean, non-empty lines from a text document (.txt)."""
    if not file_path or not os.path.isfile(file_path):
        return []

    encodings = ["utf-8", "utf-8-sig", "cp1252", "latin-1"]
    content = ""
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                content = f.read()
            break
        except Exception:
            continue

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    return lines


def load_descriptions_from_txt_file(file_path: str) -> List[str]:
    """Smart loader for descriptions supporting multi-line paragraphs, '---' dividers, and single lines."""
    if not file_path or not os.path.isfile(file_path):
        return []

    encodings = ["utf-8", "utf-8-sig", "cp1252", "latin-1"]
    content = ""
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                content = f.read()
            break
        except Exception:
            continue

    return parse_description_chunks(content)


def parse_raw_text_lines(raw_text: str) -> List[str]:
    """Parse direct user input lines from text area widget."""
    if not raw_text or not raw_text.strip():
        return []
    return [l.strip() for l in raw_text.splitlines() if l.strip()]


def parse_description_chunks(raw_text: str) -> List[str]:
    """
    Intelligently parses descriptions:
    1. If '---' or '===' dividers exist, splits by divider line.
    2. Else if multiple blank lines exist (\n\n+), splits by blank lines preserving internal newlines.
    3. Else falls back to non-empty single lines.
    """
    if not raw_text or not raw_text.strip():
        return []

    # Case 1: Explicit divider like '---' or '==='
    if re.search(r'\n\s*[-=_]{3,}\s*\n', raw_text):
        chunks = [c.strip() for c in re.split(r'\n\s*[-=_]{3,}\s*\n', raw_text) if c.strip()]
        if chunks:
            return chunks
    elif "---" in raw_text:
        chunks = [c.strip() for c in raw_text.split("---") if c.strip()]
        if chunks:
            return chunks

    # Case 2: Multi-line paragraphs separated by 1 or more blank lines (2+ newlines)
    if re.search(r'\n\s*\n+', raw_text):
        chunks = [c.strip() for c in re.split(r'\n\s*\n+', raw_text) if c.strip()]
        if chunks and len(chunks) > 1:
            return chunks

    # Case 3: Standard single lines
    return [l.strip() for l in raw_text.splitlines() if l.strip()]


def generate_upload_csv_report(records: List[Dict[str, Any]], reports_dir: Path) -> Optional[Path]:
    """Generate a clean timestamped CSV execution report."""
    if not records:
        return None

    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = reports_dir / f"FB_Bulk_Upload_Report_{timestamp}.csv"

    headers = [
        "Timestamp", "Profile Number", "Profile Name", "Video Name",
        "Video Path", "Title Used", "Description Preview",
        "Upload Status", "Duration (s)", "Error Details"
    ]

    try:
        with open(report_file, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for r in records:
                writer.writerow({
                    "Timestamp": r.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    "Profile Number": r.get("profile_number", ""),
                    "Profile Name": r.get("profile_name", ""),
                    "Video Name": r.get("video_name", ""),
                    "Video Path": r.get("video_path", ""),
                    "Title Used": r.get("title", ""),
                    "Description Preview": r.get("desc", "")[:100],
                    "Upload Status": r.get("status", "Unknown"),
                    "Duration (s)": round(r.get("duration", 0), 1),
                    "Error Details": r.get("error", "")
                })
        return report_file
    except Exception as e:
        print(f"[Report Error] Failed to write CSV: {e}")
        return None


def capture_diagnostic_screenshot(
    page: Any,
    profile_name: str = "profile",
    label: str = "error",
    reports_dir: Optional[Path] = None,
    uid: str = "",
    password: str = "",
    extra_info: str = ""
) -> str:
    """
    Captures a high-resolution diagnostic screenshot of the browser page state when failure occurs.
    Saved under reports/screenshots/UID_{uid}_{pname}_{label}_{timestamp}.png
    Overlays a clear diagnostic header banner at top with UID, Profile, Status and Timestamp.
    """
    try:
        import datetime
        if not reports_dir:
            reports_dir = Path(__file__).resolve().parent / "reports"
        ss_dir = Path(reports_dir) / "fail_screenshots"
        ss_dir.mkdir(parents=True, exist_ok=True)

        clean_pname = re.sub(r"[^\w\-]", "_", str(profile_name)).strip("_") or "profile"
        clean_label = re.sub(r"[^\w\-]", "_", str(label)).strip("_") or "error"
        t_stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        clean_uid = re.sub(r"[^\w\-]", "", str(uid)).strip()
        if not clean_uid and "fb_" in clean_pname.lower():
            match = re.search(r"\d{10,20}", clean_pname)
            if match:
                clean_uid = match.group(0)

        if clean_uid:
            file_name = f"UID_{clean_uid}_{clean_pname}_{clean_label}_{t_stamp}.png"
        else:
            file_name = f"{clean_pname}_{clean_label}_{t_stamp}.png"

        ss_file = ss_dir / file_name

        if not page or page.is_closed():
            return ""

        page.screenshot(path=str(ss_file), full_page=False, timeout=5000)

        # Draw banner if PIL is available
        try:
            from PIL import Image, ImageDraw
            with Image.open(ss_file) as img:
                img = img.convert("RGB")
                w, h = img.size
                bar_h = 44
                banner_img = Image.new("RGB", (w, h + bar_h), color=(18, 24, 38))
                banner_img.paste(img, (0, bar_h))

                draw = ImageDraw.Draw(banner_img)
                disp_uid = clean_uid if clean_uid else "N/A"
                disp_prof = clean_pname
                disp_lbl = clean_label.replace("_", " ").upper()
                info_snippet = f" | {extra_info[:40]}..." if extra_info else ""

                banner_text = f"UID: {disp_uid}  |  Profile: {disp_prof}  |  Status: {disp_lbl}{info_snippet}  |  Time: {t_stamp}"
                draw.text((16, 14), banner_text, fill=(240, 244, 248))
                banner_img.save(str(ss_file), optimize=True)
        except Exception:
            pass

        return str(ss_file.resolve())
    except Exception as err:
        print(f"[SCREENSHOT ERROR]: {err}")
        return ""


_EXCEL_REPORT_LOCK = threading.Lock()


def init_upload_excel_report(reports_dir: Path, timestamp_str: str = "") -> Path:
    """
    Initializes a new timestamped Excel workbook with 'Success' and 'Failed' tabs.
    Returns the Path to the .xlsx file.
    """
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    t_stamp = timestamp_str or datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = reports_dir / f"FB_Bulk_Upload_Report_{t_stamp}.xlsx"

    if not OPENPYXL_AVAILABLE:
        return report_file

    with _EXCEL_REPORT_LOCK:
        wb = openpyxl.Workbook()

        # TAB 1: Success
        ws_success = wb.active
        ws_success.title = "Success"
        headers_success = [
            "Profile Number",
            "UID",
            "Password",
            "2FA Secret",
            "Cookie",
            "Upload Status"
        ]
        ws_success.append(headers_success)

        # Styling Success Header: Dark Emerald Green & Bold White
        h_success_fill = PatternFill(start_color="064e3b", end_color="064e3b", fill_type="solid")
        h_success_font = Font(name="Segoe UI", size=11, bold=True, color="ffffff")
        ws_success.row_dimensions[1].height = 26

        for col_idx in range(1, len(headers_success) + 1):
            c = ws_success.cell(row=1, column=col_idx)
            c.fill = h_success_fill
            c.font = h_success_font
            c.alignment = Alignment(horizontal="center", vertical="center")

        ws_success.freeze_panes = "A2"
        ws_success.column_dimensions["A"].width = 16  # Profile Number
        ws_success.column_dimensions["B"].width = 22  # UID
        ws_success.column_dimensions["C"].width = 18  # Password
        ws_success.column_dimensions["D"].width = 24  # 2FA Secret
        ws_success.column_dimensions["E"].width = 35  # Cookie
        ws_success.column_dimensions["F"].width = 16  # Upload Status

        # TAB 2: Failed
        ws_failed = wb.create_sheet(title="Failed")
        headers_failed = [
            "Profile Number",
            "UID",
            "Password",
            "2FA Secret",
            "Cookie",
            "Upload Status",
            "Error Details"
        ]
        ws_failed.append(headers_failed)

        # Styling Failed Header: Dark Crimson Red & Bold White
        h_failed_fill = PatternFill(start_color="881337", end_color="881337", fill_type="solid")
        h_failed_font = Font(name="Segoe UI", size=11, bold=True, color="ffffff")
        ws_failed.row_dimensions[1].height = 26

        for col_idx in range(1, len(headers_failed) + 1):
            c = ws_failed.cell(row=1, column=col_idx)
            c.fill = h_failed_fill
            c.font = h_failed_font
            c.alignment = Alignment(horizontal="center", vertical="center")

        ws_failed.freeze_panes = "A2"
        ws_failed.column_dimensions["A"].width = 16  # Profile Number
        ws_failed.column_dimensions["B"].width = 22  # UID
        ws_failed.column_dimensions["C"].width = 18  # Password
        ws_failed.column_dimensions["D"].width = 24  # 2FA Secret
        ws_failed.column_dimensions["E"].width = 35  # Cookie
        ws_failed.column_dimensions["F"].width = 16  # Upload Status
        ws_failed.column_dimensions["G"].width = 45  # Error Details

        try:
            wb.save(str(report_file))
        except Exception as e:
            print(f"[INIT EXCEL ERROR]: {e}")

    return report_file


def append_upload_report_record_realtime(
    report_file: Path,
    record: Dict[str, Any]
) -> None:
    """
    Thread-safely appends a single profile execution record into the live Excel workbook.
    If status is Success -> appends to 'Success' tab.
    Else -> appends to 'Failed' tab.
    """
    if not OPENPYXL_AVAILABLE or not report_file or not Path(report_file).exists():
        return

    status_str = str(record.get("status", "")).strip()
    is_success = "succ" in status_str.lower() or status_str.lower() == "success"

    prof_num = str(record.get("profile_number") or record.get("number") or record.get("name") or "").strip()
    uid = str(record.get("uid") or record.get("fb_uid") or "").strip()
    pwd = str(record.get("password") or record.get("fb_pass") or "").strip()
    secret_2fa = str(record.get("secret_2fa") or record.get("fb_2fa") or record.get("two_factor") or "").strip()
    cookie = str(record.get("cookie") or record.get("cookies") or "").strip()
    err_details = str(record.get("error") or record.get("error_details") or record.get("failure_reason") or "").strip()

    with _EXCEL_REPORT_LOCK:
        try:
            wb = openpyxl.load_workbook(str(report_file))

            cell_font_normal = Font(name="Segoe UI", size=10, color="1e293b")
            cell_font_bold = Font(name="Segoe UI", size=10, bold=True, color="0f172a")

            if is_success:
                ws = wb["Success"] if "Success" in wb.sheetnames else wb.active
                row_vals = [prof_num, uid, pwd, secret_2fa, cookie, "Success"]
                ws.append(row_vals)
                row_idx = ws.max_row
                ws.row_dimensions[row_idx].height = 20

                # Formats
                ws.cell(row=row_idx, column=1).font = cell_font_bold
                ws.cell(row=row_idx, column=1).alignment = Alignment(horizontal="center", vertical="center")

                c_uid = ws.cell(row=row_idx, column=2)
                c_uid.number_format = "@"
                c_uid.font = cell_font_normal
                c_uid.alignment = Alignment(horizontal="center", vertical="center")

                ws.cell(row=row_idx, column=3).font = cell_font_normal
                ws.cell(row=row_idx, column=3).alignment = Alignment(horizontal="left", vertical="center")

                ws.cell(row=row_idx, column=4).font = cell_font_normal
                ws.cell(row=row_idx, column=4).alignment = Alignment(horizontal="left", vertical="center")

                ws.cell(row=row_idx, column=5).font = cell_font_normal
                ws.cell(row=row_idx, column=5).alignment = Alignment(horizontal="left", vertical="center")

                c_stat = ws.cell(row=row_idx, column=6)
                c_stat.fill = PatternFill(start_color="dcfce7", end_color="dcfce7", fill_type="solid")
                c_stat.font = Font(name="Segoe UI", size=10, bold=True, color="15803d")
                c_stat.alignment = Alignment(horizontal="center", vertical="center")

            else:
                ws = wb["Failed"] if "Failed" in wb.sheetnames else wb.create_sheet("Failed")
                row_vals = [prof_num, uid, pwd, secret_2fa, cookie, "Failed", err_details]
                ws.append(row_vals)
                row_idx = ws.max_row
                ws.row_dimensions[row_idx].height = 20

                ws.cell(row=row_idx, column=1).font = cell_font_bold
                ws.cell(row=row_idx, column=1).alignment = Alignment(horizontal="center", vertical="center")

                c_uid = ws.cell(row=row_idx, column=2)
                c_uid.number_format = "@"
                c_uid.font = cell_font_normal
                c_uid.alignment = Alignment(horizontal="center", vertical="center")

                ws.cell(row=row_idx, column=3).font = cell_font_normal
                ws.cell(row=row_idx, column=3).alignment = Alignment(horizontal="left", vertical="center")

                ws.cell(row=row_idx, column=4).font = cell_font_normal
                ws.cell(row=row_idx, column=4).alignment = Alignment(horizontal="left", vertical="center")

                ws.cell(row=row_idx, column=5).font = cell_font_normal
                ws.cell(row=row_idx, column=5).alignment = Alignment(horizontal="left", vertical="center")

                c_stat = ws.cell(row=row_idx, column=6)
                c_stat.fill = PatternFill(start_color="fee2e2", end_color="fee2e2", fill_type="solid")
                c_stat.font = Font(name="Segoe UI", size=10, bold=True, color="b91c1c")
                c_stat.alignment = Alignment(horizontal="center", vertical="center")

                c_err = ws.cell(row=row_idx, column=7)
                c_err.font = Font(name="Segoe UI", size=9.5, color="7f1d1d")
                c_err.alignment = Alignment(horizontal="left", vertical="center")

            wb.save(str(report_file))
        except Exception as ex:
            print(f"[APPEND EXCEL ERROR]: {ex}")


def get_default_titles_file_path() -> Path:
    candidates = [
        Path(__file__).resolve().parent / "default_titles.txt",
        Path(__file__).resolve().parent.parent.parent / "data" / "default_titles.txt",
        Path("data/default_titles.txt").resolve(),
    ]
    for c in candidates:
        if c.exists():
            return c
    return Path(__file__).resolve().parent / "default_titles.txt"


def get_default_descriptions_file_path() -> Path:
    candidates = [
        Path(__file__).resolve().parent / "default_descriptions.txt",
        Path(__file__).resolve().parent.parent.parent / "data" / "default_descriptions.txt",
        Path("data/default_descriptions.txt").resolve(),
    ]
    for c in candidates:
        if c.exists():
            return c
    return Path(__file__).resolve().parent / "default_descriptions.txt"


def fetch_cloud_uploader_templates() -> Dict[str, Any]:
    """
    Fetches the latest admin-configured Titles and Descriptions from local files or Cloud API.
    Prioritizes local default_titles.txt and default_descriptions.txt if available.
    """
    local_titles = []
    t_file = get_default_titles_file_path()
    if t_file.exists():
        try:
            with open(t_file, "r", encoding="utf-8") as f:
                local_titles = [line.strip() for line in f if line.strip()]
        except Exception:
            local_titles = []

    local_descs = []
    d_file = get_default_descriptions_file_path()
    if d_file.exists():
        try:
            raw_text = d_file.read_text(encoding="utf-8")
            if "\n---\n" in raw_text:
                local_descs = [b.strip() for b in raw_text.split("\n---\n") if b.strip()]
            else:
                local_descs = [line.strip() for line in raw_text.splitlines() if line.strip()]
        except Exception:
            local_descs = []

    api_urls = [
        "https://srbrowser.com/api/v1/bot/uploader/templates",
        "http://127.0.0.1:5000/api/v1/bot/uploader/templates",
        "https://api.srbrowser.com/api/v1/bot/uploader/templates"
    ]

    for url in api_urls:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "srkBrowser-BulkUploader/2.0", "Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                if resp.status == 200:
                    payload = json.loads(resp.read().decode("utf-8"))
                    tpls = payload.get("templates")
                    if isinstance(tpls, dict):
                        cloud_titles = tpls.get("titles") or []
                        cloud_descs = tpls.get("descriptions") or []
                        final_titles = local_titles if local_titles else cloud_titles
                        final_descs = local_descs if local_descs else cloud_descs
                        return {
                            "titles": final_titles,
                            "descriptions": final_descs,
                            "placeholder": tpls.get("placeholder", "{{link}}")
                        }
        except Exception:
            pass

    # Built-in fallback presets if network unreachable
    return {
        "titles": local_titles if local_titles else [
            "Episode 01 - Viral Moments 2026",
            "Episode 02 - Daily Motivation & Mindset",
            "Episode 03 - Smart Life Hacks You Need",
            "Episode 04 - Trending Entertainment Clip",
            "Episode 05 - Tech Evolution & Future",
            "Episode 06 - Incredible Discoveries",
            "Episode 07 - Success Secrets Revealed",
            "Episode 08 - Most Inspiring Story Today",
            "Episode 09 - Best Highlights Compilation",
            "Episode 10 - Epic Ending & Follow For More"
        ],
        "descriptions": local_descs if local_descs else [
            "🔥 Watch the full video and exclusive updates here 👉 {{link}}\nDon't forget to follow our page for more daily reels! #Viral #Trending #Reels",
            "🚀 Part 2 is out now! Click the link below to explore:\n👉 {{link}}\nSave this reel and share with your friends! #DailyReels #ExplorePage",
            "✨ Special offer and complete details available here 👉 {{link}}\nHit follow for daily viral updates! #ViralVideos #TrendingReels",
            "💡 Don't miss the complete breakdown! Check here 👉 {{link}}\nFollow for more daily content! #Motivation #Inspiration #Reels",
            "🎯 Full story and resource link 👉 {{link}}\nComment your thoughts below! #ViralPost #ReelsInstagram #FacebookReels"
        ],
        "placeholder": "{{link}}"
    }


def apply_user_links_to_descriptions(
    descriptions: List[str], 
    user_links: List[str], 
    placeholder: str = "{{link}}"
) -> List[str]:
    """
    Substitutes user-supplied links into description templates:
    1. Replaces {{link}}, {{LINK}}, {link}, {LINK}, [link], [LINK] with the user link.
    2. Sequentially cycles links if multiple links provided, or uses the single link.
    3. If no placeholder tag is found in the template and a user link is supplied,
       cleanly appends the link at the bottom.
    """
    clean_links = [str(l).strip() for l in user_links if str(l).strip()]
    if not descriptions:
        return []
    if not clean_links:
        # If user did not provide any link, strip out any stray {{link}} placeholders cleanly
        cleaned = []
        for d in descriptions:
            text = d
            for tag in ["{{link}}", "{{LINK}}", "{link}", "{LINK}", "[link]", "[LINK]"]:
                text = text.replace(tag, "").replace("👉  ", "").replace("👉 ", "")
            cleaned.append(text.strip())
        return cleaned

    placeholder_tags = ["{{link}}", "{{LINK}}", "{link}", "{LINK}", "[link]", "[LINK]"]
    if placeholder and placeholder not in placeholder_tags:
        placeholder_tags.insert(0, placeholder)

    results = []
    for idx, desc in enumerate(descriptions):
        active_link = clean_links[idx % len(clean_links)]
        replaced = False
        text = desc

        # Check if text already contains any of the target links
        already_has_link = any(lnk in text for lnk in clean_links)

        for tag in placeholder_tags:
            if tag in text:
                text = text.replace(tag, active_link)
                replaced = True

        # Case-insensitive fallback check
        if not replaced and re.search(r"\{\{link\}\}", text, flags=re.IGNORECASE):
            text = re.sub(r"\{\{link\}\}", active_link, text, flags=re.IGNORECASE)
            replaced = True

        # If user explicitly put {{link}} in their description, NEVER append at the bottom.
        # Only append at bottom if NO placeholder was in template AND NO link is present in text.
        if not replaced and not already_has_link and active_link:
            if "http://" not in text and "https://" not in text:
                text = f"{text}\n\n👉 {active_link}"

        results.append(text)

    return results


# -------------------------------------------------------------
# Cloud Video Vault & Stealth Caching
# -------------------------------------------------------------

def get_cloud_video_vault_dir() -> Path:
    """
    Returns the hidden, protected local cache directory for cloud videos.
    Located in AppData/Local/srkBrowser/runtime/.cloud_vault.
    Marked with Windows hidden attribute (+h) to prevent user tampering.
    """
    vault_dir = Path.home() / "AppData" / "Local" / "srkBrowser" / "runtime" / ".cloud_vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        try:
            import subprocess
            subprocess.run(f'attrib +h "{vault_dir}"', shell=True, capture_output=True, timeout=2)
        except Exception:
            pass
    return vault_dir


def fetch_cloud_videos_manifest(base_url: str = "https://srbrowser.com") -> List[dict]:
    """
    Fetches the video vault manifest from the central server.
    """
    url = f"{base_url.rstrip('/')}/api/v1/bot/uploader/videos/manifest"
    try:
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and data.get("status") == "ok":
                return data.get("videos", [])
    except Exception:
        pass
    return []


def sync_cloud_video_vault(
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
    base_url: str = "https://srbrowser.com"
) -> List[Path]:
    """
    Synchronizes cloud videos from server to the local hidden vault with smart differential caching:
    - Skips already-cached videos where file size matches manifest.
    - Only downloads new or modified videos.
    - Protects downloaded files with hidden attribute.
    - Returns list of Path objects ready for upload.
    """
    vault_dir = get_cloud_video_vault_dir()
    manifest = fetch_cloud_videos_manifest(base_url)

    if not manifest:
        # If server unreachable, return any existing cached videos in vault
        video_exts = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
        cached = [p for p in sorted(vault_dir.iterdir()) if p.is_file() and p.suffix.lower() in video_exts and p.stat().st_size > 1024]
        return cached

    ready_paths = []
    total_videos = len(manifest)

    for idx, item in enumerate(manifest, 1):
        filename = item.get("filename", "")
        size_bytes = item.get("size_bytes", 0)
        rel_url = item.get("download_url", "")
        target_path = vault_dir / filename

        # 1. SMART CACHING CHECK: Skip download if already present & size matches
        if target_path.exists() and target_path.stat().st_size == size_bytes and size_bytes > 0:
            ready_paths.append(target_path)
            if progress_callback:
                progress_callback(f"Cached: {item.get('original_name', filename)}", idx, total_videos)
            continue

        # 2. DOWNLOAD NEW OR UPDATED VIDEO
        if not rel_url:
            continue

        download_url = f"{base_url.rstrip('/')}{rel_url}" if rel_url.startswith("/") else rel_url
        if progress_callback:
            progress_callback(f"Downloading [{idx}/{total_videos}]: {item.get('original_name', filename)}...", idx, total_videos)

        try:
            tmp_path = vault_dir / f"{filename}.tmp"
            with requests.get(download_url, stream=True, timeout=120) as r:
                r.raise_for_status()
                with open(tmp_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)

            # Atomic replace
            if tmp_path.exists():
                if target_path.exists():
                    target_path.unlink()
                tmp_path.rename(target_path)

                # Set Windows hidden attribute
                if os.name == "nt":
                    try:
                        import subprocess
                        subprocess.run(f'attrib +h "{target_path}"', shell=True, capture_output=True, timeout=2)
                    except Exception:
                        pass

                ready_paths.append(target_path)
        except Exception as ex:
            if progress_callback:
                progress_callback(f"Download failed for {filename}: {ex}", idx, total_videos)

    return ready_paths



# -------------------------------------------------------------
# Anti-Detect Human Emulation Utilities
# -------------------------------------------------------------

def smart_sleep(min_sec: float = 1.0, max_sec: float = 2.5) -> None:
    """Sleep for a randomized duration to break rigid timing patterns."""
    time.sleep(random.uniform(min_sec, max_sec))


def get_stealth_init_script() -> str:
    """
    Returns robust stealth JavaScript to mask automation indicators:
    - Sets navigator.webdriver to false across prototype matching genuine desktop Chrome
    - Dynamically scrubs all CDP automation markers (/^cdc_/) from window and document
    - Simulates authentic window.chrome runtime, csi, loadTimes, and app objects
    - Sets authentic navigator.languages, plugins list, hardwareConcurrency, and deviceMemory
    - Spoofs both WebGL and WebGL2 unmasked vendor and renderer to consistent desktop NVIDIA GPU
    - Normalizes notification and clipboard permissions queries
    """
    return """
    (() => {
        try {
            // 1. Mask navigator.webdriver on prototype matching authentic Chrome
            Object.defineProperty(Navigator.prototype, 'webdriver', {
                get: () => false,
                enumerable: true,
                configurable: true
            });
            try {
                delete navigator.webdriver;
            } catch(e) {}
        } catch(e) {}

        try {
            // 2. Dynamically clean all CDP automation variables (cdc_...)
            const cleanObj = (obj) => {
                if (!obj) return;
                try {
                    for (const key of Object.getOwnPropertyNames(obj)) {
                        if (/^cdc_/.test(key)) {
                            try { delete obj[key]; } catch(e) { obj[key] = undefined; }
                        }
                    }
                } catch(e) {}
            };
            cleanObj(window);
            cleanObj(document);
            window.cdc_adoQpoasnfa76pfcZLmcfl_Array = undefined;
            window.cdc_adoQpoasnfa76pfcZLmcfl_Promise = undefined;
            window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol = undefined;
            window.__playwright = undefined;
            window.__pw_manualStatus = undefined;
        } catch(e) {}

        try {
            // 3. Mock authentic window.chrome runtime & environment
            if (!window.chrome) {
                window.chrome = {};
            }
            window.chrome.runtime = window.chrome.runtime || {
                connect: () => {},
                sendMessage: () => {},
                onMessage: { addListener: () => {}, removeListener: () => {} },
                OnInstalledReason: { INSTALL: "install", UPDATE: "update", CHROME_UPDATE: "chrome_update", SHARED_MODULE_UPDATE: "shared_module_update" },
                OnRestartRequiredReason: { APP_UPDATE: "app_update", OS_UPDATE: "os_update", PERIODIC: "periodic" }
            };
            window.chrome.loadTimes = window.chrome.loadTimes || function() {
                return {
                    commitLoadTime: Date.now() / 1000 - 0.5,
                    connectionInfo: "h2",
                    finishDocumentLoadTime: Date.now() / 1000 - 0.2,
                    finishLoadTime: Date.now() / 1000 - 0.1,
                    firstPaintAfterLoadTime: 0,
                    firstPaintTime: Date.now() / 1000 - 0.3,
                    navigationType: "Other",
                    npnNegotiatedProtocol: "h2",
                    requestTime: Date.now() / 1000 - 0.8,
                    startLoadTime: Date.now() / 1000 - 0.8,
                    wasAlternateProtocolAvailable: false,
                    wasFetchedViaSpdy: true,
                    wasNpnNegotiated: true
                };
            };
            window.chrome.csi = window.chrome.csi || function() {
                return {
                    onloadT: Date.now() - 500,
                    pageT: 250.5,
                    startE: Date.now() - 1000,
                    tran: 15
                };
            };
            window.chrome.app = window.chrome.app || {
                isInstalled: false,
                InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' },
                RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' }
            };
        } catch(e) {}

        try {
            // 4. Realistic hardware and navigator attributes
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
                configurable: true
            });
            Object.defineProperty(navigator, 'language', {
                get: () => 'en-US',
                configurable: true
            });
            Object.defineProperty(navigator, 'maxTouchPoints', {
                get: () => 0,
                configurable: true
            });
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 8,
                configurable: true
            });
            Object.defineProperty(navigator, 'deviceMemory', {
                get: () => 8,
                configurable: true
            });

            // Realistic standard plugins matching modern Chrome
            const fakePlugins = [
                { name: 'PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                { name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                { name: 'Chromium PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                { name: 'Microsoft Edge PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                { name: 'WebKit built-in PDF', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }
            ];
            fakePlugins.item = function(i) { return this[i] || null; };
            fakePlugins.namedItem = function(name) { return this.find(p => p.name === name) || null; };
            Object.defineProperty(navigator, 'plugins', {
                get: () => fakePlugins,
                configurable: true
            });
        } catch(e) {}

        try {
            // 5. Spoof WebGL & WebGL2 vendor and renderer consistently
            const spoofParam = (proto) => {
                if (!proto) return;
                const originalGet = proto.getParameter;
                proto.getParameter = function(param) {
                    if (param === 37445) return 'Google Inc. (NVIDIA)';
                    if (param === 37446) return 'ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)';
                    return originalGet.apply(this, arguments);
                };
            };
            if (window.WebGLRenderingContext) spoofParam(WebGLRenderingContext.prototype);
            if (window.WebGL2RenderingContext) spoofParam(WebGL2RenderingContext.prototype);
        } catch(e) {}

        try {
            // 6. Normalize permissions query
            if (window.navigator && window.navigator.permissions) {
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => {
                    if (!parameters) return originalQuery(parameters);
                    if (parameters.name === 'notifications') {
                        return Promise.resolve({ state: Notification.permission || 'default', onchange: null });
                    }
                    if (parameters.name === 'clipboard-read' || parameters.name === 'clipboard-write') {
                        return Promise.resolve({ state: 'granted', onchange: null });
                    }
                    return originalQuery(parameters);
                };
            }
        } catch(e) {}
    })();
    """


def human_mouse_jitter(page: Any) -> None:
    """Perform subtle, natural mouse movement to look active and human-driven."""
    try:
        x = random.randint(280, 960)
        y = random.randint(180, 620)
        page.mouse.move(x, y, steps=random.randint(6, 14))
    except Exception:
        pass


def human_mouse_move(page: Any, target_x: float, target_y: float, steps: int = 0) -> None:
    """Move the mouse cursor along a smooth, human-like trajectory with natural easing."""
    try:
        if not page or not hasattr(page, "mouse"):
            return
        if steps <= 0:
            steps = random.randint(8, 16)
        # Add slight sub-pixel natural hand jitter
        target_x += random.uniform(-2, 2)
        target_y += random.uniform(-2, 2)
        page.mouse.move(target_x, target_y, steps=steps)
    except Exception:
        pass


def human_scroll(page: Any, steps: int = 2, direction: str = "down") -> None:
    """Smooth human-like mouse wheel scrolling with micro-pauses and slight jitter."""
    try:
        for _ in range(steps):
            base_delta = random.randint(160, 360)
            delta = base_delta if direction == "down" else -base_delta
            page.mouse.wheel(0, delta)
            smart_sleep(0.25, 0.55)
            # Occasionally real humans do a slight reverse bounce/correction
            if random.random() < 0.28:
                page.mouse.wheel(0, -random.randint(30, 80))
                smart_sleep(0.15, 0.3)
    except Exception:
        pass


def human_click(locator: Any, page: Any = None) -> None:
    """
    Genuine OS-level trusted mouse click:
    - Scrolls element into view
    - Smooth human mouse trajectory to element
    - Natural hover hesitation (200-450ms)
    - Authentic mouse click with physical button-down delay (delay=55-125ms) -> isTrusted: true!
    - Brief post-click cognitive pause (150-300ms)
    """
    try:
        try:
            locator.scroll_into_view_if_needed(timeout=1500)
        except Exception:
            pass
        # Human hesitation / cursor aiming
        try:
            locator.hover(timeout=2000)
            smart_sleep(0.2, 0.45)
        except Exception:
            pass
        # Realistic physical click duration generates authentic isTrusted: true event
        locator.click(delay=random.randint(55, 125), timeout=2500)
        smart_sleep(0.15, 0.3)
    except Exception:
        try:
            locator.click(delay=random.randint(50, 100))
        except Exception:
            pass


def human_type(locator: Any, text: str, min_delay_ms: int = 25, max_delay_ms: int = 75) -> None:
    """Type character by character with human-like jitter intervals."""
    try:
        locator.click(delay=random.randint(40, 80))
        smart_sleep(0.2, 0.35)
        for ch in text:
            locator.type(ch, delay=random.randint(min_delay_ms, max_delay_ms))
            if random.random() < 0.08:
                smart_sleep(0.1, 0.25)
    except Exception:
        try:
            locator.fill(text)
        except Exception:
            pass


def human_copy_paste(*args, **kwargs) -> bool:
    """
    Robust, authentic text insertion into textarea or rich-text contenteditable (Meta Lexical/Draft.js):
    - Scrolls element into view
    - Focuses with real mouse click
    - Selects all and clears existing text (Control+A, Backspace)
    - Primary: Uses Playwright native keyboard.insert_text(text) which triggers beforeinput/input events
    - Verification: Checks if text was successfully registered in the editor
    - Fallback 1: Real clipboard paste via Control+V
    - Fallback 2: Direct locator.fill(text)
    - Fallback 3: DOM execCommand('insertText')
    - Fast, natural post-paste delay
    """
    page: Any = None
    locator: Any = None
    text: str = ""
    field_name: str = kwargs.get("field_name", "")
    post_delay_min: float = float(kwargs.get("post_delay_min", 0.15))
    post_delay_max: float = float(kwargs.get("post_delay_max", 0.25))

    if len(args) >= 3:
        if hasattr(args[0], "keyboard") or hasattr(args[0], "context"):
            page, locator, text = args[0], args[1], str(args[2])
        elif hasattr(args[2], "keyboard") or hasattr(args[2], "context"):
            locator, text, page = args[0], str(args[1]), args[2]
        elif hasattr(args[1], "keyboard") or hasattr(args[1], "context"):
            locator, page, text = args[0], args[1], str(args[2])
        else:
            page, locator, text = args[0], args[1], str(args[2])
    elif len(args) == 2:
        locator, text = args[0], str(args[1])
    else:
        return False

    if not text:
        return False

    try:
        try:
            locator.scroll_into_view_if_needed(timeout=2000)
        except Exception:
            pass

        # Quick focus click
        try:
            locator.click(timeout=2000)
        except Exception:
            try:
                locator.focus()
            except Exception:
                pass

        time.sleep(0.06)

        # Clear existing text cleanly
        if page and hasattr(page, "keyboard"):
            try:
                page.keyboard.press("Control+A")
                time.sleep(0.04)
                page.keyboard.press("Backspace")
                time.sleep(0.04)
            except Exception:
                pass

        paste_succeeded = False

        # Method 1: Playwright Native Keyboard Text Insertion (100% compatible with Meta Lexical & Draft.js)
        # Directly fires native Chromium beforeinput (inputType="insertText") and input events.
        if page and hasattr(page, "keyboard"):
            try:
                page.keyboard.insert_text(text)
                time.sleep(0.08)
                check_val = ""
                try:
                    check_val = locator.evaluate("el => (el.innerText || el.textContent || el.value || '').trim()")
                except Exception:
                    pass
                if check_val and (text[:15].strip() in check_val or len(check_val) >= min(len(text) // 2, 20)):
                    paste_succeeded = True
            except Exception:
                paste_succeeded = False

        # Method 2: Authentic Clipboard Paste via Control+V fallback
        if not paste_succeeded and page and hasattr(page, "keyboard"):
            try:
                page.evaluate("""(txt) => {
                    if (navigator.clipboard && navigator.clipboard.writeText) {
                        return navigator.clipboard.writeText(txt);
                    }
                    return Promise.reject("no clipboard");
                }""", text)
                page.keyboard.press("Control+A")
                time.sleep(0.04)
                page.keyboard.press("Control+V")
                time.sleep(0.08)
                paste_succeeded = True
            except Exception:
                paste_succeeded = False

        # Method 3: Instant Playwright Fill Fallback
        if not paste_succeeded:
            try:
                locator.fill(text)
                paste_succeeded = True
            except Exception:
                pass

        # Method 4: DOM insertText fallback
        if not paste_succeeded:
            try:
                res = locator.evaluate("""(el, val) => {
                    el.focus();
                    document.execCommand('selectAll', false, null);
                    const ins = document.execCommand('insertText', false, val);
                    if (!ins) {
                        el.innerText = val;
                        el.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertFromPaste' }));
                    }
                    return true;
                }""", text)
                paste_succeeded = bool(res)
            except Exception:
                pass

        smart_sleep(post_delay_min, post_delay_max)
        return paste_succeeded

    except Exception:
        try:
            locator.fill(text)
            smart_sleep(post_delay_min, post_delay_max)
            return True
        except Exception:
            return False



def scan_managed_facebook_pages(page: Any) -> List[Dict[str, str]]:
    """
    Scans https://www.facebook.com/pages/?category=your_pages to discover all Pages
    managed by this Facebook account.
    Returns list of dicts:
    [{"name": "...", "asset_id": "...", "profile_id": "..."}, ...]
    Zero-click, immune to home newsfeed popups or notification banners.
    """
    results: List[Dict[str, str]] = []
    try:
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass

        page.goto("https://www.facebook.com/pages/?category=your_pages", timeout=35000, wait_until="domcontentloaded")
        smart_sleep(2.5, 3.5)

        try:
            page.keyboard.press("Escape")
        except Exception:
            pass

        raw_pages = page.evaluate(r"""() => {
            let list = [];
            let main = document.querySelector('div[role="main"]') || document.body;
            let allLinks = Array.from(main.querySelectorAll('a'));
            
            // 1. Collect all page profiles listed under Pages you manage
            for (let a of allLinks) {
                let href = a.getAttribute('href') || '';
                let txt = (a.innerText || '').trim();
                
                if (href.includes('profile.php?id=') || (href.includes('facebook.com/') && !href.includes('/latest/') && !href.includes('/pages/?') && !href.includes('/settings') && !href.includes('/notifications') && !href.includes('/messages/'))) {
                    let pidMatch = href.match(/id=(\d+)/);
                    let pid = pidMatch ? pidMatch[1] : '';
                    let lower = txt.toLowerCase();
                    if (txt && txt.length > 1 && !['see all', 'discover', 'followed pages', 'invites', 'create post', 'promote', 'messages', 'create page'].includes(lower)) {
                        if (!list.some(p => p.name === txt || (pid && p.profile_id === pid))) {
                            list.push({
                                name: txt,
                                profile_id: pid,
                                profile_url: href,
                                asset_id: ''
                            });
                        }
                    }
                }
            }

            // 2. Discover Meta Business Suite asset_id from nearby buttons (Inbox/Promote)
            for (let a of allLinks) {
                let href = a.getAttribute('href') || '';
                let aidMatch = href.match(/asset_id=(\d+)/) || href.match(/page_id=(\d+)/);
                if (aidMatch) {
                    let foundAid = aidMatch[1];
                    let card = a.closest('div[role="article"]') || a.parentElement;
                    let cardText = card ? (card.innerText || '').trim() : '';
                    let matched = false;
                    for (let p of list) {
                        if (cardText && cardText.includes(p.name) && !p.asset_id) {
                            p.asset_id = foundAid;
                            matched = true;
                            break;
                        }
                    }
                    if (!matched) {
                        for (let p of list) {
                            if (!p.asset_id) {
                                p.asset_id = foundAid;
                                break;
                            }
                        }
                    }
                }
            }

            // 3. Fallback: if asset_id is still empty, fallback to profile_id
            for (let p of list) {
                if (!p.asset_id && p.profile_id) {
                    p.asset_id = p.profile_id;
                }
            }

            return list;
        }""")

        if isinstance(raw_pages, list):
            for rp in raw_pages:
                name = str(rp.get("name", "")).strip()
                aid = str(rp.get("asset_id", "")).strip()
                pid = str(rp.get("profile_id", "")).strip()
                if name and (aid or pid):
                    results.append({
                        "name": name,
                        "asset_id": aid or pid,
                        "profile_id": pid or aid
                    })
    except Exception:
        pass

    return results
