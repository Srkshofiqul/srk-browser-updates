"""
Browser Profile Manager - Playwright Automation Engine, Facebook Publisher & Bulk Live Login Verification
Python 3.13 / PySide6 Desktop Application
"""

import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import random
import re
import shutil
import threading
import time
import uuid
import urllib.request
import hmac
import hashlib
import struct
import base64
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from PySide6.QtCore import QObject, QThread, Signal

from playwright.sync_api import sync_playwright
from config import PROFILES_DIR, REPORTS_DIR
from utils import export_csv_helper, generate_random_user_agent
from common_playwright import get_chrome_executable_path, resolve_user_data_dir

CHROMIUM_FAST_LAUNCH_ARGS = [
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-background-networking",
    "--disable-component-update",
    "--disable-domain-reliability",
    "--disable-client-side-phishing-detection",
    "--disable-notifications",
    "--disable-popup-blocking",
    "--deny-permission-prompts",
    "--test-type",
    "--disable-infobars",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--lang=en-US",
    "--disable-save-password-bubble",
    "--password-store=basic"
]



def clean_val_str(val: Any) -> str:
    """
    Strips trailing '.0' from float conversions of integer UIDs/numbers in Excel cells.
    """
    if val is None:
        return ""
    if isinstance(val, float):
        if val.is_integer():
            return str(int(val))
    s = str(val).strip()
    if s.endswith(".0"):
        prefix = s[:-2]
        if prefix.isdigit() or (prefix.startswith("-") and prefix[1:].isdigit()):
            return prefix
    return s


def get_chrome_executable_path() -> Optional[str]:
    """Find installed Google Chrome executable path on system for Playwright CDP sync."""
    try:
        from utils import get_system_browsers
        browsers = get_system_browsers()
        if browsers:
            for label, exe_path in browsers.items():
                if "chrome" in label.lower() and os.path.exists(exe_path):
                    return exe_path
            for exe_path in browsers.values():
                if os.path.exists(exe_path):
                    return exe_path
    except Exception:
        pass
    return None


def ensure_profile_session_persistence(profile_folder: Path) -> None:
    """Configures Chrome Preferences to prevent session cookie clearing, purge old open tab sessions, & disable password prompts."""
    try:
        default_dir = profile_folder / "Default"
        default_dir.mkdir(parents=True, exist_ok=True)

        # Ensure exit_type is clean without purging active session tokens
        pref_file = default_dir / "Preferences"
        data = {}
        if pref_file.exists():
            try:
                with open(pref_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}

        data.setdefault("profile", {})
        data["profile"]["exit_type"] = "Normal"
        data["profile"]["exited_cleanly"] = True
        data["profile"]["password_manager_enabled"] = False
        data["profile"]["password_manager_leak_detection"] = False

        data["credentials_enable_service"] = False
        data["credentials_enable_autosignin"] = False

        data.setdefault("session", {})
        data["session"]["restore_on_startup"] = 5

        with open(pref_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def extract_account_fields(row: Dict[str, Any], idx: int = 1) -> Tuple[str, str, str]:
    """
    Robustly extract (UID, Password, Cookie) from any Excel/CSV row dict,
    handling named headers, case-insensitivity, Netscape/JSON cookies, and positional fallback.
    """
    uid = ""
    password = ""
    cookie_str = ""

    # 1. Try named keys (case-insensitive)
    for k, v in row.items():
        if v is None:
            continue
        k_str = str(k).strip().lower()
        val_str = clean_val_str(v)
        if not val_str:
            continue

        if k_str in ("uid", "user", "username", "id", "account", "fb_id", "fbid"):
            if not uid:
                uid = val_str
        elif k_str in ("password", "pass", "pwd", "secret"):
            if not password:
                password = val_str
        elif k_str in ("cookie", "cookies", "cookie_str", "session"):
            if not cookie_str:
                cookie_str = val_str

    # 2. Extract values list (ignoring empty values)
    vals = [clean_val_str(v) for v in row.values() if v is not None and str(v).strip() != ""]

    # 3. Heuristics for missing fields among values
    for val in vals:
        if not cookie_str and ("datr=" in val or "c_user=" in val or "sb=" in val or "xs=" in val or "presence=" in val or "fr=" in val or "wd=" in val or "%3b" in val.lower() or "locale=" in val or "\t" in val):
            cookie_str = val
        elif not uid and val.isdigit() and len(val) >= 8:
            uid = val

    # 4. Positional fallback if still empty
    if not uid and len(vals) >= 1:
        if vals[0] != cookie_str:
            uid = vals[0]
        elif len(vals) >= 2:
            uid = vals[1]

    if not password and len(vals) >= 2:
        for val in vals:
            if val != uid and val != cookie_str:
                password = val
                break

    if not cookie_str and len(vals) >= 3:
        for val in vals:
            if val != uid and val != password:
                cookie_str = val
                break

    if uid.endswith(".0") and uid[:-2].isdigit():
        uid = uid[:-2]

    if not uid:
        uid = f"Account_{idx}"

    return uid, password, cookie_str


def parse_cookie_string(cookie_raw: str, default_domain: str = ".facebook.com") -> List[Dict[str, Any]]:
    """
    Parse raw cookie strings (JSON, Netscape tab-separated, or key=value; format)
    into structured Playwright-compatible cookie dictionaries.
    """
    cookies: List[Dict[str, Any]] = []
    c_str = cookie_raw.strip()
    if not c_str:
        return cookies

    # 1. Try JSON format
    if c_str.startswith("[") and c_str.endswith("]"):
        try:
            parsed = json.loads(c_str)
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict) and "name" in item and "value" in item:
                        domain = item.get("domain") or default_domain
                        if not domain.startswith("."):
                            domain = "." + domain
                        cookies.append({
                            "name": str(item["name"]),
                            "value": str(item["value"]),
                            "domain": domain,
                            "path": item.get("path", "/")
                        })
                return cookies
        except Exception:
            pass

    # 2. Try Netscape format (tab-separated)
    if "\t" in c_str:
        lines = c_str.splitlines()
        for line in lines:
            line_s = line.strip()
            if not line_s or line_s.startswith("#"):
                continue
            parts = line_s.split("\t")
            if len(parts) >= 7:
                dom = parts[0].strip()
                if not dom.startswith("."):
                    dom = "." + dom
                c_name = parts[5].strip()
                c_val = parts[6].strip()
                if c_name and c_val:
                    cookies.append({
                        "name": c_name,
                        "value": c_val,
                        "domain": dom,
                        "path": parts[2].strip() or "/"
                    })
        if cookies:
            return cookies

    # 3. Try key=value; string format
    pairs = c_str.split(";")
    for pair in pairs:
        pair_s = pair.strip()
        if "=" in pair_s:
            parts = pair_s.split("=", 1)
            k = parts[0].strip()
            v = parts[1].strip()
            if k and v:
                cookies.append({
                    "name": k,
                    "value": v,
                    "domain": default_domain,
                    "path": "/"
                })

    return cookies


def inject_session_cookies_if_needed(context: Any, pdata: Dict[str, Any]) -> None:
    """
    Safely injects session cookies into browser context if needed.
    If the persistent profile context on disk ALREADY contains active Facebook session cookies (c_user/xs),
    we KEEP the live disk session intact and DO NOT overwrite it with stale database cookies.
    Only if disk cookies are missing/empty do we inject pdata['cookie'].
    """
    try:
        existing_cookies = context.cookies()
        has_live_disk_session = any(
            c.get("name") in ("c_user", "xs") and str(c.get("value", "")).strip() != ""
            for c in existing_cookies
        )
        if has_live_disk_session:
            return

        cookie_str = pdata.get("cookie", "") or pdata.get("cookies", "")
        if cookie_str:
            parsed_ck = parse_cookie_string(cookie_str, default_domain=".facebook.com")
            if parsed_ck:
                parsed_ck.append({"name": "locale", "value": "en_US", "domain": ".facebook.com", "path": "/"})
                context.add_cookies(parsed_ck)
        else:
            try:
                context.add_cookies([{"name": "locale", "value": "en_US", "domain": ".facebook.com", "path": "/"}])
            except Exception:
                pass
    except Exception:
        pass


def sync_active_cookies_to_profile(context: Any, profile_mgr: Any, profile_id: str) -> None:
    """
    Extracts live active cookies from browser context and updates the profile's stored cookie in profiles.json.
    """
    try:
        if not context or not profile_mgr or not profile_id:
            return
        cookies = context.cookies()
        fb_cookies = [c for c in cookies if ".facebook.com" in c.get("domain", "") or "facebook.com" in c.get("domain", "")]
        if fb_cookies:
            cookie_items = [f"{c['name']}={c['value']}" for c in fb_cookies if 'name' in c and 'value' in c]
            cookie_str = "; ".join(cookie_items)
            if "c_user=" in cookie_str or "xs=" in cookie_str:
                profile_mgr.update_profile(profile_id, {"cookie": cookie_str})
    except Exception:
        pass



def extract_page_creation_fields(
    row: Dict[str, Any],
    idx: int = 1,
    default_name: str = "",
    default_cat: str = "Digital Creator",
    default_bio: str = ""
) -> Tuple[str, str, str]:
    """Extract (Page Name, Category, Bio) from Excel row dict or fallback to defaults."""
    page_name = ""
    category = ""
    bio = ""

    # Known column keys to exclude when searching for page name fallback
    ignore_keys = {"uid", "id", "user", "userid", "user_id", "password", "pass", "pwd", "cookie", "cookies", "c_user", "xs", "fr", "datr", "status", "notes", "group"}

    for k, v in row.items():
        if v is None:
            continue
        k_str = str(k).strip().lower()
        k_clean = "".join(c for c in k_str if c.isalnum())
        val_str = str(v).strip()
        if not val_str:
            continue

        if k_clean in ("pagename", "page", "title", "name", "fanpage", "fbpage"):
            if not page_name:
                page_name = val_str
        elif k_clean in ("category", "cat", "pagecategory"):
            if not category:
                category = val_str
        elif k_clean in ("bio", "description", "desc", "about"):
            if not bio:
                bio = val_str

    # If page_name was not found by explicit column matching, look for candidate columns excluding account credentials
    if not page_name:
        for k, v in row.items():
            if v is None:
                continue
            k_str = str(k).strip().lower()
            k_clean = "".join(c for c in k_str if c.isalnum())
            if k_clean in ignore_keys:
                continue
            val_str = str(v).strip()
            if not val_str:
                continue
            if not val_str.isdigit() and len(val_str) >= 2 and "datr=" not in val_str and "c_user=" not in val_str:
                page_name = val_str
                break

    if not page_name:
        page_name = default_name if default_name else f"Page_{idx}"
    if not category:
        category = default_cat if default_cat else "Digital Creator"
    if not bio:
        bio = default_bio

    return page_name, category, bio


def create_facebook_page_session(
    page: Any,
    page_name: str,
    category: str = "Digital Creator",
    bio: str = "",
    mode: str = "skip",
    log_func: Optional[Any] = None
) -> Tuple[bool, str]:
    """
    Automate Facebook Page creation on an active Playwright page session.
    mode='skip': checks if account already manages a Page and skips creation.
    mode='force': creates a Page regardless.
    """
    def log(msg: str) -> None:
        if log_func:
            log_func(msg)
        else:
            print(msg)

    # Auto-dismiss/accept any browser dialogs (e.g. "Leave page?")
    try:
        page.on("dialog", lambda dialog: dialog.accept())
    except Exception:
        pass

    # 1. Check existing pages if mode is "skip"
    if mode.lower() == "skip":
        log("  🔎 Checking if account already has an existing Facebook Page...")
        try:
            page.goto("https://www.facebook.com/pages/?category=your_pages", timeout=30000, wait_until="domcontentloaded")
            time.sleep(3)

            page_links = page.locator("a[href*='/pages/'], a[href*='/profile.php?id='], div[role='main'] a[role='link']")
            body_text = page.locator("body").inner_text(timeout=3000).lower()

            has_pages = False
            if "pages you manage" in body_text or "your pages" in body_text or "classic pages" in body_text:
                has_pages = True
            elif page_links.count() > 2:
                has_pages = True

            if has_pages:
                log("  ⏩ SKIPPED: Account already has an existing Facebook Page!")
                return False, "SKIPPED: Existing page found"
        except Exception as check_err:
            log(f"  ⚠️ Note checking existing pages: {check_err}")

    # 2. Navigate to Page Creation URL
    log(f"  🚩 Navigating to Facebook Page Creation page...")
    try:
        page.goto("https://www.facebook.com/pages/create/", timeout=35000, wait_until="domcontentloaded")
        time.sleep(3.5)
    except Exception:
        try:
            page.goto("https://www.facebook.com/pages/create/", timeout=30000, wait_until="domcontentloaded")
            time.sleep(3)
        except Exception as nav_err:
            log(f"  ❌ Navigation error to page creation: {nav_err}")
            return False, f"Navigation error: {nav_err}"

    # Prevent Chrome "Leave page?" unload dialog from ever blocking execution
    try:
        page.evaluate("window.onbeforeunload = null;")
    except Exception:
        pass

    dismiss_facebook_overlays(page)

    # 3. Fill Page Name
    log(f"  📝 Setting Page Name: '{page_name}'...")
    name_filled = False
    name_selectors = [
        "input[aria-label*='Page name']",
        "input[aria-label*='Page Name']",
        "input[aria-label*='Name']",
        "label:has-text('Page name') input",
        "input[type='text']"
    ]
    for sel in name_selectors:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=1500):
                loc.click()
                time.sleep(0.3)
                loc.press("Control+A")
                loc.press("Backspace")
                time.sleep(0.2)
                loc.type(page_name, delay=80)
                name_filled = True
                break
        except Exception:
            continue

    if not name_filled:
        log("  ❌ Could not locate Page Name input field.")
        return False, "Page Name input not found"

    time.sleep(1)

    # 4. Fill Category & Tokenize Category Pill
    log(f"  🏷️ Setting Category: '{category}'...")
    cat_filled = False
    cat_selectors = [
        "input[aria-label*='Category']",
        "input[aria-label*='category']",
        "label:has-text('Category') input"
    ]
    for sel in cat_selectors:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=2000):
                loc.click()
                time.sleep(0.5)
                loc.press("Control+A")
                loc.press("Backspace")
                time.sleep(0.3)

                # Type character by character to fire React combobox search listeners
                loc.type(category, delay=100)
                time.sleep(2.5)

                # Try clicking suggestion option pill from listbox overlay
                clicked_pill = False
                pill_selectors = [
                    "div[role='listbox'] div[role='option']",
                    "div[role='option']",
                    "ul[role='listbox'] li",
                    "div[role='menu'] div",
                    f"span:has-text('{category}')"
                ]
                for p_sel in pill_selectors:
                    try:
                        pill = page.locator(p_sel).first
                        if pill.is_visible(timeout=1500):
                            pill.click(force=True)
                            clicked_pill = True
                            time.sleep(1)
                            break
                    except Exception:
                        continue

                if not clicked_pill:
                    loc.press("ArrowDown")
                    time.sleep(0.5)
                    loc.press("Enter")
                    time.sleep(1)

                cat_filled = True
                break
        except Exception:
            continue

    if not cat_filled:
        log("  ⚠️ Category dropdown selection note, attempting default fallback...")

    time.sleep(1.5)

    # 5. Fill Bio if available
    if bio:
        log(f"  ✏️ Setting Bio: '{bio}'...")
        bio_selectors = [
            "textarea[aria-label*='Bio']",
            "textarea[aria-label*='Description']",
            "textarea"
        ]
        for sel in bio_selectors:
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=1000):
                    loc.click()
                    loc.fill(bio)
                    break
            except Exception:
                continue

    time.sleep(1.5)

    # 6. Click Create Page Button
    log("  🚀 Submitting Page Creation...")
    submit_clicked = False

    # Prevent unload dialog again
    try:
        page.evaluate("window.onbeforeunload = null;")
    except Exception:
        pass

    btn_selectors = [
        "div[aria-label='Create page']",
        "div[aria-label='Create Page']",
        "div[aria-label='Create page']:not([aria-disabled='true'])",
        "div[aria-label='Create Page']:not([aria-disabled='true'])",
        "button:has-text('Create page')",
        "button:has-text('Create Page')",
        "div[role='button']:has-text('Create page')",
        "div[role='button']:has-text('Create Page')",
        "div[role='button']:has-text('Create')",
        "span:has-text('Create page')",
        "span:has-text('Create Page')"
    ]
    for sel in btn_selectors:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=1500):
                btn.scroll_into_view_if_needed()
                time.sleep(0.3)
                btn.click(force=True)
                submit_clicked = True
                break
        except Exception:
            continue

    if not submit_clicked:
        # Fallback: Press Enter on page
        try:
            page.keyboard.press("Enter")
            submit_clicked = True
        except Exception:
            pass

    if not submit_clicked:
        log("  ❌ Could not click 'Create Page' button.")
        return False, "Submit button not found"

    log("  ⏳ Waiting for Facebook to process and finalize Page Creation...")
    creation_confirmed = False

    for wait_step in range(12):
        time.sleep(1)
        body_text_curr = ""
        try:
            body_text_curr = page.locator("body").inner_text(timeout=1500).lower()
        except Exception:
            pass

        curr_url = page.url.lower()

        if any(err_txt in body_text_curr for err_txt in ["created too many pages", "you have created too many pages", "limit reached", "try again later"]):
            log("  ⚠️ DETECTED FACEBOOK RATE LIMIT: 'You have created too many Pages recently. Please try again later.'")
            return False, "TOO_MANY_PAGES: You have created too many Pages recently. Please try again later."

        if any(w in body_text_curr for w in ["created", "profile picture", "cover photo", "customize", "contact info", "connect whatsapp", "next", "save"]):
            creation_confirmed = True
            break
        if "pages" in curr_url and "create" not in curr_url:
            creation_confirmed = True
            break

    if creation_confirmed:
        log(f"  🎉 Facebook Page '{page_name}' creation confirmed!")
        finish_facebook_page_creation_wizard(page, page_name, log)
        return True, f"Created Page '{page_name}'"

    # If any Leave page? popup shows up when finishing, auto-click Leave page or Stay on page to avoid blocking
    try:
        leave_btn = page.locator("button:has-text('Leave Page'), div[role='button']:has-text('Leave Page')").first
        if leave_btn.is_visible(timeout=1000):
            leave_btn.click(force=True)
    except Exception:
        pass

    log(f"  ✅ SUCCESS: Facebook Page '{page_name}' created successfully!")
    return True, f"Created Page '{page_name}'"


def dismiss_facebook_popup_notices(page: Any, log_func: Optional[Any] = None) -> bool:
    """
    Universal Facebook Popup & Overlay Auto-Dismissal:
    Safely closes ONLY restriction/warning popups ('What happened', 'We added restrictions', 'We removed a post', etc.)
    and NEVER closes the 'Switch profiles' confirmation dialog.
    """
    def log(msg: str) -> None:
        if log_func:
            log_func(msg)

    dismissed_any = False
    try:
        # JS deep check to close restriction popups safely without touching Switch profiles dialog
        js_closed = page.evaluate("""() => {
            const dialogs = Array.from(document.querySelectorAll('div[role="dialog"]'));
            let closedCount = 0;
            for (const dialog of dialogs) {
                if (!dialog || !dialog.innerText) continue;
                const text = dialog.innerText.toLowerCase();

                // CRITICAL SAFETY: Never close any profile switch confirmation dialog!
                if (text.includes("switch profiles") || text.includes("switch to ") || text.includes("see all profiles")) {
                    continue;
                }

                // Match warning, restriction, policy, and deactivated page info notices
                if (text.includes("what happened") || text.includes("we added restrictions") || text.includes("restrictions") || text.includes("we removed") || text.includes("community standards") || text.includes("policy") || text.includes("deactivated")) {
                    const buttons = Array.from(dialog.querySelectorAll('button, div[role="button"], div[aria-label="Close"], svg[aria-label="Close"], i[aria-label="Close"]'));
                    for (const btn of buttons) {
                        const btnText = (btn.innerText || '').trim().toLowerCase();
                        const aria = (btn.getAttribute('aria-label') || '').toLowerCase();
                        if (btnText === 'close' || btnText === 'ok' || aria === 'close' || btnText === 'dismiss') {
                            btn.click();
                            closedCount++;
                            break;
                        }
                    }
                    if (closedCount === 0 && buttons.length > 0) {
                        buttons[buttons.length - 1].click();
                        closedCount++;
                    }
                }
            }
            return closedCount > 0;
        }""")

        if js_closed:
            log("  🧹 Automatically dismissed Facebook restriction/notice popup.")
            time.sleep(1.2)
            dismissed_any = True

        if handle_facebook_automated_behavior_dismiss_screen(page, log_func):
            dismissed_any = True
    except Exception:
        pass

    return dismissed_any


def select_first_facebook_page(page: Any, log_func: Optional[Any] = None) -> bool:
    """
    If any Facebook Page is associated with the logged-in account:
    1. Pre-checks if session is ALREADY operating under a Page profile.
    2. Navigates to https://www.facebook.com/pages/?category=your_pages if on personal account.
    3. Clicks 3-dot (...) menu on 1st Page card inside main content grid and selects 'Switch Now'.
    4. Confirms switch by clicking blue 'Switch' button in 'Switch profiles' modal.
    """
    def log(msg: str) -> None:
        if log_func:
            log_func(msg)

    try:
        log("  🌐 Navigating to Facebook Pages list (https://www.facebook.com/pages/?category=your_pages)...")
        try:
            page.goto("https://www.facebook.com/pages/?category=your_pages", timeout=12000, wait_until="domcontentloaded")
            time.sleep(random.uniform(2.0, 3.2))
        except Exception as e:
            log(f"  ⚠️ Page navigation timed out or encountered note: {e}")

        # Auto-dismiss any Facebook warning/notice popup overlays before starting
        dismiss_facebook_popup_notices(page, log_func=log)

        # Check if account is ALREADY operating under an active Page profile (showing 'Create post' / 'Promote' buttons)
        try:
            curr_url = page.url.lower()
            body_text = page.locator("body").inner_text(timeout=2000).lower()

            has_already_active_page_card = False
            for s in [
                'div[role="main"] a:has-text("Create post")',
                'div[role="main"] div[role="button"]:has-text("Create post")',
                'div[role="main"] button:has-text("Create post")',
                'div[role="main"] button:has-text("Promote")',
                'div[role="main"] a:has-text("Promote")'
            ]:
                if page.locator(s).count() > 0:
                    has_already_active_page_card = True
                    break

            if has_already_active_page_card or ("create post" in body_text and "promote" in body_text and ("manages" in body_text or "pages" in body_text)):
                log("  ✅ Account is ALREADY operating under an active Facebook Page profile!")
                return True

            has_switch_btn = False
            for s in [
                'div[role="main"] div[aria-label*="Switch"]',
                'div[role="main"] button:has-text("Switch")',
                'div[role="main"] div[role="button"]:has-text("...")',
                'div[role="main"] a:has-text("Switch")',
                'div[role="main"] div[aria-label*="More"]',
                'div[role="main"] div[aria-label="More"]'
            ]:
                if page.locator(s).count() > 0:
                    has_switch_btn = True
                    break

            no_page_indicators = [
                "you don't manage any pages",
                "you don't have any pages",
                "deactivated and deleted pages",
                "you have no pages",
                "create a page",
                "create new page",
                "discover pages"
            ]

            is_discover_page = "category=top" in curr_url or "discover pages" in body_text
            has_no_page_text = any(ind in body_text for ind in no_page_indicators)
            has_managed_pages_heading = "pages you manage" in body_text or "your pages" in body_text or "manages" in body_text

            if (is_discover_page or has_no_page_text or not has_managed_pages_heading) and not has_switch_btn:
                log("  ❌ No active Facebook Page found on this account (Redirected to Discover Pages / No managed pages exist).")
                return False
        except Exception as check_err:
            log(f"  ⚠️ Page pre-check note: {check_err}")

        # STEP 1: Direct 'Switch Now' button or 3-dot menu on 1st Page card inside div[role="main"]
        log("  🚩 Locating 1st Page card 3-dot (...) menu and 'Switch Now' option...")

        switched = False

        # Attempt A: Click 3-dot (...) button strictly on 1st page card in main grid (NOT top-right avatar menu)
        dots_selectors = [
            'div[role="main"] div[aria-label*="More"]',
            'div[role="main"] div[aria-label*="more"]',
            'div[role="main"] div[role="button"][aria-label*="More"]',
            'div[role="main"] div[role="button"]:has-text("...")',
            'div[role="main"] button:has-text("...")',
            'div[role="main"] div[aria-label="More"]'
        ]

        for d_sel in dots_selectors:
            try:
                dots = page.locator(d_sel).all()
                if dots:
                    for dot_btn in dots:
                        if dot_btn.is_visible(timeout=1000):
                            try:
                                dot_btn.hover()
                                time.sleep(random.uniform(0.3, 0.6))
                            except Exception:
                                pass

                            dot_btn.click()
                            log("  🖱️ Clicked 3-dot (...) menu button.")
                            time.sleep(random.uniform(1.2, 2.2))

                            # Check for 'Switch Now' item in dropdown popup menu
                            switch_now_selectors = [
                                'span:has-text("Switch Now")',
                                'div[role="menuitem"]:has-text("Switch Now")',
                                'div[role="button"]:has-text("Switch Now")',
                                'div:has-text("Switch Now")',
                                'span:has-text("Switch")'
                            ]
                            for sn_sel in switch_now_selectors:
                                try:
                                    sn_item = page.locator(sn_sel).first
                                    if sn_item and sn_item.is_visible(timeout=1200):
                                        try:
                                            sn_item.hover()
                                            time.sleep(random.uniform(0.3, 0.6))
                                        except Exception:
                                            pass
                                        sn_item.click()
                                        log("  👉 Clicked 'Switch Now' from 3-dot menu!")
                                        time.sleep(random.uniform(2.0, 3.5))
                                        switched = True
                                        break
                                except Exception:
                                    continue

                            if switched:
                                break
            except Exception:
                continue

            if switched:
                break

        # Attempt B: Direct 'Switch' button on 1st page card if visible
        if not switched:
            direct_switch_selectors = [
                'div[role="main"] div[aria-label*="Switch"]',
                'div[role="main"] div[role="button"]:has-text("Switch")',
                'div[role="main"] button:has-text("Switch")',
                'div[role="main"] a:has-text("Switch Now")'
            ]
            for ds_sel in direct_switch_selectors:
                try:
                    ds_btn = page.locator(ds_sel).first
                    if ds_btn and ds_btn.is_visible(timeout=1500):
                        try:
                            ds_btn.hover()
                            time.sleep(random.uniform(0.3, 0.6))
                        except Exception:
                            pass
                        ds_btn.click()
                        log("  👉 Clicked 'Switch' button on 1st Page card!")
                        time.sleep(random.uniform(2.0, 3.5))
                        switched = True
                        break
                except Exception:
                    continue

        # Handle modal confirmation popup ('Switch' button inside 'Switch profiles' dialog)
        if switched:
            time.sleep(random.uniform(1.5, 2.5))
            log("  ⏳ Handling 'Switch profiles' confirmation popup...")

            confirm_switch_selectors = [
                'div[role="dialog"] div[role="button"]:has-text("Switch")',
                'div[role="dialog"] button:has-text("Switch")',
                'div[role="dialog"] span:has-text("Switch")',
                'div[aria-label="Switch profiles"] div[role="button"]:has-text("Switch")',
                'div[aria-label="Switch profiles"] button:has-text("Switch")',
                'div[role="dialog"] div[aria-label="Switch"]',
                'div[role="dialog"] button[aria-label="Switch"]'
            ]

            confirmed = False
            for cs in confirm_switch_selectors:
                try:
                    c_btn = page.locator(cs).first
                    if c_btn and c_btn.is_visible(timeout=2500):
                        try:
                            c_btn.hover()
                            time.sleep(random.uniform(0.3, 0.6))
                        except Exception:
                            pass
                        c_btn.click(force=True)
                        log("  👉 Clicked blue 'Switch' button in 'Switch profiles' popup!")
                        time.sleep(random.uniform(4.0, 6.0))
                        confirmed = True
                        break
                except Exception:
                    continue

            if not confirmed:
                try:
                    js_clicked = page.evaluate("""() => {
                        const dialogs = Array.from(document.querySelectorAll('div[role="dialog"]'));
                        for (const dialog of dialogs) {
                            const text = (dialog.innerText || '').toLowerCase();
                            if (text.includes("switch profiles") || text.includes("switch to ")) {
                                const buttons = Array.from(dialog.querySelectorAll('div[role="button"], button, span'));
                                for (const b of buttons) {
                                    const t = (b.innerText || '').trim();
                                    if (t === 'Switch' || t.toLowerCase() === 'switch') {
                                        b.click();
                                        return true;
                                    }
                                }
                            }
                        }
                        return false;
                    }""")
                    if js_clicked:
                        log("  👉 Clicked blue 'Switch' button via JS in 'Switch profiles' popup!")
                        time.sleep(random.uniform(4.0, 6.0))
                except Exception:
                    pass

            log("  ✅ Successfully selected & switched to 1st Facebook Page!")
            return True

        log("  ℹ️ No created Facebook Page card or switch button was found on this account.")
        return False
    except Exception as err:
        log(f"  ⚠️ Note while checking Facebook Page: {err}")
        return False


def switch_back_to_main_profile(page: Any, log_func: Optional[Any] = None) -> bool:
    """
    Switch session back from a Facebook Page profile to the Main Personal Facebook Profile (ID).
    """
    def log(msg: str) -> None:
        if log_func:
            log_func(msg)

    if not is_already_on_facebook_page(page):
        log("  ✅ Session is already operating under Main Facebook Personal Profile (ID).")
        return True

    log("  🔄 Switching profile back to Main Facebook Personal Profile (ID)...")
    try:
        page.goto("https://www.facebook.com/", timeout=20000, wait_until="domcontentloaded")
        time.sleep(2.5)

        prof_menu = page.locator('div[aria-label="Your profile"], div[aria-label="Account controls and settings"], svg[aria-label="Your profile"]').first
        if prof_menu and prof_menu.is_visible(timeout=2500):
            prof_menu.click(force=True)
            time.sleep(2)

            see_all = page.locator('span:has-text("See all profiles"), div[role="button"]:has-text("See all profiles")').first
            if see_all and see_all.is_visible(timeout=1500):
                see_all.click(force=True)
                time.sleep(2)

            # Click on 1st item in profile menu (which is always Main User Profile)
            switched = page.evaluate("""() => {
                const dialogs = Array.from(document.querySelectorAll('div[role="dialog"], div[role="menu"]'));
                for (const dialog of dialogs) {
                    const rawItems = Array.from(dialog.querySelectorAll('div[role="button"], div[tabindex="0"]'));
                    const valid = rawItems.filter(i => {
                        const t = (i.innerText || "").toLowerCase();
                        return t && !t.includes("select profile") && !t.includes("see all") && !t.includes("create page") && !t.includes("log out");
                    });
                    if (valid.length > 0) {
                        valid[0].click(); // Main FB Profile (index 0)
                        return true;
                    }
                }
                return false;
            }""")
            if switched:
                time.sleep(4)
                try:
                    c_btn = page.locator('div[role="dialog"] div[role="button"]:has-text("Switch")').first
                    if c_btn.is_visible(timeout=2000):
                        c_btn.click(force=True)
                        time.sleep(3)
                except Exception:
                    pass
                log("  ✅ Successfully switched back to Main Facebook Personal Profile (ID)!")
    except Exception as err:
        log(f"  ⚠️ Switch back to main profile note: {err}")
    return False


import sys
from pathlib import Path

# Smart resolution of 03_Automation_Bots directory
bot_dirs = [
    Path(__file__).resolve().parent.parent.parent / "03_Automation_Bots",
    Path(__file__).resolve().parent.parent / "03_Automation_Bots",
    Path(__file__).resolve().parent / "03_Automation_Bots"
]
for bd in bot_dirs:
    if bd.exists() and str(bd) not in sys.path:
        sys.path.append(str(bd))

try:
    from fb_bulk_login_bot import BulkLoginThread
except Exception:
    class BulkLoginThread(QThread):
        """Fallback empty definition if bot module is missing."""
        log_emitted = Signal(str)
        progress_updated = Signal(int, int)
        finished_signal = Signal(bool, str, str)
        def __init__(self, *args, **kwargs):
            super().__init__(kwargs.get('parent', None))
        def run(self):
            pass


class PageCreatorThread(QThread):
    """
    Background execution thread performing automated Facebook Page Creation across target profile group.
    Supports mode='skip' (Skip if page exists) and mode='force' (Force create all).
    """

    log_emitted = Signal(str)
    progress_updated = Signal(int, int) # current, total
    finished_signal = Signal(bool, str, str) # success, message, report_csv_path

    def __init__(
        self,
        profile_mgr: Any,
        profiles_list: List[Dict[str, Any]],
        excel_page_rows: Optional[List[Dict[str, Any]]] = None,
        default_page_name: str = "",
        default_category: str = "Digital Creator",
        default_bio: str = "",
        mode: str = "skip",
        creation_mode: str = "direct",
        auto_delete_on_fail: bool = True,
        max_concurrent_browsers: int = 1,
        headless: bool = False,
        parent: Optional[Any] = None,
        **kwargs: Any
    ) -> None:
        super().__init__(parent)
        self.profile_mgr = profile_mgr
        self.profiles_list = profiles_list
        self.excel_page_rows = excel_page_rows or []
        self.default_page_name = default_page_name
        self.default_category = default_category
        self.default_bio = default_bio
        self.mode = mode.lower() if isinstance(mode, str) else "skip"
        self.creation_mode = creation_mode.lower() if isinstance(creation_mode, str) else "direct"
        self.auto_delete_on_fail = auto_delete_on_fail
        self.max_concurrent_browsers = max(1, min(15, max_concurrent_browsers))
        self.headless = headless

    def _process_single_page_creation(
        self,
        idx: int,
        total_profiles: int,
        pdata: Dict[str, Any]
    ) -> Tuple[bool, bool, Optional[Dict[str, Any]]]:
        """Worker task for creating a page for a single profile in thread pool."""
        pid = pdata["id"]
        pnum = pdata.get("number", idx)
        pname = pdata.get("name", f"Profile {pnum}")

        row_dict = self.excel_page_rows[idx - 1] if idx <= len(self.excel_page_rows) else {}
        page_name, category, bio = extract_page_creation_fields(
            row_dict,
            idx,
            default_name=self.default_page_name,
            default_cat=self.default_category,
            default_bio=self.default_bio
        )

        self.log_emitted.emit(f"\n🚩 [{idx}/{total_profiles}] Processing Profile {pnum} ({pname}). Target Page: '{page_name}'...")
        p_folder = self.profile_mgr.get_profile_folder(pid)

        try:
            with sync_playwright() as p:
                args = [
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-background-networking",
                    "--test-type",
                    "--disable-infobars",
                    "--disable-notifications",
                    "--deny-permission-prompts",
                    "--disable-popup-blocking",
                    "--no-sandbox",
                    "--lang=en-US",
                    "--disable-save-password-bubble",
                    "--password-store=basic"
                ]

                chrome_exe = get_chrome_executable_path()
                launch_kwargs = {
                    "user_data_dir": str(p_folder.resolve()),
                    "headless": self.headless,
                    "user_agent": pdata.get("user_agent", None),
                    "locale": "en-US",
                    "extra_http_headers": {"Accept-Language": "en-US,en;q=0.9"},
                    "viewport": {"width": 1280, "height": 800},
                    "args": args
                }
                if chrome_exe and os.path.exists(chrome_exe):
                    launch_kwargs["executable_path"] = chrome_exe

                context = p.chromium.launch_persistent_context(**launch_kwargs)
                configure_antidetect_context(context, pdata)

                page = context.pages[0] if context.pages else context.new_page()
                inject_session_cookies_if_needed(context, pdata)

                try:
                    page.goto("https://www.facebook.com/", timeout=15000, wait_until="commit")
                except Exception:
                    pass
                time.sleep(0.3)

                is_logged_in, login_msg = check_facebook_login_status(page)
                if not is_logged_in:
                    self.log_emitted.emit(f"  ⚠️ [{pnum}] Session is LOGGED OUT ({login_msg}). Attempting automatic re-login...")
                    relogin_ok = attempt_profile_relogin(
                        page=page,
                        context=context,
                        profile_data=pdata,
                        log_func=lambda text: self.log_emitted.emit(text)
                    )
                    if not relogin_ok:
                        if self.auto_delete_on_fail:
                            self.log_emitted.emit(f"  ❌ [{pnum}] SKIPPED & PURGED: Re-login failed. Purging profile directory & deleting from database...")
                            if context:
                                context.close()
                            self.profile_mgr.delete_profile(pid)
                        else:
                            self.log_emitted.emit(f"  ⚠️ [{pnum}] SKIPPED: Re-login failed (Auto-Delete is OFF). Profile retained in database.")
                            if context:
                                context.close()
                        return False, False, {
                            "Profile_Number": pnum,
                            "Profile_Name": pname,
                            "Target_Page_Name": page_name,
                            "Failure_Reason": "Account logged out / Re-login failed",
                            "Timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                        }

                if self.creation_mode == "bm":
                    self.log_emitted.emit("  🏢 [Phase 2] Navigating to Business Manager...")
                    try:
                        page.goto("https://business.facebook.com/", timeout=30000, wait_until="domcontentloaded")
                        time.sleep(3.0)
                    except Exception:
                        pass
                else:
                    self.log_emitted.emit("  🚩 [Phase 2] Navigating to Facebook Page Creation portal...")
                    try:
                        page.goto("https://www.facebook.com/pages/create/", timeout=30000, wait_until="domcontentloaded")
                        time.sleep(3.0)
                    except Exception:
                        pass

                self.log_emitted.emit("  ✅ [Phase 2 Complete] Successfully navigated to Page Creation Portal!")
                self.log_emitted.emit("  ℹ️ Standing by as per plan (form filling will be executed when instructed in Phase 3).")

                if not self.headless:
                    self.log_emitted.emit("  👁️ [Test Mode Visual Pause - 30s] Holding 30s inspection pause...")
                    for pause_i in range(30, 0, -1):
                        time.sleep(1)

                context.close()
                return True, False, None
        except Exception as err:
            status_msg = f"Execution Error: {str(err)}"
            self.log_emitted.emit(f"  ❌ Error for profile {pnum}: {err}")
            return False, False, {
                "Profile_Number": pnum,
                "Profile_Name": pname,
                "Target_Page_Name": page_name,
                "Failure_Reason": status_msg,
                "Timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            }

    def run(self) -> None:
        total_profiles = len(self.profiles_list)
        if total_profiles == 0:
            self.finished_signal.emit(False, "No profiles selected for Facebook Page creation.", "")
            return

        self.log_emitted.emit(f"🚀 Starting Multi-Thread Automated Facebook Page Creation for {total_profiles} profiles...")
        self.log_emitted.emit(f"⚡ Parallel Execution: {self.max_concurrent_browsers} Concurrent Browsers")

        success_count = 0
        skipped_count = 0
        failed_records = []
        completed = 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_concurrent_browsers) as executor:
            futures = {
                executor.submit(self._process_single_page_creation, idx, total_profiles, pdata): (idx, pdata)
                for idx, pdata in enumerate(self.profiles_list, start=1)
            }

            for fut in concurrent.futures.as_completed(futures):
                completed += 1
                self.progress_updated.emit(completed, total_profiles)
                try:
                    is_ok, is_skipped, fail_info = fut.result()
                    if is_ok:
                        success_count += 1
                    elif is_skipped:
                        skipped_count += 1
                    elif fail_info:
                        failed_records.append(fail_info)
                except Exception as exc:
                    self.log_emitted.emit(f"⚠️ Worker task error on page creation: {exc}")

        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report_path = REPORTS_DIR / "page_creation_report.csv"
        summary_msg = f"Page Creation Batch Complete! Created: {success_count}, Skipped: {skipped_count}, Failed: {len(failed_records)} / Total {total_profiles} profiles."
        self.finished_signal.emit(True, summary_msg, str(report_path.resolve()) if failed_records else "")


class OpenProfileLauncherThread(QThread):
    """
    Background worker thread to open a browser profile window with active session guarantee:
    1. Opens browser profile non-headlessly (headless=False).
    2. Inject stored session cookies if needed.
    3. Auto-restores session via stored credentials if logged out.
    4. Keeps browser window open for user interaction.
    """
    log_emitted = Signal(str)
    finished_signal = Signal(bool, str)

    def __init__(self, profile_mgr: Any, profile_id: str, parent: Optional[Any] = None) -> None:
        super().__init__(parent)
        self.profile_mgr = profile_mgr
        self.profile_id = profile_id

    def run(self) -> None:
        p_data = self.profile_mgr.get_profile_by_id(self.profile_id)
        if not p_data:
            self.finished_signal.emit(False, "Profile data not found in database.")
            return

        p_num = p_data.get("number", "Profile")
        p_folder = self.profile_mgr.get_profile_folder(self.profile_id)
        user_agent_val = p_data.get("user_agent") or generate_random_user_agent()

        self.log_emitted.emit(f"🚀 Opening [{p_num}] with active Facebook session guarantee...")

        try:
            with sync_playwright() as p:
                args = [
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-background-networking",
                    "--disable-notifications",
                    "--disable-popup-blocking",
                    "--deny-permission-prompts",
                    "--test-type",
                    "--disable-infobars",
                    "--no-sandbox",
                    "--lang=en-US",
                    "--disable-save-password-bubble",
                    "--password-store=basic"
                ]

                chrome_exe = get_chrome_executable_path()
                launch_kwargs = {
                    "user_data_dir": str(p_folder.resolve()),
                    "headless": False,
                    "user_agent": user_agent_val,
                    "locale": "en-US",
                    "extra_http_headers": {"Accept-Language": "en-US,en;q=0.9"},
                    "viewport": {"width": 1280, "height": 800},
                    "permissions": [],
                    "args": args,
                    "ignore_default_args": ["--enable-automation"]
                }
                if chrome_exe and os.path.exists(chrome_exe):
                    launch_kwargs["executable_path"] = chrome_exe

                context = p.chromium.launch_persistent_context(**launch_kwargs)
                page = context.pages[0] if context.pages else context.new_page()

                inject_session_cookies_if_needed(context, p_data)

                page.goto("https://www.facebook.com/", timeout=40000, wait_until="domcontentloaded")
                time.sleep(2.0)

                is_ok, _ = check_facebook_login_status(page, context)
                if not is_ok:
                    self.log_emitted.emit(f"🔑 Session inactive for [{p_num}]. Auto-restoring session...")
                    attempt_profile_relogin(page, context, p_data, log_func=lambda msg: self.log_emitted.emit(msg))

                self.finished_signal.emit(True, f"Profile [{p_num}] opened with active session!")

                # Keep browser process alive as long as user keeps window open
                while len(context.pages) > 0:
                    try:
                        time.sleep(1.0)
                        _ = page.url
                    except Exception:
                        break
        except Exception as err:
            self.finished_signal.emit(False, f"Launch Error: {err}")


class SingleProfileReloginThread(QThread):
    """
    Background worker thread to perform 1-click manual Re-login for a specific browser profile.
    Uses stored Cookie first, then stored UID + Password.
    """
    log_emitted = Signal(str)
    finished_signal = Signal(bool, str) # success, message

    def __init__(self, profile_mgr: Any, profile_id: str, parent: Optional[Any] = None) -> None:
        super().__init__(parent)
        self.profile_mgr = profile_mgr
        self.profile_id = profile_id

    def run(self) -> None:
        p_data = self.profile_mgr.get_profile_by_id(self.profile_id)
        if not p_data:
            self.finished_signal.emit(False, "Profile data not found in database.")
            return

        p_num = p_data.get("number", "Profile")
        p_folder = self.profile_mgr.get_profile_folder(self.profile_id)
        p_data["user_data_dir"] = str(p_folder.resolve())
        user_agent_val = p_data.get("user_agent") or generate_random_user_agent()

        self.log_emitted.emit(f"🔑 Starting 1-Click Re-login for [{p_num}]...")

        try:
            # 1. Obtain native BrowserLauncher instance
            launcher = None
            if self.parent() and hasattr(self.parent(), "browser_launcher"):
                launcher = self.parent().browser_launcher
            else:
                try:
                    from browser import BrowserLauncher
                except ImportError:
                    try:
                        from core.browser import BrowserLauncher
                    except ImportError:
                        BrowserLauncher = None
                if BrowserLauncher:
                    launcher = BrowserLauncher(self)

            if not launcher:
                self.finished_signal.emit(False, "Could not initialize BrowserLauncher.")
                return

            # 2. Launch profile natively if not already running
            if not launcher.is_running(self.profile_id):
                chrome_exe = launcher.get_default_browser_executable()
                success, msg = launcher.launch_profile(chrome_exe, p_folder, p_data)
                if not success:
                    self.finished_signal.emit(False, f"Could not launch browser: {msg}")
                    return
                time.sleep(2.5)

            # 3. Calculate CDP port for this profile
            raw_num = str(p_data.get("number", "1")).replace("Profile", "").replace("#", "").strip().lstrip("0") or "1"
            n_val = int(raw_num) if raw_num.isdigit() else 1
            cdp_port = 9200 + (n_val % 500)
            cdp_url = f"http://127.0.0.1:{cdp_port}"

            # 4. Connect Playwright over CDP to active profile window
            pw_instance = sync_playwright().start()
            context = None
            for _attempt in range(12):
                try:
                    browser_cdp = pw_instance.chromium.connect_over_cdp(cdp_url)
                    if browser_cdp and browser_cdp.contexts:
                        context = browser_cdp.contexts[0]
                        break
                except Exception:
                    time.sleep(0.5)

            if not context:
                self.finished_signal.emit(False, f"Could not connect Playwright to profile window on port {cdp_port}")
                return

            page = context.pages[0] if context.pages else context.new_page()

            # 5. Perform smart 1-Click FB Auto Re-login (FBRL)
            relogin_ok = False
            relogin_msg = ""
            try:
                import sys
                from pathlib import Path
                sp_candidates = [
                    Path(__file__).resolve().parent.parent.parent / "06_Script_Store" / "05_FB_Re_Login",
                    Path(__file__).resolve().parent.parent / "06_Script_Store" / "05_FB_Re_Login",
                    Path.cwd() / "06_Script_Store" / "05_FB_Re_Login"
                ]
                for scp in sp_candidates:
                    if scp.exists() and str(scp.resolve()) not in sys.path:
                        sys.path.insert(0, str(scp.resolve()))

                from fb_relogin_engine import execute_relogin
                relogin_ok, relogin_msg = execute_relogin(
                    profile_data=p_data,
                    profile_mgr=self.profile_mgr,
                    log_func=lambda text: self.log_emitted.emit(text),
                    user_data_dir=str(p_folder.resolve())
                )
            except Exception as eng_err:
                self.log_emitted.emit(f"  ℹ️ Using native fallback re-login engine ({eng_err})")
                relogin_ok = attempt_profile_relogin(
                    page=page,
                    context=context,
                    profile_data=p_data,
                    log_func=lambda text: self.log_emitted.emit(text)
                )
                relogin_msg = f"✅ Re-login SUCCESSFUL for [{p_num}]! Saved active session cookies to profile database." if relogin_ok else f"❌ Re-login Failed for [{p_num}]. Stored credentials invalid or account locked."

            if relogin_ok:
                try:
                    new_cookies = context.cookies()
                    if new_cookies:
                        ck_parts = [f"{c['name']}={c['value']}" for c in new_cookies if c.get("name") and c.get("value")]
                        ck_str = "; ".join(ck_parts)
                        self.profile_mgr.update_profile(
                            self.profile_id,
                            cookie=ck_str,
                            user_agent=user_agent_val,
                            start_url="https://www.facebook.com"
                        )
                        # Immediately persist cookies to Chromium SQLite Cookies DB & update sr_cookie_injector extension payload
                        try:
                            from browser import inject_cookies_to_chromium_profile, create_cookie_injector_extension
                            inject_cookies_to_chromium_profile(p_folder, ck_str)
                            updated_p = self.profile_mgr.get_profile_by_id(self.profile_id)
                            if updated_p:
                                create_cookie_injector_extension(p_folder, updated_p)
                        except Exception:
                            try:
                                from core.browser import inject_cookies_to_chromium_profile, create_cookie_injector_extension
                                inject_cookies_to_chromium_profile(p_folder, ck_str)
                                updated_p = self.profile_mgr.get_profile_by_id(self.profile_id)
                                if updated_p:
                                    create_cookie_injector_extension(p_folder, updated_p)
                            except Exception:
                                pass
                except Exception:
                    pass

                self.finished_signal.emit(True, relogin_msg or f"✅ Re-login SUCCESSFUL for [{p_num}]! Saved active session cookies to profile database.")
            else:
                self.finished_signal.emit(False, relogin_msg or f"❌ Re-login Failed for [{p_num}]. Stored credentials invalid or account locked.")
        except Exception as err:
            self.finished_signal.emit(False, f"Re-login Execution Error: {err}")


class OpenProfileInteractiveThread(QThread):
    """
    Background worker thread to open a profile interactively with automatic database cookie injection,
    ensuring 100% logged-in session persistence matching Re-Login functionality.
    """
    log_emitted = Signal(str)
    finished_signal = Signal(bool, str)

    def __init__(self, profile_mgr: Any, profile_id: str, parent: Optional[Any] = None) -> None:
        super().__init__(parent)
        self.profile_mgr = profile_mgr
        self.profile_id = profile_id

    def run(self) -> None:
        p_data = self.profile_mgr.get_profile_by_id(self.profile_id)
        if not p_data:
            self.finished_signal.emit(False, "Profile data not found in database.")
            return

        p_num = p_data.get("number", "Profile")
        p_folder = self.profile_mgr.get_profile_folder(self.profile_id)
        user_agent_val = p_data.get("user_agent")
        if not user_agent_val:
            user_agent_val = generate_random_user_agent()
            try:
                self.profile_mgr.update_profile(self.profile_id, {"user_agent": user_agent_val})
            except Exception:
                pass

        self.log_emitted.emit(f"🚀 Opening [{p_num}] with active session cookies...")

        try:
            pw_instance = sync_playwright().start()
            args = [
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-background-networking",
                "--disable-notifications",
                "--disable-popup-blocking",
                "--deny-permission-prompts",
                "--test-type",
                "--disable-infobars",
                "--no-sandbox",
                "--lang=en-US",
                "--disable-save-password-bubble",
                "--password-store=basic",
                "--disable-blink-features=AutomationControlled",
                "--force-webrtc-ip-handling-policy=disable_non_proxied_udp"
            ]

            chrome_exe = get_chrome_executable_path()
            launch_kwargs = {
                "user_data_dir": str(p_folder.resolve()),
                "headless": False,
                "user_agent": user_agent_val,
                "locale": "en-US",
                "extra_http_headers": {"Accept-Language": "en-US,en;q=0.9"},
                "viewport": None,
                "permissions": [],
                "args": args,
                "ignore_default_args": ["--enable-automation"]
            }
            if chrome_exe and os.path.exists(chrome_exe):
                launch_kwargs["executable_path"] = chrome_exe

            context = pw_instance.chromium.launch_persistent_context(**launch_kwargs)

            inject_session_cookies_if_needed(context, p_data)

            page = context.pages[0] if context.pages else context.new_page()
            start_url = p_data.get("start_url") or "https://www.facebook.com/"
            try:
                page.goto(start_url, timeout=25000, wait_until="domcontentloaded")
            except Exception:
                pass

            try:
                page.bring_to_front()
            except Exception:
                pass

            # Extract & persist active session cookies back to database
            try:
                active_cookies = context.cookies()
                if active_cookies:
                    c_str = "; ".join([f"{c['name']}={c['value']}" for c in active_cookies if "facebook.com" in c.get("domain", "")])
                    if c_str and len(c_str) > 20:
                        self.profile_mgr.update_profile(self.profile_id, {"cookie": c_str})
            except Exception:
                pass

            try:
                page.bring_to_front()
            except Exception:
                pass

            self.finished_signal.emit(True, f"✅ Profile [{p_num}] opened successfully with active session!")
        except Exception as err:
            self.finished_signal.emit(False, f"Error opening profile: {err}")


def handle_facebook_profile_continue_screen(page: Any, password: str, log_func: Optional[Any] = None) -> bool:
    """
    Detects and handles Facebook's 'Continue' profile selection screen (as shown in user screenshot).
    Supports English ('Continue'), French ('Continuer'), Spanish ('Continuar'), and multi-lingual buttons.
    Clicks 'Continue'/'Continuer', types the password if requested, and submits.
    Returns True if successfully handled/bypassed, False otherwise.
    """
    def log(msg: str) -> None:
        if log_func:
            log_func(msg)
        else:
            print(msg)

    try:
        # CRITICAL SAFETY CHECK: If URL is 2FA, checkpoint, or authentication page, return False immediately!
        curr_url = page.url.lower()
        if any(k in curr_url for k in ["two_step", "2fa", "authentication", "checkpoint", "security", "login", "recover", "challenge"]):
            return False

        # CRITICAL SAFETY CHECK: If standard email input is visible, this is a normal login page, NOT a profile continue screen!
        email_inp_check = page.locator("input[name='email'], #email, input[type='email'], input[data-testid='royal_email']").first
        if email_inp_check.is_visible(timeout=1000):
            return False

        # 1. Multi-lingual button selectors for 'Continue' / 'Continuer' / primary profile button
        continue_selectors = [
            "button:has-text('Continue')",
            "div[role='button']:has-text('Continue')",
            "button:has-text('Continuer')",
            "div[role='button']:has-text('Continuer')",
            "button:has-text('Continuar')",
            "div[role='button']:has-text('Continuar')",
            "button:has-text('Weiter')",
            "div[role='button']:has-text('Weiter')",
            "a:has-text('Continue')",
            "a:has-text('Continuer')",
            "a:has-text('Continuar')"
        ]

        continue_btn = None
        for sel in continue_selectors:
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=1200):
                    continue_btn = loc
                    break
            except Exception:
                continue

        if continue_btn:
            log("  👉 Detected Profile Selection / Continue screen. Clicking blue Continue button...")
            continue_btn.click(force=True)
            time.sleep(random.uniform(2.5, 4.0))

            # Verify if clicking Continue restored full Home Feed session
            ok, _ = check_facebook_login_status(page)
            if ok:
                log("  ✅ Successfully restored active Facebook session via Continue button!")
                return True

            # Check if Password input prompt appears after clicking Continue
            pass_inp = page.locator("input[name='pass'], #pass, input[type='password']").first
            if pass_inp.is_visible(timeout=2500) and password:
                log("  🔑 Password prompt appeared after Continue. Entering password...")
                pass_inp.click()
                time.sleep(0.3)
                pass_inp.fill("")
                pass_inp.press_sequentially(password, delay=random.randint(40, 90))
                time.sleep(0.5)
                pass_inp.press("Enter")
                time.sleep(random.uniform(4.5, 7.0))

            ok, _ = check_facebook_login_status(page)
            if ok:
                log("  ✅ Successfully logged in via Continue screen!")
                return True

        # 2. Check if Password input prompt is directly visible on profile screen
        pass_inp_direct = page.locator("input[name='pass'], #pass, input[type='password']").first
        if pass_inp_direct.is_visible(timeout=1000) and password:
            log("  🔑 Direct Password prompt visible on profile screen. Entering password...")
            pass_inp_direct.click()
            time.sleep(0.3)
            pass_inp_direct.fill("")
            pass_inp_direct.press_sequentially(password, delay=random.randint(40, 90))
            time.sleep(0.5)
            pass_inp_direct.press("Enter")
            time.sleep(random.uniform(4.5, 7.0))
            ok, _ = check_facebook_login_status(page)
            if ok:
                log("  ✅ Successfully logged in via direct password field!")
                return True
    except Exception as err:
        log(f"  ⚠️ Note handling Continue screen: {err}")
    return False


def handle_facebook_automated_behavior_dismiss_screen(page: Any, log_func: Optional[Any] = None) -> bool:
    """
    Detects and dismisses Facebook's 'We suspect automated behavior on your account' notice screen.
    Clicks 'Dismiss' / 'Ignorer' / 'Descartar' button, waits for redirection, and returns True if successfully dismissed.
    """
    def log(msg: str) -> None:
        if log_func:
            log_func(msg)
        else:
            print(msg)

    try:
        url_lower = page.url.lower()
        body_text = ""
        try:
            body_text = page.locator("body").inner_text(timeout=1000).lower()
        except Exception:
            pass

        is_automated_notice = (
            "automated behavior" in body_text or
            "suspect automated behavior" in body_text or
            "temporarily restricted" in body_text or
            "terms of use" in body_text or
            "checkpoint" in url_lower
        )

        if is_automated_notice:
            dismiss_selectors = [
                "button:has-text('Dismiss')",
                "div[role='button']:has-text('Dismiss')",
                "a:has-text('Dismiss')",
                "button:has-text('Ignorer')",
                "div[role='button']:has-text('Ignorer')",
                "button:has-text('Descartar')",
                "div[role='button']:has-text('Descartar')",
                "button:has-text('OK')",
                "div[role='button']:has-text('OK')",
                "button:has-text('Continue')",
                "div[role='button']:has-text('Continue')"
            ]

            for sel in dismiss_selectors:
                try:
                    btn = page.locator(sel).first
                    if btn.is_visible(timeout=1200):
                        log("  🛡️ Detected 'We suspect automated behavior on your account' notice screen!")
                        log("  👆 Clicking 'Dismiss' button to bypass security notice...")
                        btn.hover()
                        time.sleep(0.4)
                        btn.click(force=True)
                        time.sleep(random.uniform(3.0, 5.0))

                        new_url = page.url.lower()
                        if "checkpoint" not in new_url or "facebook.com" in new_url:
                            log("  ✅ 'Dismiss' clicked successfully! Account redirected to active feed.")
                            return True
                except Exception:
                    continue
    except Exception as err:
        log(f"  ⚠️ Error handling automated behavior screen: {err}")

    return False


def wait_and_verify_no_checkpoint(page: Any, context: Optional[Any] = None, wait_seconds: float = 4.5) -> Tuple[bool, str]:
    """
    Watches page state & URL for wait_seconds after login to detect delayed Facebook Checkpoint / Account Lock redirects.
    Returns (True, "Clean session") if no checkpoint detected, or (False, reason) if redirected to /checkpoint/ or locked screen.
    """
    start_t = time.time()
    while time.time() - start_t < wait_seconds:
        try:
            curr_url = page.url.lower()
            try:
                js_url = str(page.evaluate("window.location.href")).lower()
            except Exception:
                js_url = ""

            full_url = f"{curr_url} {js_url}"

            checkpoint_keys = [
                "checkpoint", "/checkpoint/", "security", "confirm_your_identity",
                "two_step", "two_step_verification", "authentication", "encrypted_context",
                "auth_platform", "limbo", "2fa", "two_factor", "account_locked", "challenge",
                "arkose", "matchkey"
            ]
            if any(ck in full_url for ck in checkpoint_keys):
                # Try clicking 'Dismiss' on 'We suspect automated behavior' screen first before failing
                if handle_facebook_automated_behavior_dismiss_screen(page):
                    time.sleep(1.5)
                    curr_url_new = page.url.lower()
                    if "checkpoint" not in curr_url_new:
                        return True, "Clean session (Dismissed automated behavior notice)"
                return False, f"Security Checkpoint / Device Approval Required in URL ('{curr_url}')"

            try:
                body_text = page.locator("body").inner_text(timeout=600).lower()
                lock_phrases = [
                    "log in on another device",
                    "approve this login",
                    "i don't have another device",
                    "extra security step at login",
                    "invalid request",
                    "we could not validate your request",
                    "starting the flow from beginning",
                    "confirm this is your account",
                    "we locked your account",
                    "account locked",
                    "confirm your identity",
                    "account has been locked",
                    "your account has been locked",
                    "account disabled",
                    "account suspended",
                    "checkpoint",
                    "two-step verification",
                    "reload page"
                ]
                if any(lp in body_text for lp in lock_phrases):
                    if handle_facebook_automated_behavior_dismiss_screen(page):
                        return True, "Clean session (Dismissed automated behavior notice)"
                    return False, "Security Checkpoint / Device Approval Required in page text"
            except Exception:
                pass
        except Exception:
            pass

        time.sleep(0.8)

    return True, "Clean session (No Checkpoint)"


def check_facebook_login_status(page: Any, context: Optional[Any] = None) -> Tuple[bool, str]:
    """
    Checks if the current browser session is genuinely logged into Facebook.
    Returns (True, "Logged in") if logged in, or (False, reason) if on Login screen, 2FA, or security checkpoint / account lock.
    """
    try:
        curr_url = page.url.lower()
        try:
            js_url = str(page.evaluate("window.location.href")).lower()
        except Exception:
            js_url = ""

        full_url = f"{curr_url} {js_url}"

        # 1. Immediate URL check for Security Checkpoints, 2FA, Device Approval, or Account Recovery
        checkpoint_urls = [
            "checkpoint", "security", "two_step", "two_factor", "2fa", "two_step_verification",
            "authentication", "encrypted_context", "auth_platform", "limbo", "confirm", "recover",
            "authenticate", "identity", "challenge", "arkose", "matchkey"
        ]
        if any(u in full_url for u in checkpoint_urls):
            if handle_facebook_automated_behavior_dismiss_screen(page):
                curr_url_new = page.url.lower()
                if "checkpoint" not in curr_url_new:
                    full_url = curr_url_new
                else:
                    return False, "Security Checkpoint / Account Verification Required"
            else:
                return False, "Security Checkpoint / 2FA / Account Verification Required"

        # 2. Check for visible full email/password login form or login buttons
        try:
            login_inputs = page.locator("input[name='email'], input[id='email'], input[data-testid='royal_email'], input[name='pass'], input[id='pass'], button[name='login'], #loginbutton, button[data-testid='royal_login_button']").all()
            for inp in login_inputs:
                if inp.is_visible(timeout=400):
                    return False, "Not logged in (Login form visible on page)"
        except Exception:
            pass

        if "/login" in full_url and not ("c_user" in full_url):
            return False, "Not logged in (On Facebook Login page)"

        # 3. Check for Security Checkpoint / Account Locked / Device Approval modals in body text
        try:
            body_text = page.locator("body").inner_text(timeout=800).lower()
            lock_triggers = [
                "log in on another device",
                "approve this login",
                "i don't have another device",
                "extra security step at login",
                "invalid request",
                "we could not validate your request",
                "starting the flow from beginning",
                "confirm this is your account",
                "we locked your account",
                "account locked",
                "confirm your identity",
                "account has been locked",
                "your account has been locked",
                "account disabled",
                "account suspended"
            ]
            if any(lt in body_text for lt in lock_triggers):
                return False, "Security Checkpoint / Device Approval Required"
        except Exception:
            pass

        # 4. Check if genuine logged-in UI elements are present
        logged_in_selectors = [
            "a[aria-label='Facebook']",
            "svg[aria-label='Facebook']",
            "a[aria-label='Home']",
            "div[role='navigation']",
            "div[role='feed']",
            "[aria-label*='Account']",
            "[aria-label*='Your profile']",
            "[aria-label*='Menu']",
            "input[placeholder*='Search Facebook']",
            "input[aria-label*='Search Facebook']"
        ]
        for sel in logged_in_selectors:
            try:
                if page.locator(sel).first.is_visible(timeout=600):
                    return True, "Logged into Facebook"
            except Exception:
                pass

        # 5. Check active session cookies in context (ONLY if no login form is present)
        target_context = context
        if not target_context:
            try:
                target_context = page.context
            except Exception:
                target_context = None

        if target_context:
            try:
                cookies = target_context.cookies()
                has_session_cookie = any(
                    c.get("name") == "c_user" and str(c.get("value", "")).strip().isdigit()
                    for c in cookies
                )
                if has_session_cookie and ("facebook.com" in full_url) and ("/login" not in full_url):
                    return True, "Logged into Facebook (Active c_user session)"
            except Exception:
                pass

        return False, "Not logged in (No active session or logged-in interface detected)"
    except Exception as err:
        return False, f"Login status evaluation note: {err}"


def get_2fa_totp_code(secret_key: str) -> Optional[str]:
    """Generates 6-digit TOTP code via 2fa.live API or local HMAC fallback."""
    if not secret_key or not str(secret_key).strip():
        return None
    clean_secret = re.sub(r"\s+", "", str(secret_key).strip())
    
    # 1. API fetch via 2fa.live
    try:
        req = urllib.request.Request(f"https://2fa.live/tok/{clean_secret}", headers={"User-Agent": "srkBrowser-2FA"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            if data.get("token") and str(data["token"]).isdigit():
                return str(data["token"])
    except Exception:
        pass

    # 2. Local fallback using standard python HMAC
    try:
        key = base64.b32decode(clean_secret.upper() + '=' * (-len(clean_secret) % 8))
        counter = struct.pack(">Q", int(time.time()) // 30)
        h = hmac.new(key, counter, hashlib.sha1).digest()
        offset = h[19] & 0xF
        code = ((struct.unpack(">I", h[offset:offset+4])[0] & 0x7FFFFFFF) % 1000000)
        return f"{code:06d}"
    except Exception:
        pass
    return None


def handle_facebook_2fa_verification(page: Any, secret_2fa: str, context: Any = None, log_func: Optional[Any] = None) -> bool:
    """Handles 2FA OTP submission."""
    def log(m: str):
        if log_func: log_func(m)

    if not secret_2fa:
        return False

    try:
        url = page.url.lower()
        body = ""
        try:
            body = page.locator("body").inner_text(timeout=1000).lower()
        except Exception:
            pass

        if "two_step_verification" in url or "two_factor" in url or "checkpoint" in url or "enter the 6-digit code" in body or "two-factor" in body:
            log("  🔐 2FA Screen Detected. Generating 6-Digit TOTP Code...")
            totp = get_2fa_totp_code(secret_2fa)
            if not totp:
                log("  ❌ Failed to generate 2FA TOTP code.")
                return False

            code_inp = page.locator("input[name='approvals_code'], input[type='text'], input[placeholder*='code'], input[id='approvals_code']").first
            if code_inp.is_visible(timeout=3000):
                code_inp.click()
                code_inp.fill(totp)
                time.sleep(0.5)

                sub_btn = page.locator("button:has-text('Continue'), button:has-text('Submit'), #checkpointSubmitButton, button[type='submit']").first
                if sub_btn.is_visible(timeout=2000):
                    sub_btn.click()
                else:
                    code_inp.press("Enter")
                log(f"  👉 Submitted 2FA Code: [{totp}]. Waiting for feed...")
                time.sleep(5)
                return True
    except Exception as err:
        log(f"  ⚠️ 2FA verification note: {err}")
    return False


def ensure_facebook_english_language(page: Any, context: Optional[Any] = None, log_func: Optional[Any] = None) -> bool:
    """
    Enforces English (US) interface language across the Facebook session:
    1. Checks if UI contains Bangla characters ([\u0980-\u09FF]) or non-English phrases.
    2. Step 1: Navigates directly to https://www.facebook.com/settings/?tab=language.
    3. Step 2: Clicks 1st row under Language Settings ("অ্যাকাউন্টের ভাষা" / "Facebook Language").
    4. Step 3: Selects "English (US)" from modal list using Playwright Native Mouse Click & JS fallback.
    5. Step 4: Clicks primary blue confirmation button ("ঠিক আছে" / "Refresh" / "Confirm").
    """
    def log(msg: str) -> None:
        if log_func:
            log_func(msg)
        print(f"[Language Enforcer] {msg}")

    try:
        target_context = context or getattr(page, 'context', None)
        if target_context:
            try:
                target_context.add_cookies([
                    {"name": "locale", "value": "en_US", "domain": ".facebook.com", "path": "/"},
                    {"name": "locale", "value": "en_US", "domain": "www.facebook.com", "path": "/"},
                    {"name": "locale", "value": "en_US", "domain": "www.facebook.com", "path": "/"}
                ])
            except Exception:
                pass

        # Check if page is already in English (US) interface
        is_non_english = True
        try:
            is_non_english = page.evaluate("""() => {
                const bodyTxt = (document.body.innerText || document.body.textContent || "").toLowerCase();
                
                // 1. If page contains Non-Latin scripts (Bangla, Hindi/Devanagari, Arabic, Cyrillic), it is Non-English
                if (/[\u0980-\u09FF\u0600-\u06FF\u0900-\u097F\u0400-\u04FF]/.test(bodyTxt)) {
                    return true;
                }

                // 2. Strong English homepage indicator phrases
                if (bodyTxt.includes("what's on your mind") || 
                    bodyTxt.includes("whats on your mind") ||
                    bodyTxt.includes("search facebook") ||
                    bodyTxt.includes("create story") ||
                    bodyTxt.includes("your shortcuts") ||
                    bodyTxt.includes("see original")) {
                    return false;
                }

                // 3. Search input element check
                if (document.querySelector("input[placeholder*='Search Facebook'], input[aria-label*='Search Facebook']")) {
                    return false;
                }

                // 4. Count common English FB navigation & UI keywords
                const englishKeywords = [
                    "friends", "memories", "saved", "groups", "reels", 
                    "marketplace", "feeds", "events", "see more", "sponsored", 
                    "birthdays", "friend requests", "meta ai", "ads manager", "dashboard"
                ];
                let matchCount = 0;
                for (const kw of englishKeywords) {
                    if (bodyTxt.includes(kw)) {
                        matchCount++;
                    }
                }

                if (matchCount >= 2) {
                    return false;
                }

                return true;
            }""")
        except Exception:
            is_non_english = True

        if not is_non_english:
            log("  🌐 Facebook interface language is already English (US). Skipping settings.")
            return True

        log("  🌐 Non-English interface detected. Navigating to https://www.facebook.com/settings/?tab=language...")

        # Step 1: Navigate directly to FB Language Settings tab
        page.goto("https://www.facebook.com/settings/?tab=language", timeout=35000, wait_until="domcontentloaded")
        time.sleep(3.0)

        # Step 2: Click the 1st row under App/Account Language ("অ্যাকাউন্টের ভাষা" / 1st option in main panel)
        log("  👉 Step 2: Clicking Account Language row...")
        row_clicked = False
        try:
            # Try Playwright locator first
            row_target = page.locator("div[role='main'] div[role='button'], div[role='main'] a[role='button']").first
            if row_target.is_visible(timeout=3000):
                row_target.click(force=True)
                row_clicked = True
        except Exception:
            pass

        if not row_clicked:
            page.evaluate("""() => {
                const main = document.querySelector('div[role="main"]') || document.body;
                const btns = Array.from(main.querySelectorAll('div[role="button"], a[role="button"]'));
                for (const b of btns) {
                    const r = b.getBoundingClientRect();
                    if (r.width > 100 && r.height > 20) {
                        b.click();
                        return true;
                    }
                }
                return false;
            }""")

        time.sleep(2.5)

        # Step 3: Select "English (US)" from modal list
        log("  👉 Step 3: Selecting 'English (US)' from popup modal...")
        eng_clicked = False
        try:
            # Native Playwright Click on English (US) text in modal dialog
            eng_loc = page.locator("div[role='dialog']").get_by_text("English (US)", exact=False).first
            if eng_loc.is_visible(timeout=4000):
                eng_loc.scroll_into_view_if_needed()
                time.sleep(0.5)
                eng_loc.click(force=True)
                eng_clicked = True
                log("  ✅ Clicked 'English (US)' via Playwright Native Click!")
        except Exception as e_err:
            log(f"  ⚠️ Playwright click note: {e_err}")

        if not eng_clicked:
            # JS Fallback Click
            page.evaluate("""() => {
                const dialogs = Array.from(document.querySelectorAll('div[role="dialog"]'));
                for (const dialog of dialogs) {
                    const allEls = Array.from(dialog.querySelectorAll('*'));
                    for (const el of allEls) {
                        const txt = (el.innerText || el.textContent || '').trim();
                        if (txt === 'English (US)' || txt.startsWith('English (US)')) {
                            const clickable = el.closest('div[role="radio"], label, input[type="radio"], div[role="button"]') || el;
                            clickable.click();
                            const radio = clickable.querySelector('input[type="radio"]');
                            if (radio) {
                                radio.click();
                                radio.checked = true;
                            }
                            return true;
                        }
                    }
                }
                return false;
            }""")

        time.sleep(2.0)

        # Step 4: Click primary blue confirmation button ("ঠিক আছে" / "Refresh" / "Confirm")
        log("  👉 Step 4: Clicking Blue Confirm button...")
        confirm_clicked = False
        try:
            # Native Playwright locator for blue button inside modal
            dialog_btns = page.locator("div[role='dialog'] div[role='button'], div[role='dialog'] button").all()
            for btn in dialog_btns:
                txt = (btn.inner_text() or "").strip()
                if "ঠিক আছে" in txt or "OK" in txt or "Confirm" in txt or "Refresh" in txt or "Save" in txt:
                    btn.click(force=True)
                    confirm_clicked = True
                    log("  ✅ Clicked Confirm button via Playwright Native Click!")
                    break
        except Exception:
            pass

        if not confirm_clicked:
            # JS Fallback
            page.evaluate("""() => {
                const dialogs = Array.from(document.querySelectorAll('div[role="dialog"]'));
                for (const d of dialogs) {
                    const blueBtns = Array.from(d.querySelectorAll('div[role="button"], button'));
                    for (const b of blueBtns) {
                        const r = b.getBoundingClientRect();
                        if (r.width > 0 && r.height > 0) {
                            b.click();
                            return true;
                        }
                    }
                }
                return false;
            }""")

        time.sleep(3.0)

        log("  ✅ Successfully executed 4-Step Language Switcher to English (US)!")
        return True
    except Exception as err:
        log(f"  ⚠️ Language enforcement note: {err}")
        return False


def handle_facebook_profile_continue_screen(page: Any, password: str = "", log_func: Optional[Any] = None) -> bool:
    """
    Handles Facebook's Account Chooser / Profile Continue screen and Password Modal Popup.
    - Clicks 'Continue' button on Account Chooser screen.
    - Fills password in the Password Modal Popup ('Tuh Efds', Password input, Log in button).
    - Clicks 'Log in' button or presses Enter.
    """
    def log(msg: str) -> None:
        if log_func:
            log_func(msg)

    try:
        ok, _ = check_facebook_login_status(page)
        if ok:
            return True

        # Step 1: Look for Account Chooser 'Continue' button
        continue_selectors = [
            "button:has-text('Continue')",
            "div[role='button']:has-text('Continue')",
            "a[role='button']:has-text('Continue')",
            "button:has-text('Continuar')",
            "div[role='button']:has-text('Continuar')",
            "button[name='login']",
            "div[aria-label='Continue']",
            "span:has-text('Continue')"
        ]

        found_continue = False
        for c_sel in continue_selectors:
            try:
                c_btn = page.locator(c_sel).first
                if c_btn.is_visible(timeout=1500):
                    log("  👉 Account Chooser Screen Detected! Auto-clicking 'Continue' button...")
                    c_btn.scroll_into_view_if_needed()
                    time.sleep(0.3)
                    c_btn.click(force=True)
                    found_continue = True
                    time.sleep(random.uniform(2.0, 3.5))
                    break
            except Exception:
                continue

        # Step 2: Detect & Handle Password Modal Popup (as shown in user screenshot)
        pass_selectors = [
            "div[role='dialog'] input[type='password']",
            "div[role='dialog'] input[name='pass']",
            "div[role='dialog'] #pass",
            "input[type='password']",
            "input[name='pass']",
            "#pass"
        ]

        pass_field = None
        for p_sel in pass_selectors:
            try:
                pf = page.locator(p_sel).first
                if pf.is_visible(timeout=1500):
                    pass_field = pf
                    break
            except Exception:
                continue

        if pass_field and password:
            log(f"  🔑 Password Modal Popup Detected! Filling saved password into password box...")
            pass_field.click()
            time.sleep(0.2)
            pass_field.fill("")
            time.sleep(0.2)
            pass_field.press_sequentially(password, delay=random.randint(40, 90))
            time.sleep(0.4)

            # Click 'Log in' button inside modal dialog
            login_btn_selectors = [
                "div[role='dialog'] button:has-text('Log in')",
                "div[role='dialog'] div[role='button']:has-text('Log in')",
                "div[role='dialog'] button[name='login']",
                "div[role='dialog'] button[type='submit']",
                "button:has-text('Log in')",
                "div[role='button']:has-text('Log in')",
                "button[name='login']"
            ]

            clicked_login = False
            for l_sel in login_btn_selectors:
                try:
                    l_btn = page.locator(l_sel).first
                    if l_btn.is_visible(timeout=1200):
                        l_btn.click(force=True)
                        clicked_login = True
                        log("  👉 Clicked 'Log in' button on Password Modal Popup!")
                        break
                except Exception:
                    continue

            if not clicked_login:
                log("  👉 Submitting Password Modal Popup via Enter key...")
                pass_field.press("Enter")

            time.sleep(random.uniform(3.5, 5.5))

        ok, _ = check_facebook_login_status(page)
        if ok:
            log("  ✅ Session activated via Password Modal Popup!")
            return True

    except Exception as err:
        log(f"  ⚠️ Note handling Continue screen & Password Modal: {err}")

    return False


def attempt_profile_relogin(page: Any, context: Any, profile_data: Dict[str, Any], log_func: Optional[Any] = None) -> bool:
    """
    Attempt to re-login a logged-out profile using its stored Cookie first, then stored UID + Password + 2FA.
    Returns True if re-login succeeded, False if failed.
    """
    def log(msg: str) -> None:
        if log_func:
            log_func(msg)
        else:
            print(msg)

    uid = profile_data.get("uid", "") or profile_data.get("fb_uid", "")
    password = profile_data.get("password", "") or profile_data.get("fb_pass", "")
    cookie_str = profile_data.get("cookie", "") or profile_data.get("fb_cookie", "")
    secret_2fa = profile_data.get("secret_2fa") or profile_data.get("2fa_secret") or profile_data.get("fb_2fa") or profile_data.get("secret") or ""

    # Fallback to parse notes if dict fields are blank
    notes = profile_data.get("notes", "") or profile_data.get("custom_notes", "")
    if notes:
        for line in notes.split("\n"):
            line_s = line.strip()
            if line_s.startswith("FB UID:"):
                uid = uid or line_s.replace("FB UID:", "").strip()
            elif line_s.startswith("UID:"):
                uid = uid or line_s.replace("UID:", "").strip()
            elif line_s.startswith("Pass:"):
                password = password or line_s.replace("Pass:", "").strip()
            elif line_s.startswith("Password:"):
                password = password or line_s.replace("Password:", "").strip()
            elif line_s.startswith("Cookie:"):
                cookie_str = cookie_str or line_s.replace("Cookie:", "").strip()
            elif "2fa secret:" in line_s.lower() or "2fa:" in line_s.lower() or "secret_2fa:" in line_s.lower():
                if not secret_2fa:
                    secret_2fa = line_s.split(":", 1)[1].strip()

    log(f"  🔐 Attempting Auto Re-Login for UID: '{uid}'...")

    # Stage 1: Try Cookie Re-login first
    if cookie_str:
        parsed_ck = parse_cookie_string(cookie_str, default_domain=".facebook.com")
        if parsed_ck:
            try:
                parsed_ck.append({"name": "locale", "value": "en_US", "domain": ".facebook.com", "path": "/"})
                log(f"  🔐 [Re-login Stage 1] Injecting {len(parsed_ck)} stored cookies...")
                context.add_cookies(parsed_ck)
                page.goto("https://www.facebook.com/", timeout=40000, wait_until="domcontentloaded")
                time.sleep(random.uniform(2.5, 4.0))

                ok, _ = check_facebook_login_status(page)
                if not ok:
                    ok = handle_facebook_profile_continue_screen(page, password, log)

                if ok:
                    log("  ✅ Re-login SUCCESSFUL via stored Cookies!")
                    try:
                        import threading
                        from cloud_sync import upload_profiles_cloud_backup
                        threading.Thread(target=upload_profiles_cloud_backup, args=([profile_data],), daemon=True).start()
                    except Exception:
                        pass
                    return True
                else:
                    log("  ⚠️ Stored cookies expired or invalid. Moving to UID & Password re-login...")
            except Exception as ck_err:
                log(f"  ⚠️ Cookie re-login note: {ck_err}")

    # Stage 2: Check for Continue screen
    try:
        if handle_facebook_profile_continue_screen(page, password, log):
            try:
                import threading
                from cloud_sync import upload_profiles_cloud_backup
                threading.Thread(target=upload_profiles_cloud_backup, args=([profile_data],), daemon=True).start()
            except Exception:
                pass
            return True
    except Exception:
        pass

    # Stage 3: Try UID & Password Re-login if Cookie & Continue failed
    if uid and password:
        try:
            log(f"  📝 [Re-login Stage 3] Attempting UID ({uid}) and Password re-login...")
            page.goto("https://www.facebook.com/", timeout=40000, wait_until="domcontentloaded")
            time.sleep(random.uniform(2.0, 3.5))

            # Click 'Use another profile' / 'Utiliser un autre profil' if present to reveal email/pass fields
            try:
                use_another_selectors = [
                    "button:has-text('Use another profile')",
                    "button:has-text('Utiliser un autre profil')",
                    "button:has-text('Usar otra cuenta')",
                    "div[role='button']:has-text('Use another profile')",
                    "div[role='button']:has-text('Utiliser un autre profil')",
                    "div[role='button']:has-text('Usar otra cuenta')",
                    "a:has-text('Use another profile')",
                    "a:has-text('Utiliser un autre profil')"
                ]
                for u_sel in use_another_selectors:
                    try:
                        u_btn = page.locator(u_sel).first
                        if u_btn.is_visible(timeout=1000):
                            u_btn.click(force=True)
                            time.sleep(1.5)
                            break
                    except Exception:
                        continue
            except Exception:
                pass

            email_inp = page.locator("input[name='email'], #email, input[type='email'], input[data-testid='royal_email'], input[type='text']").first
            pass_inp = page.locator("input[name='pass'], #pass, input[type='password'], input[data-testid='royal_pass']").first

            if email_inp.is_visible(timeout=4000) and pass_inp.is_visible(timeout=4000):
                log(f"  ⌨️ Typing UID/Email into field: '{uid}'...")
                email_inp.click()
                time.sleep(0.3)
                email_inp.fill("")
                time.sleep(0.2)
                email_inp.press_sequentially(uid, delay=random.randint(40, 90))

                time.sleep(0.4)
                log("  🔑 Typing Password into field...")
                pass_inp.click()
                time.sleep(0.3)
                pass_inp.fill("")
                time.sleep(0.2)
                pass_inp.press_sequentially(password, delay=random.randint(40, 90))
                time.sleep(0.5)

                login_btn = page.locator("button[name='login'], #loginbutton, button[type='submit']").first
                if login_btn.is_visible(timeout=1500):
                    login_btn.click()
                else:
                    pass_inp.press("Enter")

                time.sleep(random.uniform(4.0, 6.0))

                # Check for 2FA Page in Stage 3 Re-login
                if secret_2fa:
                    try:
                        handle_facebook_2fa_verification(page=page, secret_2fa=secret_2fa, context=context, log_func=log)
                    except Exception as fa_err:
                        log(f"  ⚠️ 2FA re-login note: {fa_err}")

                ok, _ = check_facebook_login_status(page)
                if not ok:
                    ok = handle_facebook_profile_continue_screen(page, password, log)

                if ok:
                    log("  ✅ Re-login SUCCESSFUL via stored UID & Password!")
                    try:
                        import threading
                        from cloud_sync import upload_profiles_cloud_backup
                        threading.Thread(target=upload_profiles_cloud_backup, args=([profile_data],), daemon=True).start()
                    except Exception:
                        pass
                    return True
        except Exception as form_err:
            log(f"  ⚠️ UID/Pass re-login note: {form_err}")

    log("  ❌ Re-login failed via Cookie, Continue prompt, and UID/Password.")
    return False


def dismiss_facebook_overlays(page: Any) -> None:
    """Auto-dismiss overlay popups (e.g. 'What happened / We added restrictions to your account', notifications, PIN dialogs, etc.)."""
    try:
        # 1. Send Escape key to close active overlay modal immediately
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass

        # 2. Comprehensive selectors for modal dialog top-right X close buttons and action dismissals
        close_btns = [
            "div[role='dialog'] [aria-label='Close']",
            "div[role='dialog'] div[aria-label='Close']",
            "div[role='dialog'] div[role='button'][aria-label='Close']",
            "div[role='dialog'] [aria-label='Cerrar']",
            "div[role='dialog'] svg[aria-label='Close']",
            "div[role='dialog'] svg[aria-label='Cerrar']",
            "div[role='dialog'] i[aria-label='Close']",
            "div[role='dialog'] div[role='button']:has(svg)",
            "button:has-text('Block')",
            "div[role='button']:has-text('Block')",
            "button:has-text('Allow')",
            "div[role='dialog'] button:has-text('Not Now')",
            "div[role='dialog'] button:has-text('Ahora no')",
            "div[role='dialog'] div[role='button']:has-text('Not Now')",
            "div[role='dialog'] div[role='button']:has-text('Ahora no')"
        ]

        for c_sel in close_btns:
            try:
                elems = page.locator(c_sel)
                count = elems.count()
                for i in range(min(count, 3)):
                    elem = elems.nth(i)
                    if elem.is_visible(timeout=300):
                        elem.click(force=True)
                        time.sleep(0.3)
            except Exception:
                continue
    except Exception:
        pass


def configure_antidetect_context(context: Any, profile_data: Optional[Dict[str, Any]] = None) -> None:
    """
    Applies stealth anti-detect fingerprinting overrides to a Playwright browser context:
    1. Canvas 2D noise injection (subtle hash randomization)
    2. WebGL Vendor & Renderer parameter spoofing
    3. AudioContext micro-noise
    4. Hardware Concurrency & RAM spoofing per profile
    5. Mask navigator.webdriver, navigator.languages, and Chrome runtime bindings
    """
    pdata = profile_data or {}
    cores = pdata.get("cpu_cores") or random.choice([4, 8, 12, 16])
    ram = pdata.get("ram_gb") or random.choice([4, 8, 16, 32])

    init_js = f"""
    (() => {{
        try {{
            Object.defineProperty(navigator, 'webdriver', {{ get: () => undefined }});
            delete navigator.__proto__.webdriver;
        }} catch(e) {{}}

        try {{
            window.chrome = {{
                runtime: {{}},
                loadTimes: function() {{}},
                csi: function() {{}},
                app: {{}}
            }};
        }} catch(e) {{}}

        try {{
            Object.defineProperty(navigator, 'hardwareConcurrency', {{ get: () => {cores} }});
            Object.defineProperty(navigator, 'deviceMemory', {{ get: () => {ram} }});
            Object.defineProperty(navigator, 'languages', {{ get: () => ['en-US', 'en'] }});
            Object.defineProperty(navigator, 'language', {{ get: () => 'en-US' }});
            Object.defineProperty(navigator, 'maxTouchPoints', {{ get: () => 0 }});
        }} catch(e) {{}}

        try {{
            const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function(type) {{
                const ctx = this.getContext('2d');
                if (ctx) {{
                    try {{
                        const imgData = ctx.getImageData(0, 0, Math.min(this.width, 10), Math.min(this.height, 10));
                        if (imgData.data.length > 3) {{
                            imgData.data[0] = Math.max(0, Math.min(255, imgData.data[0] + (Math.random() > 0.5 ? 1 : -1)));
                            ctx.putImageData(imgData, 0, 0);
                        }}
                    }} catch(e) {{}}
                }}
                return originalToDataURL.apply(this, arguments);
            }};
        }} catch(e) {{}}

        try {{
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {{
                if (parameter === 37445) return 'Google Inc. (NVIDIA)';
                if (parameter === 37446) return 'ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0)';
                return getParameter.apply(this, arguments);
            }};
        }} catch(e) {{}}
    }})();
    """
    try:
        context.add_init_script(init_js)
    except Exception:
        pass


def finish_facebook_page_creation_wizard(page: Any, page_name: str = "", log_func: Optional[Any] = None) -> bool:
    """
    Handles the 5-step post page creation onboarding wizard:
    1. Waits for black toast notification '[Page Name] was created' to disappear/close.
    2. Clicks 'Next' through the setup steps.
    3. Handles WhatsApp skip, profile/cover picture skip, page notifications, and clicks 'Done' / 'Save'.
    """
    def log(msg: str) -> None:
        if log_func:
            log_func(msg)
        else:
            print(msg)

    try:
        log(f"  🎉 Page '{page_name}' created successfully! Processing onboarding setup steps...")

        # Step 1: Explicitly dismiss bottom-left black toast notification ('[Page Name] was created')
        log("  ⏳ Closing bottom creation notification popup ('...was created')...")
        toast_closed = False
        toast_close_selectors = [
            "div[role='alert']:has-text('was created') [aria-label='Close']",
            "div[role='alert']:has-text('was created') svg[aria-label='Close']",
            "div[role='alert']:has-text('was created') svg",
            "div[role='alert']:has-text('was created') div[role='button']",
            "div[role='alert']:has-text('was created') button",
            "div:has-text('was created') div[role='button']",
            "div:has-text('created'):has-text('images') div[role='button']",
            "div:has-text('created'):has-text('images') svg",
            "div[role='alert'] [aria-label='Close']",
            "div[role='alert'] div[role='button']"
        ]
        
        for attempt in range(8):
            for t_sel in toast_close_selectors:
                try:
                    c_btn = page.locator(t_sel).first
                    if c_btn.is_visible(timeout=500):
                        c_btn.click(force=True)
                        toast_closed = True
                        log("  ✓ Closed black toast notification popup [x].")
                        time.sleep(1.2)
                        break
                except Exception:
                    continue
            if toast_closed:
                break
            time.sleep(0.7)
        
        if not toast_closed:
            time.sleep(2.0)

        # Step 2: Onboarding Wizard Loop (Step 1 to 5: Next, Skip, Done, Save)
        log("  ⏩ Navigating onboarding steps (Clicking Next / Skip / Done)...")
        for wizard_step in range(1, 9):
            time.sleep(random.uniform(1.5, 2.5))
            
            # Dismiss any popup overlays/dialogs
            dismiss_facebook_overlays(page)

            # Look for Next, Skip, Done, or Save buttons
            btn_found = False
            action_selectors = [
                "div[aria-label='Next']",
                "div[aria-label*='Next']",
                "button:has-text('Next')",
                "div[role='button']:has-text('Next')",
                "span:has-text('Next')",
                "button:has-text('Siguiente')",
                "div[role='button']:has-text('Siguiente')",

                "div[aria-label='Skip']",
                "button:has-text('Skip')",
                "div[role='button']:has-text('Skip')",
                "span:has-text('Skip')",
                "button:has-text('Omitir')",

                "div[aria-label='Done']",
                "button:has-text('Done')",
                "div[role='button']:has-text('Done')",
                "span:has-text('Done')",
                "button:has-text('Listo')",

                "div[aria-label='Save']",
                "button:has-text('Save')",
                "div[role='button']:has-text('Save')",

                "button:has-text('Use Page')",
                "div[role='button']:has-text('Use Page')",
                "button:has-text('Not now')",
                "div[role='button']:has-text('Not now')",
                "button:has-text('Continue')",
                "div[role='button']:has-text('Continue')"
            ]

            for sel in action_selectors:
                try:
                    btn = page.locator(sel).first
                    if btn.is_visible(timeout=1200):
                        btn_text = btn.inner_text().strip() or "Next"
                        btn.scroll_into_view_if_needed()
                        time.sleep(0.2)
                        btn.click(force=True)
                        log(f"  ✓ Step {wizard_step}: Clicked '{btn_text}' button.")
                        btn_found = True
                        time.sleep(random.uniform(2.5, 4.0))
                        break
                except Exception:
                    continue

            if not btn_found:
                curr_url = page.url.lower()
                if "creation" not in curr_url:
                    log("  ✅ Reached final Facebook Page profile view! Setup complete.")
                    break

        log("  🌐 Page setup complete. Navigating back to Facebook Home Page (https://www.facebook.com)...")
        try:
            page.goto("https://www.facebook.com", timeout=35000, wait_until="domcontentloaded")
            time.sleep(random.uniform(2.5, 4.0))
            log("  ✓ Successfully loaded Facebook Home Page.")
        except Exception as home_err:
            log(f"  ⚠️ Home page navigation note: {home_err}")

        return True
    except Exception as err:
        log(f"  ⚠️ Note completing page wizard steps: {err}")
        return True


def ensure_active_facebook_page(page: Any, log_func: Optional[Any] = None) -> Tuple[bool, str]:
    """
    Ensures that the current Facebook browser session is operating under a Facebook Page context.
    - NEVER posts video from the personal profile ID.
    - Uses exact Page names (Velvet Vibes, 3d XX Videos, etc.) or general Page switcher selectors.
    """
    def log(msg: str) -> None:
        if log_func:
            log_func(msg)
        else:
            print(msg)

    log("  🔎 Verifying Facebook Page context & selection...")

    # Check login status inside page verification
    is_logged_in, login_status_msg = check_facebook_login_status(page)
    if not is_logged_in:
        log(f"  ❌ Account is NOT logged into Facebook ({login_status_msg}). Skipping Page check.")
        return False, f"Not logged in: {login_status_msg}"

    # Auto-dismiss overlay popups ("Create a PIN", etc.)
    dismiss_facebook_overlays(page)

def is_already_on_facebook_page(page: Any) -> bool:
    """
    Returns True if the browser session is already switched to a Facebook Page profile.
    Checks page text, presence of 'Professional dashboard', 'Manage Page', 'Switch to [Personal]', etc.
    """
    try:
        main_text = page.locator("body").inner_text(timeout=2000).lower()
        page_indicators = [
            "you're using facebook as",
            "acting as",
            "professional dashboard",
            "manage page",
            "create reel",
            "boost post",
            "boost instagram post"
        ]
        if any(ind in main_text for ind in page_indicators):
            return True

        if page.locator("span:has-text('Professional dashboard'), div:has-text('Professional dashboard'), span:has-text('Manage Page')").first.is_visible(timeout=1000):
            return True
    except Exception:
        pass
    return False


def switch_facebook_to_page_profile(page: Any, log_func: Optional[Any] = None) -> Tuple[bool, str]:
    """
    Ensures Facebook session is switched to 1st Page profile before publishing.
    Delegates to select_first_facebook_page for robust 3-dot and modal handling.
    """
    def log(msg: str) -> None:
        if log_func:
            log_func(msg)

    try:
        ok = select_first_facebook_page(page, log_func=log)
        if ok:
            return True, "Switched to 1st Facebook Page"
        return False, "Failed to switch to Page"
    except Exception as err:
        log(f"  ⚠️ Page profile switch note: {err}")
        return False, str(err)

    # STEP 0: Close any open Messenger / PIN drawers via Escape key & overlay dismiss
    try:
        page.keyboard.press("Escape")
        time.sleep(0.3)
        page.keyboard.press("Escape")
        time.sleep(0.5)
        dismiss_facebook_overlays(page)
    except Exception:
        pass

    system_keywords = [
        "settings", "configuración", "help", "ayuda", "support", "asistencia",
        "display", "pantalla", "accessibility", "accesibilidad", "feedback",
        "comentarios", "log out", "cerrar sesión", "privacy", "privacidad",
        "terms", "términos", "advertising", "anuncios"
    ]

    # STEP 1: Check if already operating under a Page context
    try:
        body_text_home = page.locator("body").inner_text(timeout=3000).lower()
        if "you're using facebook as" in body_text_home or "acting as" in body_text_home:
            log("  ✅ Session is already operating under a Facebook Page!")
            return True, "Already on Page context"
    except Exception:
        pass

    # STEP 2: Try Left Sidebar "Your shortcuts" FIRST (Direct 1-click Page Switch!)
    try:
        shortcut_selectors = [
            "a[role='link']:has-text('Beauty Box')",
            "a[role='link']:has-text('Velvet Vibes')",
            "a[role='link']:has-text('3d XX Videos')",
            "div[aria-label='Shortcuts'] a[role='link']",
            "div[aria-label='Sus accesos directos'] a[role='link']"
        ]
        for sc_sel in shortcut_selectors:
            try:
                sc_elem = page.locator(sc_sel).first
                if sc_elem.is_visible(timeout=1000):
                    sc_text = sc_elem.inner_text().strip()
                    if sc_text and sc_text.lower() not in system_keywords and len(sc_text) > 2:
                        log(f"  ✓ Found Page in Left Shortcuts: '{sc_text}'. Clicking to switch...")
                        sc_elem.click(force=True)
                        time.sleep(4)

                        switch_btn = page.locator("button:has-text('Switch'), div[role='button']:has-text('Switch'), button:has-text('Cambiar'), div[role='button']:has-text('Cambiar')").first
                        if switch_btn.is_visible(timeout=3000):
                            switch_btn.click(force=True)
                            time.sleep(4)
                            log("  ✅ Successfully switched to Page via Left Shortcut & Banner Switch!")
                            return True, f"Switched to Page {sc_text} via Left Shortcut"
                        
                        log(f"  ✅ Opened Page '{sc_text}' via Left Shortcut!")
                        return True, f"Opened Page {sc_text} via Left Shortcut"
            except Exception:
                continue
    except Exception:
        pass

    # STEP 3: Target top-right Profile Avatar button (.last button in top banner)
    log("  🔎 Opening Account Profile Menu (top-right avatar)...")
    menu_opened = False
    try:
        banner_btns = page.locator("div[role='banner'] div[role='button']")
        if banner_btns.count() > 0:
            # The profile avatar is ALWAYS the LAST button in top banner (avoids Messenger icon!)
            banner_btns.last.click(force=True)
            log("  ✓ Clicked Top-Right Profile Avatar menu (.last button)")
            menu_opened = True
            time.sleep(2.5)
    except Exception as av_err:
        log(f"  ⚠️ Top avatar click note: {av_err}")

    if menu_opened:
        try:
            # Check for direct Page targets in open menu (Velvet Vibes, 3d XX Videos)
            direct_page_selectors = [
                "span:has-text('Velvet Vibes')",
                "div:has-text('Velvet Vibes')",
                "span:has-text('3d XX Videos')",
                "div:has-text('3d XX Videos')",
                "div[role='button']:has-text('Velvet Vibes')",
                "div[role='button']:has-text('3d XX Videos')"
            ]

            for dp_sel in direct_page_selectors:
                try:
                    dp_elem = page.locator(dp_sel).first
                    if dp_elem.is_visible(timeout=1000):
                        log(f"  🔄 Found Page in Account Menu! Clicking to switch...")
                        dp_elem.click(force=True)
                        time.sleep(5)

                        # Handle switch confirmation dialog if any
                        try:
                            confirm_btn = page.locator("div[role='dialog'] div[aria-label*='Switch'], div[role='dialog'] button:has-text('Switch'), div[role='dialog'] div[aria-label*='Cambiar'], div[role='dialog'] button:has-text('Cambiar')").first
                            if confirm_btn.is_visible(timeout=2000):
                                confirm_btn.click(force=True)
                                time.sleep(3)
                        except Exception:
                            pass

                        log("  ✅ Successfully switched to Facebook Page!")
                        return True, "Switched to Page via Direct Menu Target"
                except Exception:
                    continue

            # Click "See all profiles" / "Ver todos los perfiles"
            see_all_selectors = [
                "span:has-text('See all profiles')",
                "span:has-text('Ver todos los perfiles')",
                "div[role='button']:has-text('See all profiles')",
                "div[role='button']:has-text('Ver todos los perfiles')",
                "span:has-text('See all')",
                "span:has-text('Ver todos')",
                "div[aria-label*='See all' i]",
                "div[aria-label*='Ver todos' i]"
            ]

            for sa_sel in see_all_selectors:
                try:
                    sa_elem = page.locator(sa_sel).first
                    if sa_elem.is_visible(timeout=1500):
                        sa_elem.click(force=True)
                        log("  ✓ Clicked 'See all profiles' / 'Ver todos los perfiles'")
                        time.sleep(2.5)

                        # Check direct page targets in full list
                        for dp_sel in direct_page_selectors:
                            try:
                                sub_dp = page.locator(dp_sel).first
                                if sub_dp.is_visible(timeout=1000):
                                    log(f"  🔄 Clicking Page profile from full list...")
                                    sub_dp.click(force=True)
                                    time.sleep(5)
                                    log("  ✅ Successfully switched to Facebook Page!")
                                    return True, "Switched to Page via Sub-Menu Target"
                            except Exception:
                                continue
                        break
                except Exception:
                    continue

            # General dynamic row iterator fallback inside menu (works for ANY Facebook ID and ANY Page Name!)
            switch_rows = page.locator("div[role='dialog'] div[role='button'], div[role='menu'] div[role='button'], div[role='dialog'] div[tabindex='0'], div[role='menu'] div[tabindex='0'], div[role='button'], div[tabindex='0']")
            for idx in range(switch_rows.count()):
                try:
                    row = switch_rows.nth(idx)
                    if not row.is_visible(timeout=500):
                        continue
                    txt = row.inner_text(timeout=500).strip().lower()
                    if not txt or len(txt) < 2:
                        continue

                    # Skip main personal profile (1st item) or system menu items
                    if idx == 0:
                        continue
                    if any(kw in txt for kw in system_keywords):
                        continue
                    if "see all" in txt or "ver todos" in txt:
                        continue

                    log(f"  🔄 Found Page in Account Menu dynamically ({txt[:25]})! Clicking to switch...")
                    row.click(force=True)
                    time.sleep(5)
                    log("  ✅ Successfully switched to Facebook Page profile!")
                    return True, "Switched to Page via Menu Row"
                except Exception:
                    continue
        except Exception as menu_err:
            log(f"  ⚠️ Top menu switch note: {menu_err}")

    # STEP 3: Left Sidebar Shortcuts (Your shortcuts -> Velvet Vibes / 3d XX Videos)
    log("  🔎 Checking Left Sidebar shortcuts for Pages...")
    try:
        sidebar_page_selectors = [
            "a[role='link']:has-text('Velvet Vibes')",
            "a[role='link']:has-text('3d XX Videos')",
            "span:has-text('Velvet Vibes')",
            "span:has-text('3d XX Videos')",
            "a[href*='/pages/']",
            "a[href*='/profile.php?id=']"
        ]
        for sb_sel in sidebar_page_selectors:
            try:
                sb_elem = page.locator(sb_sel).first
                if sb_elem.is_visible(timeout=1500):
                    sb_href = sb_elem.get_attribute("href") or ""
                    if "facebook.com" in sb_href or "/" in sb_href:
                        log(f"  🌐 Opening Page from Left Sidebar shortcuts: {sb_elem.inner_text(timeout=500)}")
                        sb_elem.click(force=True)
                        time.sleep(4)

                        # Look for Switch button on Page banner
                        banner_switch = page.locator("button:has-text('Switch'), div[role='button']:has-text('Switch'), button:has-text('Cambiar'), div[role='button']:has-text('Cambiar'), div[aria-label*='Switch' i], div[aria-label*='Cambiar' i]").first
                        if banner_switch.is_visible(timeout=3000):
                            banner_switch.click(force=True)
                            time.sleep(4)
                            log("  ✅ Successfully switched to Page via Page Profile Banner!")
                            return True, "Switched to Page via Banner"
            except Exception:
                continue
    except Exception as sb_err:
        log(f"  ⚠️ Sidebar check note: {sb_err}")

    # STEP 4: Pages Overview (/pages/?category=your_pages)
    log("  🔎 Navigating to Facebook Pages Overview (/pages)...")
    try:
        page.goto("https://www.facebook.com/pages/?category=your_pages", timeout=35000, wait_until="domcontentloaded")
        time.sleep(4)

        switch_candidates = page.locator("div[role='main'] button, div[role='main'] div[role='button'], div[role='main'] a, button, div[role='button'], div[aria-label*='Switch' i], div[aria-label*='Cambiar' i]")
        for c_i in range(switch_candidates.count()):
            try:
                elem = switch_candidates.nth(c_i)
                if not elem.is_visible(timeout=500):
                    continue
                t_text = elem.inner_text(timeout=500).strip().lower()
                t_aria = (elem.get_attribute("aria-label") or "").lower()
                if "switch" in t_text or "cambiar" in t_text or "usar" in t_text or "switch" in t_aria or "cambiar" in t_aria or "seleccionar" in t_aria or "velvet" in t_text or "3d xx" in t_text:
                    log(f"  🔄 Found Switch/Page button on Pages Overview ('{t_text}'). Clicking...")
                    elem.click(force=True)
                    time.sleep(4)

                    try:
                        c_btn = page.locator("div[role='dialog'] div[aria-label*='Switch'], div[role='dialog'] button:has-text('Switch'), div[role='dialog'] div[aria-label*='Cambiar'], div[role='dialog'] button:has-text('Cambiar')").first
                        if c_btn.is_visible(timeout=2000):
                            c_btn.click(force=True)
                            time.sleep(3)
                    except Exception:
                        pass

                    log("  ✅ Successfully switched to Facebook Page profile!")
                    return True, "Switched to Page via Overview"
            except Exception:
                continue
    except Exception as nav_err:
        log(f"  ⚠️ Pages Overview switch note: {nav_err}")

    log("  ❌ SKIPPED: Could NOT switch to a Facebook Page on this account. Video upload skipped to protect personal profile ID.")
    return False, "Failed to switch to Page"


def humanized_type_text(element: Any, text: str, page: Optional[Any] = None) -> None:
    """
    Inputs text into an input/contenteditable element via scoped focus + JS paste & React events.
    """
    try:
        try:
            element.scroll_into_view_if_needed()
        except Exception:
            pass
        time.sleep(0.2)
        try:
            element.click(force=True)
        except Exception:
            pass
        time.sleep(0.3)

        # Scoped DOM node selection + Native JS execCommand & React Event Dispatching
        try:
            element.evaluate("""(el, text) => {
                el.focus();
                el.click();
                if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
                    const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set;
                    if (setter) {
                        setter.call(el, text);
                    } else {
                        el.value = text;
                    }
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                } else {
                    try {
                        const sel = window.getSelection();
                        const range = document.createRange();
                        range.selectNodeContents(el);
                        sel.removeAllRanges();
                        sel.addRange(range);
                        document.execCommand('delete', false, null);
                        document.execCommand('insertText', false, text);
                    } catch(e) {}
                    if (!el.innerText || !el.innerText.includes(text.substring(0, 10))) {
                        el.innerText = text;
                    }
                    el.dispatchEvent(new InputEvent('beforeinput', { bubbles: true, inputType: 'insertFromPaste', data: text }));
                    el.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertFromPaste', data: text }));
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    el.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true }));
                }
            }""", text)
            time.sleep(0.3)
            val = element.evaluate("el => el.value || el.innerText || ''")
            if text[:10] in val:
                return
        except Exception:
            pass

        # Standard fill fallback
        try:
            element.fill(text)
        except Exception:
            for char in text:
                element.press_sequentially(char, delay=random.randint(10, 30))
    except Exception:
        pass


def check_meta_bulk_upload_progress(page: Any) -> Tuple[bool, str]:
    """
    Evaluates Meta Business Suite Bulk Upload Composer progress.
    Returns (progressed: bool, reason: str).
    Returns progressed=True if any video progress is > 0% or completed.
    Returns progressed=False if progress is stuck at 0%.
    """
    try:
        res = page.evaluate("""() => {
            const bodyText = (document.body.innerText || '').toLowerCase();
            
            // Collect all percentage text matches (e.g. 0%, 5%, 100%)
            const matches = Array.from(bodyText.matchAll(/\\b(\\d{1,3})%/g));
            if (matches.length > 0) {
                const percentages = matches.map(m => parseInt(m[1], 10));
                const maxPct = Math.max(...percentages);
                if (maxPct > 0) {
                    return { progressed: true, reason: maxPct + '%' };
                } else {
                    return { progressed: false, reason: 'stuck_at_0%' };
                }
            }
            
            if (bodyText.includes('safe to publish') || bodyText.includes('ready to publish')) {
                return { progressed: true, reason: 'safe_to_publish' };
            }
            
            return { progressed: false, reason: 'no_pct_found' };
        }""")
        return bool(res.get("progressed", False)), str(res.get("reason", ""))
    except Exception:
        return False, "error"


def get_current_upload_percentage(page: Any) -> str:
    """
    Extracts the current video upload percentage text from Meta Business Suite page DOM (e.g. '8%', '0%', '100%').
    """
    try:
        res = page.evaluate("""() => {
            const bodyText = (document.body.innerText || '').toLowerCase();
            const matches = Array.from(bodyText.matchAll(/\\b(\\d{1,3})%/g));
            if (matches.length > 0) {
                const percentages = matches.map(m => parseInt(m[1], 10)).filter(n => n <= 100);
                if (percentages.length > 0) {
                    const maxPct = Math.max(...percentages);
                    return maxPct + '%';
                }
            }
            return '0%';
        }""")
        return str(res) if res else "0%"
    except Exception:
        return "0%"


def cleanup_incomplete_bulk_upload_rows(page: Any, log_func: Optional[Any] = None) -> int:
    """
    Finds and clicks the delete/trash icon on any bulk upload video rows that have NOT reached 100%.
    Returns the number of deleted incomplete rows.
    """
    def log(msg: str) -> None:
        if log_func:
            log_func(msg)
        else:
            print(msg)

    deleted_count = 0
    try:
        deleted_count = page.evaluate("""() => {
            let removed = 0;
            const rows = Array.from(document.querySelectorAll('div[role="row"], tr, div[class*="row"]'));
            
            for (const row of rows) {
                const rowText = (row.innerText || '').toLowerCase();
                const is100 = rowText.includes('100%') || rowText.includes('safe to publish') || rowText.includes('ready to publish');
                const hasProgress = rowText.includes('%') || rowText.includes('checking');
                
                if (hasProgress && !is100) {
                    const trashBtns = Array.from(row.querySelectorAll('button, div[role="button"], i, svg'));
                    for (const b of trashBtns) {
                        const aria = (b.getAttribute('aria-label') || b.getAttribute('title') || '').toLowerCase();
                        if (aria.includes('delete') || aria.includes('remove') || aria.includes('eliminar') || aria.includes('trash')) {
                            b.click();
                            removed++;
                            break;
                        }
                    }
                }
            }
            return removed;
        }""")
        if deleted_count > 0:
            log(f"  🗑️ Removed {deleted_count} incomplete video row(s) stuck before 100% upload!")
            time.sleep(2.0)
    except Exception:
        pass

    return deleted_count


def process_meta_bulk_composer_publishing(
    page: Any,
    log_func: Optional[Any] = None,
    upload_timeout_sec: int = 180,
    auto_delete_incomplete: bool = True
) -> bool:
    """
    Handles Meta Business Suite Bulk Upload Reels Composer publishing:
    1. Considers video ready as soon as progress reaches 100% (Does NOT wait for Copyright check).
    2. Instantly detects '100%' / 'safe to publish' on page body with humanized mouse jitter.
    3. If timeout (upload_timeout_sec) is reached and auto_delete_incomplete is True:
       removes stuck/incomplete video rows and publishes whatever videos reached 100%!
    4. Clicks the bottom-right blue 'Publish' button!
    """
    def log(msg: str) -> None:
        if log_func:
            log_func(msg)
        else:
            print(msg)

    try:
        timeout_min = max(1, upload_timeout_sec // 60)
        log(f"  ⏳ Checking video upload progress for ALL videos (Base timeout: {timeout_min} min / {upload_timeout_sec}s)...")
        start_time = time.time()
        max_wait_sec = max(30, upload_timeout_sec)
        upload_ready = False
        last_pct_str = "0%"
        last_numeric_pct = 0
        last_progress_update_time = time.time()
        STAGNANT_STALL_THRESHOLD_SEC = 75 # Instantly remove frozen video row if progress stays unchanged for >75s

        while True:
            elapsed_sec = time.time() - start_time
            time.sleep(2.0)
            
            # Dismiss any popup overlays/dialogs
            dismiss_facebook_overlays(page)

            # Evaluate status across ALL bulk upload video rows
            status = page.evaluate("""() => {
                const rowElements = Array.from(document.querySelectorAll('div[role="row"], tr, div[class*="row"]'));
                let totalVideoRows = 0;
                let completedRows = 0;
                let incompleteRows = 0;
                let minPct = 100;
                let maxPct = 0;
                
                for (const r of rowElements) {
                    const txt = (r.innerText || '').toLowerCase();
                    if (txt.includes('%') || txt.includes('checking for copyrighted') || txt.includes('ready to publish') || txt.includes('safe to publish')) {
                        totalVideoRows++;
                        const matches = Array.from(txt.matchAll(/\\b(\\d{1,3})%/g));
                        if (matches.length > 0) {
                            const pcts = matches.map(m => parseInt(m[1], 10)).filter(n => n <= 100);
                            if (pcts.length > 0) {
                                const pVal = Math.min(...pcts);
                                const pMax = Math.max(...pcts);
                                if (pVal < minPct) minPct = pVal;
                                if (pMax > maxPct) maxPct = pMax;
                            }
                        }
                        const is100 = txt.includes('100%') || txt.includes('safe to publish') || txt.includes('ready to publish');
                        if (is100) {
                            completedRows++;
                        } else {
                            incompleteRows++;
                        }
                    }
                }

                if (totalVideoRows > 0) {
                    return {
                        total: totalVideoRows,
                        completed: completedRows,
                        incomplete: incompleteRows,
                        allReady: incompleteRows === 0,
                        maxPct: maxPct > 0 ? maxPct : (completedRows > 0 ? 100 : 0)
                    };
                }
                
                const bodyText = (document.body.innerText || '').toLowerCase();
                const matches = Array.from(bodyText.matchAll(/\\b(\\d{1,3})%/g));
                if (matches.length > 0) {
                    const pcts = matches.map(m => parseInt(m[1], 10)).filter(n => n <= 100);
                    const incompletePcts = pcts.filter(p => p < 100);
                    return {
                        total: pcts.length,
                        completed: pcts.length - incompletePcts.length,
                        incomplete: incompletePcts.length,
                        allReady: incompletePcts.length === 0,
                        maxPct: pcts.length > 0 ? Math.max(...pcts) : 0
                    };
                }

                return { total: 0, completed: 0, incomplete: 0, allReady: false, maxPct: 0 };
            }""")

            total_v = status.get("total", 0)
            comp_v = status.get("completed", 0)
            incomp_v = status.get("incomplete", 0)
            all_ready = status.get("allReady", False)
            curr_max_pct = status.get("maxPct", 0)

            if curr_max_pct > 0:
                last_pct_str = f"{curr_max_pct}%"

            # Check if percentage has increased across any uploading video (Active Progress)
            if curr_max_pct > last_numeric_pct:
                last_numeric_pct = curr_max_pct
                last_progress_update_time = time.time()
                log(f"  📈 Video upload progress active: {curr_max_pct}% ({comp_v}/{total_v} video(s) ready)...")

            # 1. Condition: ALL video rows reached 100% completion!
            if all_ready and total_v > 0:
                log(f"  ✓ ALL {total_v}/{total_v} video(s) reached 100% upload completion!")
                upload_ready = True
                break

            # 2. Check for Stagnant Stall (Percentage frozen for >75s)
            time_stuck_sec = time.time() - last_progress_update_time
            if time_stuck_sec >= STAGNANT_STALL_THRESHOLD_SEC and incomp_v > 0:
                log(f"  ⚠️ Video upload progress frozen for >{STAGNANT_STALL_THRESHOLD_SEC}s without change!")
                if auto_delete_incomplete:
                    log("  🗑️ Instantly removing frozen/stuck video row(s)...")
                    cleanup_incomplete_bulk_upload_rows(page, log_func=log)
                    time.sleep(2.0)
                    # Re-check if remaining rows are now 100% completed
                    body_txt = page.locator("body").inner_text(timeout=2000).lower()
                    if "100%" in body_txt or "safe to publish" in body_txt or "ready to publish" in body_txt:
                        upload_ready = True
                        break

            # 3. Check for Timeout & Auto-Extension (Option 2)
            if elapsed_sec >= max_wait_sec:
                # If progress was updated recently (within last 45 seconds), auto-extend timeout by +60s!
                if time.time() - last_progress_update_time < 45 and incomp_v > 0:
                    max_wait_sec += 60
                    log(f"  ⏳ Base timeout reached, but videos are still actively uploading. Auto-extending wait time by +60s...")
                else:
                    log(f"  ⏳ Max upload wait limit reached ({int(max_wait_sec)}s). Cleaning up incomplete rows...")
                    break

            # Subtle humanized mouse movement during wait
            try:
                if random.random() < 0.3:
                    page.mouse.move(random.randint(200, 800), random.randint(200, 600))
            except Exception:
                pass

        if not upload_ready:
            if auto_delete_incomplete:
                log("  🧹 Cleaning up any remaining incomplete video rows before publish check...")
                cleanup_incomplete_bulk_upload_rows(page, log_func=log)
                time.sleep(2.0)
                try:
                    body_txt = page.locator("body").inner_text(timeout=2000).lower()
                    if "100%" in body_txt or "safe to publish" in body_txt or "ready to publish" in body_txt:
                        log("  ✓ Proceeding to publish remaining 100% completed video(s)!")
                        upload_ready = True
                except Exception:
                    pass

        if not upload_ready:
            log(f"  ⚠️ Could not complete video upload because progress was stuck at {last_pct_str}!")
            return False

        # Humanized pause to simulate real user inspecting post before publishing
        time.sleep(random.uniform(2.2, 4.0))

        # Click the BIG BLUE Publish button at bottom right footer
        log("  🚀 Submitting Publish for 100% uploaded Reel video(s)...")

        published = False
        try:
            # High-precision JS evaluator for bottom-right primary blue Publish button
            published = page.evaluate("""() => {
                const buttons = Array.from(document.querySelectorAll('button, div[role="button"], a[role="button"]'));
                for (let i = buttons.length - 1; i >= 0; i--) {
                    const b = buttons[i];
                    const text = (b.innerText || '').trim();
                    if (text === 'Publish' || text === 'Publicar') {
                        b.scrollIntoView();
                        b.click();
                        return true;
                    }
                }
                return false;
            }""")
            if published:
                log("  ✅ Clicked Bottom Right Blue 'Publish' button via JS!")
                time.sleep(random.uniform(4.0, 6.0))
        except Exception:
            published = False

        if not published:
            bottom_publish_selectors = [
                "button:has-text('Publish')",
                "div[role='button']:has-text('Publish')",
                "button:has-text('Publicar')",
                "div[role='button']:has-text('Publicar')"
            ]
            for pb in bottom_publish_selectors:
                try:
                    loc = page.locator(pb)
                    count = loc.count()
                    if count > 0:
                        for i in range(count - 1, -1, -1):
                            btn = loc.nth(i)
                            if btn.is_visible(timeout=1200):
                                try:
                                    btn.hover()
                                    time.sleep(random.uniform(0.3, 0.6))
                                except Exception:
                                    pass
                                btn.scroll_into_view_if_needed()
                                time.sleep(0.3)
                                btn.click(force=True)
                                log("  ✅ Clicked Bottom Right Blue 'Publish' button!")
                                published = True
                                time.sleep(random.uniform(4.0, 6.0))
                                break
                    if published:
                        break
                except Exception:
                    continue

        if not published:
            try:
                page.locator("button:has-text('Publish')").first.click(force=True)
                published = True
            except Exception:
                pass

        # Handle 'Your bulk upload is processing!' confirmation dialog -> Click Done
        done_selectors = [
            "div[role='dialog'] button:has-text('Done')",
            "div[role='dialog'] div[role='button']:has-text('Done')",
            "div[role='dialog'] div[aria-label='Done']",
            "div[role='dialog'] button:has-text('Listo')",
            "div[role='dialog'] div[role='button']:has-text('Listo')",
            "button:has-text('Done')",
            "div[role='button']:has-text('Done')"
        ]
        for d_sel in done_selectors:
            try:
                d_btn = page.locator(d_sel).first
                if d_btn.is_visible(timeout=3500):
                    time.sleep(random.uniform(1.2, 2.2))
                    d_btn.click(force=True)
                    log("  ✓ Clicked 'Done' button on upload confirmation popup.")
                    time.sleep(random.uniform(2.0, 3.5))
                    break
            except Exception:
                continue

        return published
    except Exception as err:
        log(f"  ⚠️ Meta Bulk Composer publishing note: {err}")
        return False


class FbPublisherThread(QThread):
    """
    Background thread supporting Concurrent Multi-Thread Parallel Execution (up to 15 browsers simultaneously)
    across Facebook profiles in a selected Group using local isolated browser profiles.
    """

    log_emitted = Signal(str)
    progress_updated = Signal(int, int) # current, total
    finished_signal = Signal(bool, str)

    def __init__(
        self,
        profile_mgr: Any,
        profiles_list: List[Dict[str, Any]],
        video_path: Optional[Path] = None,
        video_folder: Optional[Path] = None,
        videos_per_id: int = 1,
        max_concurrent_browsers: int = 1,
        selection_mode: str = "Sequential",
        delay_seconds: int = 5,
        title_text: str = "",
        title_lines: Optional[List[str]] = None,
        caption_text: str = "",
        caption_lines: Optional[List[str]] = None,
        enable_auto_comment: bool = False,
        comment_rows: Optional[List[Dict[str, Any]]] = None,
        auto_delete_on_fail: bool = True,
        headless: bool = False,
        auto_select_first_page: bool = True,
        upload_timeout_sec: int = 180,
        auto_delete_incomplete: bool = True,
        enable_serial_matching: bool = False,
        parent: Optional[Any] = None
    ) -> None:
        super().__init__(parent)
        self.profile_mgr = profile_mgr
        self.profiles_list = profiles_list
        self.video_path = video_path
        self.video_folder = video_folder
        self.videos_per_id = max(1, videos_per_id)
        self.max_concurrent_browsers = max(1, min(15, max_concurrent_browsers))
        self.selection_mode = selection_mode
        self.delay_seconds = max(1, delay_seconds)
        self.title_text = title_text.strip()
        self.title_lines = title_lines or [line.strip() for line in title_text.splitlines() if line.strip()]
        self.caption_text = caption_text.strip()
        self.caption_lines = caption_lines or [line.strip() for line in caption_text.splitlines() if line.strip()]
        self.enable_auto_comment = enable_auto_comment
        self.comment_rows = comment_rows or []
        self.auto_delete_on_fail = auto_delete_on_fail
        self.headless = headless
        self.auto_select_first_page = auto_select_first_page
        self.upload_timeout_sec = max(30, upload_timeout_sec)
        self.auto_delete_incomplete = auto_delete_incomplete
        self.enable_serial_matching = enable_serial_matching

    def _get_folder_videos(self) -> List[Path]:
        """Scan and return sorted video files from folder."""
        if not self.video_folder or not self.video_folder.exists():
            return []
        valid_exts = (".mp4", ".mov", ".mkv", ".avi", ".webm")
        files = [f for f in self.video_folder.iterdir() if f.is_file() and f.suffix.lower() in valid_exts]
        if self.enable_serial_matching:
            files.sort(key=lambda x: [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', x.name)])
        else:
            files.sort(key=lambda x: x.name.lower())
        return files

    def _get_comment_list(self) -> List[str]:
        """Extract comment strings dynamically from loaded Excel rows."""
        comments = []
        for r in self.comment_rows:
            if not isinstance(r, dict):
                continue

            c_val = ""
            for k, v in r.items():
                if str(k).lower() in ("comment", "comments", "text", "content"):
                    c_val = str(v).strip()
                    break

            if not c_val and r.values():
                c_val = str(list(r.values())[0]).strip()

            if c_val:
                comments.append(c_val)

        return comments

    def _process_single_profile(
        self,
        p_idx: int,
        total_profiles: int,
        profile_data: Dict[str, Any],
        folder_videos: List[Path],
        comment_list: List[str]
    ) -> int:
        """Process video upload & optional comment injection for a single profile worker task."""
        p_num = profile_data.get("number", "Profile")
        p_name = profile_data.get("name", p_num)
        p_folder = self.profile_mgr.get_profile_folder(profile_data["id"])

        if self.video_folder and folder_videos:
            if not self.enable_serial_matching or self.selection_mode == "Random":
                if len(folder_videos) >= self.videos_per_id:
                    current_batch = random.sample(folder_videos, self.videos_per_id)
                else:
                    current_batch = [random.choice(folder_videos) for _ in range(self.videos_per_id)]
            else:
                start_offset = (p_idx - 1) * self.videos_per_id
                current_batch = [
                    folder_videos[(start_offset + v_i) % len(folder_videos)]
                    for v_i in range(self.videos_per_id)
                ]
        else:
            current_batch = [self.video_path] * self.videos_per_id

        self.log_emitted.emit(f"\n==========================================")
        self.log_emitted.emit(f"👤 [{p_idx}/{total_profiles}] Worker Profile: {p_name} ({p_num})")
        self.log_emitted.emit(f"🎬 Assigned Batch ({len(current_batch)} videos): {[v.name for v in current_batch]}")
        self.log_emitted.emit(f"==========================================")

        published_count = 0

        try:
            with sync_playwright() as p:
                args = [
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-background-networking",
                    "--disable-component-update",
                    "--disable-domain-reliability",
                    "--disable-client-side-phishing-detection",
                    "--disable-notifications",
                    "--disable-popup-blocking",
                    "--deny-permission-prompts",
                    "--test-type",
                    "--disable-infobars",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--lang=en-US",
                    "--disable-save-password-bubble",
                    "--password-store=basic"
                ]
                ensure_profile_session_persistence(p_folder)
                try:
                    from common_playwright import init_bot_browser_context
                except ImportError:
                    try:
                        from core.common_playwright import init_bot_browser_context
                    except ImportError:
                        init_bot_browser_context = None

                if init_bot_browser_context:
                    context, page, is_logged_in, connected_via_cdp = init_bot_browser_context(
                        playwright_instance=p,
                        profile_data=profile_data,
                        profile_index=p_idx,
                        headless=self.headless,
                        log_func=lambda msg: self.log_emitted.emit(msg)
                    )
                else:
                    chrome_exe = get_chrome_executable_path()
                    launch_kwargs = {
                        "user_data_dir": str(p_folder.resolve()),
                        "headless": self.headless,
                        "user_agent": profile_data.get("user_agent", ""),
                        "locale": "en-US",
                        "extra_http_headers": {"Accept-Language": "en-US,en;q=0.9"},
                        "permissions": [],
                        "args": args,
                        "ignore_default_args": ["--enable-automation"]
                    }
                    if chrome_exe and os.path.exists(chrome_exe):
                        launch_kwargs["executable_path"] = chrome_exe
                    context = p.chromium.launch_persistent_context(**launch_kwargs)
                    page = context.pages[0] if context.pages else context.new_page()

                configure_antidetect_context(context, profile_data)

                # Always inject saved database session cookies into browser context upon launch
                try:
                    cookie_str = profile_data.get("cookie", "") or profile_data.get("cookies", "")
                    if cookie_str:
                        parsed_ck = parse_cookie_string(cookie_str, default_domain=".facebook.com")
                        if parsed_ck:
                            parsed_ck.append({"name": "locale", "value": "en_US", "domain": ".facebook.com", "path": "/"})
                            context.add_cookies(parsed_ck)
                except Exception:
                    pass

                # Stealth JS Injection: Mask navigator.webdriver & simulate authentic Chrome environment
                stealth_script = """
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    window.chrome = { runtime: {} };
                    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en', 'es'] });
                    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4] });
                """
                context.add_init_script(stealth_script)

                page = context.pages[0] if context.pages else context.new_page()
                self.log_emitted.emit(f"  🌐 [{p_name}] Opening Facebook...")
                try:
                    page.goto("https://www.facebook.com/", timeout=20000, wait_until="domcontentloaded")
                except Exception:
                    pass
                time.sleep(1.5)

                # LOGIN STATUS CHECK & AUTO RE-LOGIN / AUTO-PURGE
                is_logged_in, login_msg = check_facebook_login_status(page, context)
                if is_logged_in:
                    self.log_emitted.emit(f"  ✅ [{p_name}] Active Facebook session verified (Already logged in)!")
                    sync_active_cookies_to_profile(context, getattr(self, "profile_mgr", None), pid if "pid" in locals() else profile_data.get("id"))
                else:
                    self.log_emitted.emit(f"  ⚠️ [{p_name}] Session is LOGGED OUT ({login_msg}). Attempting automatic re-login using stored credentials...")
                    relogin_ok = attempt_profile_relogin(
                        page=page,
                        context=context,
                        profile_data=profile_data,
                        log_func=lambda text: self.log_emitted.emit(text)
                    )
                    if not relogin_ok:
                        if self.auto_delete_on_fail:
                            self.log_emitted.emit(f"  ❌ [{p_name}] SKIPPED & PURGED: Re-login failed (account locked/invalid). Purging browser profile & deleting from database...")
                            if context:
                                context.close()
                            p_id = profile_data.get("id")
                            if p_id:
                                self.profile_mgr.delete_profile(p_id)
                        else:
                            self.log_emitted.emit(f"  ⚠️ [{p_name}] SKIPPED: Re-login failed (Auto-Delete is OFF). Profile retained in database.")
                            if context:
                                context.close()
                        return 0

                # Extract & save fresh session cookies to database
                try:
                    new_cookies = context.cookies()
                    if new_cookies:
                        ck_str = "; ".join([f"{c['name']}={c['value']}" for c in new_cookies if c.get("name") and c.get("value")])
                        self.profile_mgr.update_profile(profile_data["id"], cookie=ck_str)
                except Exception:
                    pass

                # DIRECT NAVIGATION TO META BUSINESS SUITE BULK COMPOSER
                self.log_emitted.emit(f"  🌐 [{p_name}] Navigating directly to Meta Business Suite Bulk Upload Reels Composer...")
                meta_bulk_url = "https://business.facebook.com/latest/bulk_upload_composer"
                try:
                    page.goto(meta_bulk_url, timeout=45000, wait_until="domcontentloaded")
                    time.sleep(random.uniform(3.0, 4.5))
                except Exception as meta_err:
                    self.log_emitted.emit(f"  ⚠️ [{p_name}] Meta Business Suite nav note: {meta_err}")

                # MULTI-CONDITION DIRECT VERIFICATION FOR FACEBOOK PAGE ASSET
                curr_url = page.url.lower()
                body_txt = ""
                try:
                    body_txt = (page.locator("body").inner_text(timeout=3000) or "").lower()
                except Exception:
                    pass

                no_page_indicators = [
                    "unable to access meta business suite",
                    "create a facebook page",
                    "does not have access to any facebook pages",
                    "create page",
                    "crear una página"
                ]

                has_no_page_screen = any(ind in body_txt for ind in no_page_indicators)
                is_redirected_away = "business.facebook.com" not in curr_url and "bulk_upload" not in curr_url

                if has_no_page_screen or is_redirected_away:
                    self.log_emitted.emit(f"  ❌ [{p_name}] SKIPPED: Account does NOT have any active Facebook Page asset (Detected on Meta Business Suite). Closing browser to protect personal account...")
                    if context:
                        try:
                            context.close()
                        except Exception:
                            pass
                    return 0

                self.log_emitted.emit(f"  ✅ [{p_name}] Active Facebook Page asset verified on Meta Business Suite!")

                # STEP 3: Attach all batch videos into Meta Business Suite Bulk Upload Composer
                batch_video_paths = [str(v.resolve()) for v in current_batch]
                self.log_emitted.emit(f"\n  ▶️ [{p_name}] Attaching {len(batch_video_paths)} video file(s) to Meta Business Suite Bulk Composer...")
                
                files_attached = False
                try:
                    file_inputs = page.locator("input[type='file']")
                    if file_inputs.count() > 0:
                        file_inputs.first.set_input_files(batch_video_paths)
                        self.log_emitted.emit(f"  ✓ [{p_name}] Attached {len(batch_video_paths)} video file(s) to Meta Business Suite")
                        files_attached = True
                        time.sleep(4.0)
                except Exception:
                    pass

                if not files_attached:
                    add_video_triggers = [
                        "button:has-text('Add videos')",
                        "div[role='button']:has-text('Add videos')",
                        "span:has-text('Add videos')",
                        "button:has-text('Agregar videos')",
                        "div[role='button']:has-text('Agregar videos')"
                    ]
                    for av_tr in add_video_triggers:
                        try:
                            av_elem = page.locator(av_tr).first
                            if av_elem.is_visible(timeout=1500):
                                try:
                                    with page.expect_file_chooser(timeout=2500) as fc_info:
                                        av_elem.click(force=True)
                                    fc_info.value.set_files(batch_video_paths)
                                    self.log_emitted.emit(f"  ✓ [{p_name}] Attached video(s) via 'Add videos' chooser")
                                    files_attached = True
                                    time.sleep(4.0)
                                    break
                                except Exception:
                                    av_elem.click(force=True)
                                    time.sleep(1.5)
                                    inputs = page.locator("input[type='file']")
                                    if inputs.count() > 0:
                                        inputs.first.set_input_files(batch_video_paths)
                                        files_attached = True
                                        time.sleep(4.0)
                                        break
                        except Exception:
                            continue

                if files_attached:
                    # 15-Second Stuck at 0% Upload Check
                    self.log_emitted.emit(f"  ⏳ [{p_name}] Monitoring video upload start (15-second 0% timeout check)...")
                    upload_started = False
                    start_chk_time = time.time()
                    
                    while time.time() - start_chk_time < 15.0:
                        time.sleep(1.5)
                        progressed, reason = check_meta_bulk_upload_progress(page)
                        if progressed:
                            upload_started = True
                            self.log_emitted.emit(f"  ✓ [{p_name}] Video upload started successfully (Progress detected: '{reason}')")
                            break

                    if not upload_started:
                        self.log_emitted.emit(f"  ⚠️ [{p_name}] Could not complete video upload because progress was stuck at 0%! Skipping this profile...")
                        if context:
                            try:
                                context.close()
                            except Exception:
                                pass
                        return 0

                    # STEP 4: Assign line-by-line unique title and description/caption to each Reel row in Meta Bulk Composer
                    self.log_emitted.emit(f"  📝 [{p_name}] Assigning titles & descriptions to all {len(current_batch)} Reel(s)...")
                    time.sleep(2.0)

                    batch_titles = []
                    batch_captions = []
                    for v_i in range(len(current_batch)):
                        global_v_idx = (p_idx - 1) * self.videos_per_id + v_i
                        if self.enable_serial_matching:
                            if self.title_lines:
                                t_line = self.title_lines[global_v_idx] if global_v_idx < len(self.title_lines) else self.title_lines[global_v_idx % len(self.title_lines)]
                            else:
                                t_line = self.title_text

                            if self.caption_lines:
                                c_line = self.caption_lines[global_v_idx] if global_v_idx < len(self.caption_lines) else self.caption_lines[global_v_idx % len(self.caption_lines)]
                            else:
                                c_line = self.caption_text

                            v_name = current_batch[v_i].name
                            c_short = c_line[:30] + ("..." if len(c_line) > 30 else "")
                            self.log_emitted.emit(f"  🔄 Serial Pair #{global_v_idx + 1}: Video '{v_name}' ➡️ Title: '{t_line}' ➡️ Caption: '{c_short}'")
                        else:
                            if self.title_lines:
                                t_line = random.choice(self.title_lines)
                            else:
                                t_line = self.title_text

                            if self.caption_lines:
                                c_line = random.choice(self.caption_lines)
                            else:
                                c_line = self.caption_text

                            v_name = current_batch[v_i].name
                            c_short = c_line[:30] + ("..." if len(c_line) > 30 else "")
                            self.log_emitted.emit(f"  🎲 Random Selection: Video '{v_name}' ➡️ Title: '{t_line}' ➡️ Caption: '{c_short}'")

                        batch_titles.append(t_line)
                        batch_captions.append(c_line)

                    # Execute Playwright native locator assignment separating Title fields and Description fields
                    try:
                        pasted_title_count = 0
                        pasted_caption_count = 0
                        
                        box_locators = page.locator("input[type='text'], input:not([type]), textarea, div[contenteditable='true'], [role='textbox']")
                        box_count = box_locators.count()
                        
                        valid_title_boxes = []
                        valid_desc_boxes = []
                        
                        for b_i in range(box_count):
                            b_loc = box_locators.nth(b_i)
                            try:
                                if b_loc.is_visible(timeout=400):
                                    is_nav = b_loc.evaluate("el => !!el.closest('header, nav, [role=\"navigation\"]')")
                                    if not is_nav:
                                        info = b_loc.evaluate("""el => {
                                            const aria = (el.getAttribute('aria-label') || '').toLowerCase();
                                            const ph = (el.getAttribute('placeholder') || '').toLowerCase();
                                            const name = (el.getAttribute('name') || '').toLowerCase();
                                            const parentTxt = (el.parentElement ? el.parentElement.innerText : '').toLowerCase();
                                            
                                            const isTitle = aria.includes('title') || ph.includes('title') || name.includes('title') ||
                                                            aria.includes('add a title') || ph.includes('add a title') ||
                                                            parentTxt.includes('video title') || parentTxt.includes('title (optional)') ||
                                                            parentTxt.includes('add a title') || parentTxt.includes('title');
                                            
                                            const isDesc = aria.includes('desc') || ph.includes('desc') || aria.includes('caption') ||
                                                           ph.includes('caption') || aria.includes('describe') || ph.includes('describe');
                                            
                                            return { isTitle: isTitle, isDesc: isDesc };
                                        }""")
                                        
                                        if info["isTitle"]:
                                            valid_title_boxes.append(b_loc)
                                        else:
                                            valid_desc_boxes.append(b_loc)
                            except Exception:
                                pass

                        # 1. Fill Title fields if title boxes detected and titles provided
                        if valid_title_boxes:
                            self.log_emitted.emit(f"  📌 [{p_name}] Detected {len(valid_title_boxes)} Reel Title box(es) on page.")
                            for i, box in enumerate(valid_title_boxes):
                                if i < len(batch_titles):
                                    title_str = batch_titles[i]
                                    if not title_str:
                                        continue
                                    try:
                                        box.scroll_into_view_if_needed()
                                        time.sleep(0.2)
                                        box.click(force=True)
                                        time.sleep(0.3)
                                        page.keyboard.press("Control+A")
                                        page.keyboard.press("Backspace")
                                        time.sleep(0.1)
                                        page.keyboard.insert_text(title_str)
                                        time.sleep(0.3)
                                        box.evaluate("""(el, text) => {
                                            if (!el.innerText || !el.innerText.includes(text.substring(0, 5))) {
                                                if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') el.value = text;
                                                else el.innerText = text;
                                            }
                                            el.dispatchEvent(new InputEvent('beforeinput', { bubbles: true, cancelable: true, inputType: 'insertText', data: text }));
                                            el.dispatchEvent(new InputEvent('input', { bubbles: true, cancelable: true, inputType: 'insertText', data: text }));
                                            el.dispatchEvent(new Event('change', { bubbles: true }));
                                        }""", title_str)
                                        pasted_title_count += 1
                                        self.log_emitted.emit(f"  ✓ [{p_name}] Pasted title line #{i+1} into Reel Title field!")
                                        time.sleep(random.uniform(0.3, 0.6))
                                    except Exception as t_err:
                                        self.log_emitted.emit(f"  ⚠️ [{p_name}] Note pasting title line #{i+1}: {t_err}")

                        # 2. Fill Description / Caption fields
                        for i, box in enumerate(valid_desc_boxes):
                            if i < len(batch_captions):
                                caption = batch_captions[i]
                                if not caption:
                                    continue

                                try:
                                    box.scroll_into_view_if_needed()
                                    time.sleep(0.2)
                                    box.click(force=True)
                                    time.sleep(0.3)

                                    page.keyboard.press("Control+A")
                                    page.keyboard.press("Backspace")
                                    time.sleep(0.1)

                                    page.keyboard.insert_text(caption)
                                    time.sleep(0.3)

                                    box.evaluate("""(el, text) => {
                                        if (!el.innerText || !el.innerText.includes(text.substring(0, 5))) {
                                            if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') el.value = text;
                                            else el.innerText = text;
                                        }
                                        el.dispatchEvent(new InputEvent('beforeinput', { bubbles: true, cancelable: true, inputType: 'insertText', data: text }));
                                        el.dispatchEvent(new InputEvent('input', { bubbles: true, cancelable: true, inputType: 'insertText', data: text }));
                                        el.dispatchEvent(new Event('change', { bubbles: true }));
                                    }""", caption)

                                    pasted_caption_count += 1
                                    self.log_emitted.emit(f"  ✓ [{p_name}] Pasted active black caption line #{i+1} into Reel description box!")
                                    time.sleep(random.uniform(0.4, 0.8))
                                except Exception as paste_err:
                                    self.log_emitted.emit(f"  ⚠️ [{p_name}] Note pasting caption line #{i+1}: {paste_err}")

                        if pasted_caption_count > 0 or pasted_title_count > 0:
                            self.log_emitted.emit(f"  ✓ [{p_name}] Successfully assigned active content ({pasted_title_count} titles, {pasted_caption_count} captions) to Reel boxes!")
                    except Exception as caption_err:
                        self.log_emitted.emit(f"  ⚠️ [{p_name}] Note on bulk content assignment: {caption_err}")

                    # STEP 5: Execute Immediate 100% Upload Publishing for entire batch
                    was_posted = process_meta_bulk_composer_publishing(
                        page=page,
                        log_func=lambda text: self.log_emitted.emit(f"  [{p_name}] {text}"),
                        upload_timeout_sec=self.upload_timeout_sec,
                        auto_delete_incomplete=self.auto_delete_incomplete
                    )
                    if was_posted:
                        published_count += len(current_batch)
                        self.log_emitted.emit(f"  🚀 [{p_name}] Published bulk video batch ({len(current_batch)} reel(s)) via Meta Business Suite!")

                    screenshot_path = p_folder / f"fb_page_bulk_video_p{p_idx}.png"
                    try:
                        page.screenshot(path=str(screenshot_path))
                        self.log_emitted.emit(f"  📸 Saved proof screenshot: {screenshot_path.name}")
                    except Exception:
                        pass

                else:
                    # Cancel fallback to personal profile feed to protect user's personal timeline
                    self.log_emitted.emit(f"  🛑 [{p_name}] SKIPPED: Account does NOT have an active Page asset (or Meta Business Suite attachment failed). Personal profile posting is strictly disabled.")

                if context:
                    context.close()
                time.sleep(1)
                time.sleep(1)

        except Exception as p_err:
            self.log_emitted.emit(f"  ⚠️ Exception on profile worker {p_name}: {p_err}")

        return published_count

    def run(self) -> None:
        """Execute automated video publishing loop across selected Facebook profiles in parallel thread pool."""
        total_profiles = len(self.profiles_list)
        if total_profiles == 0:
            self.finished_signal.emit(False, "No profiles found in the selected target group.")
            return

        folder_videos = self._get_folder_videos() if self.video_folder else []
        comment_list = self._get_comment_list() if self.enable_auto_comment else []

        if not self.video_folder and (not self.video_path or not self.video_path.exists()):
            self.finished_signal.emit(False, "No valid video file or folder selected.")
            return

        if self.video_folder and not folder_videos:
            self.finished_signal.emit(False, f"No video files (.mp4, .mov) found in folder: {self.video_folder}")
            return

        self.log_emitted.emit(f"🚀 Starting Multi-Thread Parallel Video Publisher for {total_profiles} Facebook IDs...")
        self.log_emitted.emit(f"⚡ Parallel Execution: {self.max_concurrent_browsers} Concurrent Browsers")
        self.log_emitted.emit(f"⚙️ Configuration: {self.videos_per_id} Video(s) per ID | Mode: {self.selection_mode} | Delay: {self.delay_seconds}s")
        if self.enable_auto_comment and comment_list:
            self.log_emitted.emit(f"💬 Excel Auto-Comment Enabled ({len(comment_list)} comments loaded)")

        total_published = 0
        completed_profiles = 0

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_concurrent_browsers) as executor:
                futures = {}
                for p_idx, profile_data in enumerate(self.profiles_list, start=1):
                    fut = executor.submit(
                        self._process_single_profile,
                        p_idx,
                        total_profiles,
                        profile_data,
                        folder_videos,
                        comment_list
                    )
                    futures[fut] = (p_idx, profile_data)

                for fut in concurrent.futures.as_completed(futures):
                    completed_profiles += 1
                    self.progress_updated.emit(completed_profiles, total_profiles)
                    try:
                        pub_count = fut.result()
                        total_published += pub_count
                    except Exception as exc:
                        p_info = futures[fut][1].get("name", "")
                        self.log_emitted.emit(f"⚠️ Worker task error on profile {p_info}: {exc}")

            self.finished_signal.emit(True, f"Multi-Thread Parallel Publishing Complete! Total {total_published} video posts published across {total_profiles} Facebook IDs!")

        except Exception as err:
            self.finished_signal.emit(False, f"Facebook Multi-Thread Auto Publisher error: {str(err)}")


def post_comment_on_first_reel(
    page: Any,
    comment_text: str,
    log_func: Optional[Any] = None
) -> Tuple[bool, str]:
    """
    Automated Facebook Reels Commenter:
    1. Navigates to active Page's Reels Tab (www.facebook.com/me?sk=reels_tab) or clicks Reels link.
    2. Clicks the 1st Reel video thumbnail or navigates directly to 1st Reel URL.
    3. Locates 'Comment as <Page Name>' textbox.
    4. Humanized types the line-by-line comment.
    5. Submits comment (Paper plane icon or Enter key).
    """
    def _log(msg: str) -> None:
        if log_func:
            log_func(msg)

    _log("  🎬 Navigating to Page Profile's OWN Reels Tab...")
    try:
        # 1. Open active Page Profile page (https://www.facebook.com/me)
        page.goto("https://www.facebook.com/me", wait_until="domcontentloaded", timeout=20000)
        time.sleep(2.5)

        # 2. Extract actual Page Profile URL (e.g., www.facebook.com/profile.php?id=6157738642303 or www.facebook.com/PageName)
        profile_url = page.url
        _log(f"  📌 Active Page Profile URL: {profile_url}")

        if "sk=reels_tab" not in profile_url and "reels_tab" not in profile_url:
            if "?id=" in profile_url or "profile.php" in profile_url:
                target_reels_url = f"{profile_url}&sk=reels_tab"
            else:
                clean_url = profile_url.rstrip("/")
                target_reels_url = f"{clean_url}?sk=reels_tab" if "?" not in clean_url else f"{clean_url}&sk=reels_tab"

            _log(f"  ⏩ Opening Page's OWN Reels tab URL: {target_reels_url}")
            page.goto(target_reels_url, wait_until="domcontentloaded", timeout=20000)
            time.sleep(3.0)

        # Fallback: Click 'Reels' tab on Page Profile header if URL did not load reels tab
        if "reels_tab" not in page.url:
            profile_reels_tab = page.locator("a[role='tab']:has-text('Reels'), div[role='tab']:has-text('Reels')").first
            if profile_reels_tab.is_visible(timeout=2000):
                profile_reels_tab.click(force=True)
                time.sleep(3.0)
    except Exception as nav_err:
        _log(f"  ⚠️ Page Reels tab navigation note: {nav_err}")

    # Step 2: Open Page's OWN 1st Reel video strictly from 'div[role="main"]' grid
    _log("  ▶️ Opening Page's OWN 1st Reel video under 'Your Reels'...")
    reel_clicked = False

    # Strategy A: Extract direct Reel href from div[role='main'] grid ONLY
    try:
        reel_href = page.evaluate("""
            () => {
                const main = document.querySelector("div[role='main']");
                if (!main) return null;
                const links = Array.from(main.querySelectorAll("a[href*='/reel/'], a[href*='/reels/']"));
                for (let link of links) {
                    const rect = link.getBoundingClientRect();
                    if (rect.top > 180 && link.href && (link.href.includes('/reel/') || link.href.includes('/reels/'))) {
                        return link.href;
                    }
                }
                return null;
            }
        """)
        if reel_href:
            _log(f"  ▶️ Found Page's OWN Reel URL: '{reel_href[:55]}...'. Opening video...")
            page.goto(reel_href, wait_until="domcontentloaded", timeout=20000)
            reel_clicked = True
            time.sleep(3.5)
    except Exception as e_href:
        _log(f"  ⚠️ Direct href check note: {e_href}")

    # Strategy B: Click 1st vertical video thumbnail inside div[role='main'] grid ONLY
    if not reel_clicked:
        try:
            reel_clicked = page.evaluate("""
                () => {
                    const main = document.querySelector("div[role='main']");
                    if (!main) return false;
                    const imgs = Array.from(main.querySelectorAll("img"));
                    for (let img of imgs) {
                        const rect = img.getBoundingClientRect();
                        if (rect.top > 200 && rect.width >= 60 && rect.width <= 450 && rect.height >= 100) {
                            img.scrollIntoView({ block: 'center' });
                            const target = img.closest("a") || img.closest("div[role='button']") || img.closest("div[role='article']") || img;
                            if (target.tagName === 'A' && target.href && target.href.includes('/reel/')) {
                                window.location.href = target.href;
                                return true;
                            }
                            ['mouseover', 'mousedown', 'mouseup', 'click'].forEach(eventType => {
                                target.dispatchEvent(new MouseEvent(eventType, { bubbles: true, cancelable: true, view: window }));
                            });
                            if (typeof target.click === 'function') {
                                target.click();
                            }
                            return true;
                        }
                    }
                    return false;
                }
            """)
            if reel_clicked:
                _log("  ▶️ Triggered click on Page's OWN 1st Reel thumbnail image.")
                time.sleep(3.5)
        except Exception as e_dom:
            _log(f"  ⚠️ DOM click note: {e_dom}")

    # Strategy C: Playwright locator click inside div[role='main'] grid ONLY
    if not reel_clicked:
        try:
            cards = page.locator("div[role='main'] a[href*='/reel/'], div[role='main'] div[role='article'] img")
            if cards.count() > 0:
                for i in range(cards.count()):
                    c = cards.nth(i)
                    box = c.bounding_box()
                    if box and box['y'] > 200 and box['width'] > 60:
                        c.scroll_into_view_if_needed()
                        c.click(force=True)
                        reel_clicked = True
                        time.sleep(3.5)
                        break
        except Exception as e_loc:
            _log(f"  ⚠️ Locator click note: {e_loc}")

    if not reel_clicked:
        return False, "Could not locate or click the Page's OWN 1st Reel video thumbnail on page."

    # Step 2.5: Pause Reel Video Playback by clicking video container or executing DOM pause
    _log("  ⏸️ Pausing Reel video playback for quiet comment typing...")
    try:
        page.evaluate("""
            () => {
                const video = document.querySelector("video");
                if (video) {
                    video.pause();
                    video.dispatchEvent(new Event('pause'));
                }
            }
        """)
        time.sleep(1.0)
    except Exception:
        try:
            v_loc = page.locator("video").first
            if v_loc.is_visible(timeout=1000):
                v_loc.click(force=True)
                time.sleep(1.0)
        except Exception:
            pass

    # Step 2.7: Ensure Comment Panel Drawer is Open (Click Speech Bubble Icon if needed)
    _log("  💬 Opening Reel Comments Drawer...")
    try:
        box_already_open = False
        for sel in ["div[aria-label*='Comment as' i]", "div[aria-label*='Write a comment' i]", "div[role='textbox']"]:
            if page.locator(sel).first.is_visible(timeout=1000):
                box_already_open = True
                break

        if not box_already_open:
            _log("  👉 Clicking comment speech bubble icon on video player...")
            icon_clicked = page.evaluate("""
                () => {
                    const buttons = Array.from(document.querySelectorAll("div[role='button']"));
                    for (let b of buttons) {
                        const label = (b.getAttribute('aria-label') || '').toLowerCase();
                        if (label.includes('comment') || label.includes('comentar')) {
                            b.click();
                            return true;
                        }
                    }
                    return false;
                }
            """)
            if icon_clicked:
                time.sleep(2.0)
            else:
                for c_sel in ["div[aria-label*='Comment' i]", "div[aria-label*='Comments' i]"]:
                    c_btn = page.locator(c_sel).first
                    if c_btn.is_visible(timeout=1500):
                        c_btn.click(force=True)
                        time.sleep(2.0)
                        break
    except Exception as drawer_err:
        _log(f"  ⚠️ Comments drawer note: {drawer_err}")

    # Step 3: Humanized Anti-Bot Pre-Interactions & Comment Writing
    _log("  🤖 Stealth Anti-Bot: Simulating natural human reading & mouse movement...")
    try:
        for _ in range(random.randint(2, 4)):
            page.mouse.move(random.randint(300, 900), random.randint(200, 700))
            time.sleep(random.uniform(0.3, 0.7))
        page.mouse.wheel(0, random.randint(100, 250))
        time.sleep(random.uniform(1.8, 3.2))
    except Exception:
        pass

    # Sanitize comment string into a clean single line (strip internal newlines/carriage returns)
    clean_comment = " ".join(comment_text.replace("\r", " ").replace("\n", " ").split()).strip()
    if not clean_comment:
        clean_comment = "Awesome Reel! 🔥"

    _log(f"  💬 Writing Reel comment: '{clean_comment[:40]}...'")
    comment_box = None
    try:
        selectors = [
            "div[aria-label*='Comment as' i]",
            "div[aria-label*='Write a comment' i]",
            "div[aria-label*='Comment' i][role='textbox']",
            "div[contenteditable='true'][role='textbox']",
            "textarea[placeholder*='Comment' i]",
            "div[role='textbox']"
        ]
        for sel in selectors:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=3000):
                comment_box = loc
                break

        if not comment_box:
            return False, "Comment box ('Comment as Page') not found on Reel video player."

        comment_box.scroll_into_view_if_needed()
        time.sleep(random.uniform(0.8, 1.5))
        comment_box.click(force=True)
        time.sleep(random.uniform(0.5, 1.0))

        # Focus, clear any existing draft, and insert single-line comment natively
        typed_ok = False
        try:
            comment_box.focus()
            time.sleep(0.2)
            page.keyboard.press("Control+A")
            time.sleep(0.1)
            page.keyboard.press("Backspace")
            time.sleep(0.2)
            page.keyboard.insert_text(clean_comment)
            time.sleep(0.8)
            typed_ok = True
        except Exception:
            pass

        if not typed_ok:
            humanized_type_text(comment_box, clean_comment, page=page)

        time.sleep(random.uniform(1.2, 2.5))

        # Step 4: Multi-Strategy Comment Submission
        _log("  🚀 Submitting Reel comment...")

        # 4A: Dismiss quick reaction bar overlay if close button '✖' is visible
        try:
            close_rxn_btn = page.locator("div[aria-label*='Close' i], div[aria-label*='Dismiss' i]").first
            if close_rxn_btn.is_visible(timeout=1000):
                close_rxn_btn.click(force=True)
                time.sleep(0.5)
        except Exception:
            pass

        # 4B: Press 'Enter' key directly inside focused comment box
        try:
            comment_box.focus()
            time.sleep(0.4)
            comment_box.press("Enter")
            time.sleep(2.0)
        except Exception:
            pass

        # 4C: Click paper plane submit button (blue arrow icon)
        try:
            submit_selectors = [
                "div[aria-label*='Comment' i][role='button']",
                "div[aria-label*='Send' i]",
                "div[aria-label*='Post' i]",
                "button[type='submit']"
            ]
            for s_sel in submit_selectors:
                s_btn = page.locator(s_sel).first
                if s_btn.is_visible(timeout=1000):
                    s_btn.click(force=True)
                    time.sleep(2.0)
                    break
        except Exception:
            pass

        # 4D: JS Event dispatch fallback for Enter key
        try:
            page.evaluate("""
                () => {
                    const boxes = Array.from(document.querySelectorAll("div[role='textbox'], div[contenteditable='true']"));
                    for (let b of boxes) {
                        const evt = new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true });
                        b.dispatchEvent(evt);
                    }
                }
            """)
            time.sleep(2.0)
        except Exception:
            pass

        _log(f"  ⏳ Comment submitted! Waiting 7-10 seconds for Facebook comment sync...")
        time.sleep(random.uniform(7.0, 10.0))

        # Step 5: Post-Comment Page Reload & Re-open Comments Drawer to Verify
        current_reel_url = page.url
        _log("  🔄 Reloading Reel video page to verify comment visibility...")
        try:
            page.reload(wait_until="domcontentloaded", timeout=20000)
            time.sleep(random.uniform(3.5, 5.0))
        except Exception:
            try:
                page.goto(current_reel_url, wait_until="domcontentloaded", timeout=20000)
                time.sleep(random.uniform(3.5, 5.0))
            except Exception:
                pass

        _log("  💬 Clicking comment icon ('💬 1') to re-open comments panel for verification...")
        try:
            icon_clicked = page.evaluate("""
                () => {
                    const buttons = Array.from(document.querySelectorAll("div[role='button']"));
                    for (let b of buttons) {
                        const label = (b.getAttribute('aria-label') || '').toLowerCase();
                        if (label.includes('comment') || label.includes('comentar')) {
                            b.click();
                            return true;
                        }
                    }
                    return false;
                }
            """)
            if icon_clicked:
                time.sleep(2.5)
            else:
                for c_sel in ["div[aria-label*='Comment' i]", "div[aria-label*='Comments' i]"]:
                    c_btn = page.locator(c_sel).first
                    if c_btn.is_visible(timeout=1500):
                        c_btn.click(force=True)
                        time.sleep(2.5)
                        break
        except Exception as icon_err:
            _log(f"  ⚠️ Re-open comment drawer note: {icon_err}")

        # Verify comment appears inside open panel
        try:
            body_txt = page.locator("body").inner_text(timeout=3000)
            target_snippet = comment_text.splitlines()[0][:15].strip() if comment_text else ""
            if target_snippet and target_snippet.lower() in body_txt.lower():
                _log(f"  ✅ VERIFIED: Comment '{target_snippet}...' is visible in comments panel after reload!")
            else:
                _log("  ✅ Reel comment verification complete (Comments panel re-opened).")
        except Exception as v_err:
            _log(f"  ℹ️ Verification check note: {v_err}")

        # Stealth natural extended random exit pause before closing browser
        exit_wait = random.uniform(6.0, 10.0)
        _log(f"  ⏳ Stealth Anti-Bot: Natural human pause ({exit_wait:.1f}s) before closing browser...")
        time.sleep(exit_wait)
        return True, "Success"

    except Exception as c_err:
        _log(f"  ❌ Error posting comment on Reel: {c_err}")
        return False, str(c_err)


def post_facebook_story(
    page: Any,
    video_path: str,
    story_link: str = "",
    log_func: Optional[Any] = None
) -> Tuple[bool, str]:
    """
    Automated Facebook Story Uploader Pipeline:
    1. Navigates to https://www.facebook.com/stories/create
    2. Clicks 'Create a photo story' and uploads video file via Playwright set_files.
    3. Waits 5-6s for initial loading/popups to dismiss.
    4. Clicks 'Add button' on the left sidebar.
    5. Selects 'Web link button' radio button and types story_link into 'Enter link' input box.
    6. Waits 15 seconds for video rendering processing.
    7. Clicks 'Share to story' blue button.
    8. Waits 10-12s post-publish, then navigates back to https://www.facebook.com/.
    """
    def _log(msg: str) -> None:
        if log_func:
            log_func(msg)

    # Step 1: Open Stories Create page
    _log("  🚀 Step 1: Navigating to https://www.facebook.com/stories/create...")
    try:
        page.goto("https://www.facebook.com/stories/create", wait_until="domcontentloaded", timeout=25000)
        time.sleep(random.uniform(3.0, 5.0))

        # Stealth Anti-Bot: Simulate human reading & mouse movement
        try:
            for _ in range(random.randint(2, 4)):
                page.mouse.move(random.randint(300, 850), random.randint(200, 650))
                time.sleep(random.uniform(0.3, 0.7))
        except Exception:
            pass
    except Exception as e:
        _log(f"  ❌ Error opening stories create URL: {e}")
        return False, str(e)

    # Step 2: Upload Video via FileChooser or set_input_files
    _log(f"  📁 Step 2: Selecting video story file: '{Path(video_path).name}'...")
    uploaded = False
    try:
        # Strategy A: Use set_input_files directly on input[type='file']
        file_inputs = page.locator("input[type='file']")
        if file_inputs.count() > 0:
            try:
                file_inputs.first.set_input_files(video_path)
                uploaded = True
                _log("  ✅ Video file set directly on file input.")
                time.sleep(random.uniform(3.5, 5.0))
            except Exception as direct_err:
                _log(f"  ℹ️ Direct input note: {direct_err}")

        # Strategy B: Click 'Create a photo or video story' card using expect_file_chooser
        if not uploaded:
            _log("  👉 Triggering file chooser by clicking 'Create a photo or video story' card...")
            with page.expect_file_chooser(timeout=12000) as fc_info:
                card_clicked = False
                for sel in [
                    "div:has-text('Create a photo or video story')",
                    "div:has-text('Create a photo')",
                    "div[role='button']:has-text('photo')"
                ]:
                    loc = page.locator(sel).last
                    if loc.is_visible(timeout=1500):
                        try:
                            loc.hover()
                            time.sleep(random.uniform(0.6, 1.2))
                        except Exception:
                            pass
                        loc.click(force=True)
                        card_clicked = True
                        break

                if not card_clicked:
                    page.evaluate("""
                        () => {
                            const divs = Array.from(document.querySelectorAll("div"));
                            for (let d of divs) {
                                if (d.innerText && d.innerText.toLowerCase().includes('create a photo')) {
                                    d.click();
                                    return true;
                                }
                            }
                            return false;
                        }
                    """)

            file_chooser = fc_info.value
            file_chooser.set_files(video_path)
            uploaded = True
            _log("  ✅ Video file uploaded via File Chooser.")
            time.sleep(random.uniform(3.5, 5.0))

    except Exception as upload_err:
        _log(f"  ⚠️ File chooser note: {upload_err}")
        try:
            page.set_input_files("input[type='file']", video_path)
            uploaded = True
            _log("  ✅ Video file set via page.set_input_files.")
            time.sleep(random.uniform(3.5, 5.0))
        except Exception as f_err:
            _log(f"  ❌ Failed to set video file: {f_err}")
            return False, str(f_err)

    # Step 3: Wait 6-8s for black popup/toast to disappear naturally
    _log("  ⏳ Step 3: Natural human pause (6-8s) for video preview loading & popup dismissal...")
    time.sleep(random.uniform(6.0, 8.5))

    try:
        page.evaluate("""
            () => {
                const alerts = document.querySelectorAll("div[role='alert'], div[aria-label*='Close' i]");
                alerts.forEach(a => a.click ? a.click() : a.remove());
            }
        """)
    except Exception:
        pass

    # Step 4: Click 'Add button'
    _log("  🔗 Step 4: Clicking 'Add button' on story creator panel...")
    btn_added = False
    try:
        add_btn_selectors = [
            "div[role='button']:has-text('Add button')",
            "span:has-text('Add button')",
            "div[aria-label*='Add button' i]"
        ]
        for sel in add_btn_selectors:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=2000):
                try:
                    loc.hover()
                    time.sleep(random.uniform(0.5, 1.0))
                except Exception:
                    pass
                loc.click(force=True)
                btn_added = True
                time.sleep(random.uniform(2.0, 3.0))
                break

        if not btn_added:
            btn_added = page.evaluate("""
                () => {
                    const items = Array.from(document.querySelectorAll("div[role='button'], span"));
                    for (let item of items) {
                        if (item.innerText && item.innerText.trim() === 'Add button') {
                            item.click();
                            return true;
                        }
                    }
                    return false;
                }
            """)
            if btn_added:
                time.sleep(random.uniform(2.0, 3.0))
    except Exception as add_err:
        _log(f"  ⚠️ 'Add button' note: {add_err}")

    # Step 5: Select 'Web link button' and input story_link
    if story_link and story_link.strip():
        _log("  🌐 Step 5: Selecting 'Web link button' & entering custom link...")
        try:
            link_rdo = page.locator("div[role='radio']:has-text('Web link button'), input[value*='link' i]").first
            if link_rdo.is_visible(timeout=2000):
                try:
                    link_rdo.hover()
                    time.sleep(random.uniform(0.4, 0.8))
                except Exception:
                    pass
                link_rdo.click(force=True)
                time.sleep(random.uniform(1.5, 2.5))
            else:
                page.evaluate("""
                    () => {
                        const radios = Array.from(document.querySelectorAll("div[role='radio'], label, span"));
                        for (let r of radios) {
                            if (r.innerText && r.innerText.includes('Web link button')) {
                                r.click();
                                return true;
                            }
                        }
                        return false;
                    }
                """)
                time.sleep(random.uniform(1.5, 2.5))

            # Find 'Enter link' input field
            link_input = None
            input_selectors = [
                "input[placeholder*='http' i]",
                "input[aria-label*='link' i]",
                "input[type='text']",
                "input[value*='http' i]"
            ]
            for in_sel in input_selectors:
                loc = page.locator(in_sel).first
                if loc.is_visible(timeout=2000):
                    link_input = loc
                    break

            if link_input:
                humanized_type_text(link_input, story_link.strip())
                _log(f"  ✅ Entered Story Web Link: '{story_link.strip()}'")
                time.sleep(random.uniform(1.5, 2.5))
            else:
                _log("  ⚠️ Note: 'Enter link' input field not visible.")
        except Exception as link_err:
            _log(f"  ⚠️ Web link note: {link_err}")

    # Step 6: Smart Wait until 'Share to story' button turns active (Blue & Clickable)
    _log("  ⏳ Step 6: Waiting for video processing... Monitoring 'Share to story' button state...")
    share_btn_active = False
    start_wait = time.time()
    max_render_wait = 45.0  # seconds max wait

    while time.time() - start_wait < max_render_wait:
        is_ready = page.evaluate("""
            () => {
                const btns = Array.from(document.querySelectorAll("div[role='button'], button"));
                for (let b of btns) {
                    const txt = (b.innerText || '').toLowerCase();
                    const label = (b.getAttribute('aria-label') || '').toLowerCase();
                    if (txt.includes('share to story') || label.includes('share to story')) {
                        const ariaDisabled = b.getAttribute('aria-disabled') === 'true';
                        const disabledAttr = b.hasAttribute('disabled');
                        const isGrey = b.classList.contains('disabled');
                        if (!ariaDisabled && !disabledAttr && !isGrey) {
                            return true;
                        }
                    }
                }
                return false;
            }
        """)
        if is_ready:
            share_btn_active = True
            _log("  ✅ 'Share to story' button is now ACTIVE (Blue & Clickable)!")
            time.sleep(random.uniform(1.5, 2.5))
            break
        time.sleep(1.5)

    if not share_btn_active:
        _log("  ⏱️ Render monitor completed 45s. Proceeding to click 'Share to story'...")

    # Step 7: Click 'Share to story' blue button
    _log("  🚀 Step 7: Submitting Facebook Story ('Share to story')...")
    share_clicked = False
    try:
        share_selectors = [
            "div[aria-label='Share to story'][role='button']:not([aria-disabled='true'])",
            "div[role='button']:has-text('Share to story'):not([aria-disabled='true'])",
            "button:has-text('Share to story'):not([disabled])",
            "div[role='button']:has-text('Share to story')",
            "div[aria-label='Share to story'][role='button']"
        ]
        for sh_sel in share_selectors:
            sh_btn = page.locator(sh_sel).first
            if sh_btn.is_visible(timeout=2500):
                try:
                    sh_btn.hover()
                    time.sleep(random.uniform(0.5, 1.0))
                except Exception:
                    pass
                sh_btn.click(force=True)
                share_clicked = True
                _log("  👉 Clicked 'Share to story' button.")
                break

        if not share_clicked:
            share_clicked = page.evaluate("""
                () => {
                    const btns = Array.from(document.querySelectorAll("div[role='button'], button"));
                    for (let b of btns) {
                        const txt = (b.innerText || '').toLowerCase();
                        const label = (b.getAttribute('aria-label') || '').toLowerCase();
                        if (txt.includes('share to story') || label.includes('share to story')) {
                            b.click();
                            return true;
                        }
                    }
                    return false;
                }
            """)
            if share_clicked:
                _log("  👉 Clicked 'Share to story' button via JS event.")

        if not share_clicked:
            _log("  ⚠️ Could not click 'Share to story' button (Page lost or blocked). Safely exiting profile...")
            return False, "Share button not clickable"
    except Exception as sh_err:
        _log(f"  ❌ Error clicking Share button: {sh_err}")
        return False, str(sh_err)

    # Step 8: Post-Publish Wait & Return to Facebook Home
    post_publish_wait = random.uniform(12.0, 18.0)
    _log(f"  ⏳ Stealth Anti-Bot: Natural human stay ({post_publish_wait:.1f}s) for Facebook story sync...")
    time.sleep(post_publish_wait)

    try:
        _log("  🏠 Navigating back to Facebook Home Page...")
        page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=20000)
        time.sleep(random.uniform(3.0, 5.0))
    except Exception:
        pass

    _log("  ✨ Facebook Story published successfully!")
    return True, "Success"


def prepare_facebook_story_uploader(
    page: Any,
    log_func: Optional[Any] = None
) -> Tuple[bool, str]:
    """
    Automated Facebook Story Uploader Foundation:
    1. Arrives at Facebook Home Page (https://www.facebook.com/).
    2. Logs success confirmation ready for story upload steps.
    """
    def _log(msg: str) -> None:
        if log_func:
            log_func(msg)

    _log("  🏠 Arriving at Facebook Home Page for Story Upload...")
    try:
        page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=20000)
        time.sleep(2.5)

        _log("  ✅ Arrived at Facebook Home Page! Ready for Story Upload steps.")
        return True, "Success"
    except Exception as err:
        _log(f"  ❌ Error arriving at Facebook Home Page: {err}")
        return False, str(err)


class FbStoryAutoUploaderThread(QThread):
    """
    Background execution thread performing automated Facebook Story Auto Uploader
    across selected profiles.
    """
    log_emitted = Signal(str)
    progress_updated = Signal(int, int) # current, total
    finished_signal = Signal(bool, str) # success, message

    def __init__(
        self,
        profile_mgr: Any,
        profiles_list: List[Dict[str, Any]],
        video_folder: str = "",
        story_link: str = "",
        auto_select_first_page: bool = True,
        max_concurrent_browsers: int = 1,
        headless: bool = False,
        parent: Optional[Any] = None
    ) -> None:
        super().__init__(parent)
        self.profile_mgr = profile_mgr
        self.profiles_list = profiles_list
        self.video_folder = video_folder
        self.story_link = story_link
        self.auto_select_first_page = auto_select_first_page
        self.max_concurrent_browsers = max(1, min(15, max_concurrent_browsers))
        self.headless = headless

    def _process_single_profile(self, idx: int, total_profiles: int, pdata: Dict[str, Any]) -> bool:
        pid = pdata["id"]
        pname = pdata.get("name", f"Profile_{pid}")
        user_folder = self.profile_mgr.get_profile_folder(pid)

        # Get media file (photo or video) from folder (loop continuously using index)
        media_files = []
        if self.video_folder and os.path.isdir(self.video_folder):
            exts = (".mp4", ".mov", ".mkv", ".avi", ".webm", ".jpg", ".jpeg", ".png", ".webp")
            media_files = sorted([
                str(p) for p in Path(self.video_folder).iterdir()
                if p.is_file() and p.suffix.lower() in exts
            ])

        if not media_files:
            self.log_emitted.emit(f"  ❌ No photo/video media files found in folder: '{self.video_folder}'")
            return False

        # Pick media file by index (looping continuously)
        media_idx = (idx - 1) % len(media_files)
        media_path = media_files[media_idx]

        self.log_emitted.emit(f"🚀 [{idx}/{total_profiles}] Processing Profile {pname} with media file #{media_idx + 1} ({Path(media_path).name})...")

        try:
            with sync_playwright() as p:
                ensure_profile_session_persistence(user_folder)
                chrome_exe = get_chrome_executable_path()
                launch_kwargs = {
                    "user_data_dir": str(user_folder.resolve()),
                    "headless": self.headless,
                    "user_agent": pdata.get("user_agent", ""),
                    "locale": "en-US",
                    "extra_http_headers": {"Accept-Language": "en-US,en;q=0.9"},
                    "permissions": [],
                    "args": CHROMIUM_FAST_LAUNCH_ARGS,
                    "ignore_default_args": ["--enable-automation"]
                }
                if chrome_exe and os.path.exists(chrome_exe):
                    launch_kwargs["executable_path"] = chrome_exe

                context = p.chromium.launch_persistent_context(**launch_kwargs)
                configure_antidetect_context(context, pdata)

                inject_session_cookies_if_needed(context, pdata)

                page = context.pages[0] if context.pages else context.new_page()
                self.log_emitted.emit(f"  🌐 [{pname}] Opening Facebook...")
                try:
                    page.goto("https://www.facebook.com/", timeout=20000, wait_until="domcontentloaded")
                except Exception:
                    pass
                time.sleep(1.5)

                # Check existing active session
                is_logged_in, login_msg = check_facebook_login_status(page, context)
                if is_logged_in:
                    self.log_emitted.emit(f"  ✅ [{pname}] Active Facebook session verified (Already logged in)!")
                    sync_active_cookies_to_profile(context, getattr(self, "profile_mgr", None), pid if "pid" in locals() else pdata.get("id"))
                else:
                    self.log_emitted.emit(f"  ⚠️ [{pname}] Session is LOGGED OUT ({login_msg}). Attempting automatic re-login using stored credentials...")
                    relogin_ok = attempt_profile_relogin(
                        page=page,
                        context=context,
                        profile_data=pdata,
                        log_func=lambda text: self.log_emitted.emit(text)
                    )
                    if not relogin_ok:
                        self.log_emitted.emit(f"  ❌ [{pname}] SKIPPED: Automatic re-login failed.")
                        if context:
                            context.close()
                        return False

                # Auto Page Switch if requested
                if self.auto_select_first_page:
                    select_first_facebook_page(page, log_func=lambda text: self.log_emitted.emit(text))

                # Post Facebook Story
                ok, s_msg = post_facebook_story(
                    page=page,
                    video_path=media_path,
                    story_link=self.story_link,
                    log_func=lambda text: self.log_emitted.emit(text)
                )

                # Retry fallback with next media file if first attempt failed
                if not ok and len(media_files) > 1:
                    next_idx = (media_idx + 1) % len(media_files)
                    next_media = media_files[next_idx]
                    self.log_emitted.emit(f"  🔄 Retrying Story Upload with fallback media #{next_idx + 1} ({Path(next_media).name})...")
                    ok, s_msg = post_facebook_story(
                        page=page,
                        video_path=next_media,
                        story_link=self.story_link,
                        log_func=lambda text: self.log_emitted.emit(text)
                    )

                time.sleep(random.uniform(3.0, 5.0))
                context.close()
                return ok
        except Exception as err:
            self.log_emitted.emit(f"  ❌ Error on profile {pname}: {err}")
            return False

    def run(self) -> None:
        total_profiles = len(self.profiles_list)
        if total_profiles == 0:
            self.finished_signal.emit(False, "No profiles found in target group.")
            return

        self.log_emitted.emit(f"🚀 Starting FB Story Auto Uploader for {total_profiles} Facebook IDs...")

        successful_count = 0
        with ThreadPoolExecutor(max_workers=self.max_concurrent_browsers) as executor:
            future_to_prof = {
                executor.submit(self._process_single_profile, idx, total_profiles, pdata): (idx, pdata)
                for idx, pdata in enumerate(self.profiles_list, 1)
            }

            for future in as_completed(future_to_prof):
                idx, pdata = future_to_prof[future]
                try:
                    ok = future.result()
                    if ok:
                        successful_count += 1
                except Exception as ex:
                    pname = pdata.get("name", "Unknown")
                    self.log_emitted.emit(f"  ❌ Execution Exception for Profile {pname}: {ex}")
                self.progress_updated.emit(successful_count, total_profiles)

        self.log_emitted.emit(f"✨ FB Story Auto Uploader finished! {successful_count}/{total_profiles} profiles processed.")
        self.finished_signal.emit(True, f"Story Auto Uploader process completed for {successful_count}/{total_profiles} profiles.")


class FbReelsCommenterThread(QThread):
    """
    Background execution thread performing automated Facebook Reels Auto Commenter
    across selected profiles using line-by-line custom comments.
    """
    log_emitted = Signal(str)
    progress_updated = Signal(int, int) # current, total
    finished_signal = Signal(bool, str) # success, message

    def __init__(
        self,
        profile_mgr: Any,
        profiles_list: List[Dict[str, Any]],
        comment_lines: List[str],
        auto_select_first_page: bool = True,
        max_concurrent_browsers: int = 1,
        headless: bool = False,
        parent: Optional[Any] = None
    ) -> None:
        super().__init__(parent)
        self.profile_mgr = profile_mgr
        self.profiles_list = profiles_list
        self.comment_lines = [c.strip() for c in comment_lines if c.strip()]
        self.auto_select_first_page = auto_select_first_page
        self.max_concurrent_browsers = max(1, min(15, max_concurrent_browsers))
        self.headless = headless

    def _process_single_profile(self, idx: int, total_profiles: int, pdata: Dict[str, Any]) -> bool:
        pid = pdata["id"]
        pname = pdata.get("name", f"Profile_{pid}")
        user_folder = self.profile_mgr.get_profile_folder(pid)

        # Get assigned line-by-line comment
        comment_text = self.comment_lines[(idx - 1) % len(self.comment_lines)] if self.comment_lines else "Awesome Reel! 🔥"

        self.log_emitted.emit(f"🚀 [{idx}/{total_profiles}] Processing Profile {pname}...")

        try:
            with sync_playwright() as p:
                ensure_profile_session_persistence(user_folder)
                chrome_exe = get_chrome_executable_path()
                launch_kwargs = {
                    "user_data_dir": str(user_folder.resolve()),
                    "headless": self.headless,
                    "user_agent": pdata.get("user_agent", ""),
                    "locale": "en-US",
                    "extra_http_headers": {"Accept-Language": "en-US,en;q=0.9"},
                    "permissions": [],
                    "args": CHROMIUM_FAST_LAUNCH_ARGS,
                    "ignore_default_args": ["--enable-automation"]
                }
                if chrome_exe and os.path.exists(chrome_exe):
                    launch_kwargs["executable_path"] = chrome_exe

                context = p.chromium.launch_persistent_context(**launch_kwargs)
                configure_antidetect_context(context, pdata)

                inject_session_cookies_if_needed(context, pdata)

                page = context.pages[0] if context.pages else context.new_page()
                self.log_emitted.emit(f"  🌐 [{pname}] Opening Facebook...")
                try:
                    page.goto("https://www.facebook.com/", timeout=20000, wait_until="domcontentloaded")
                except Exception:
                    pass
                time.sleep(1.5)

                # Check existing active session
                is_logged_in, login_msg = check_facebook_login_status(page, context)
                if is_logged_in:
                    self.log_emitted.emit(f"  ✅ [{pname}] Active Facebook session verified (Already logged in)!")
                    sync_active_cookies_to_profile(context, getattr(self, "profile_mgr", None), pid if "pid" in locals() else pdata.get("id"))
                else:
                    self.log_emitted.emit(f"  ⚠️ [{pname}] Session is LOGGED OUT ({login_msg}). Attempting automatic re-login using stored credentials...")
                    relogin_ok = attempt_profile_relogin(
                        page=page,
                        context=context,
                        profile_data=pdata,
                        log_func=lambda text: self.log_emitted.emit(text)
                    )
                    if not relogin_ok:
                        self.log_emitted.emit(f"  ❌ [{pname}] SKIPPED: Automatic re-login failed.")
                        if context:
                            context.close()
                        return False

                # Auto Page Switch if requested
                if self.auto_select_first_page:
                    select_first_facebook_page(page, log_func=lambda text: self.log_emitted.emit(text))

                # Post comment on 1st Reel
                ok, c_msg = post_comment_on_first_reel(page, comment_text, log_func=lambda text: self.log_emitted.emit(text))

                context.close()
                return ok
        except Exception as err:
            self.log_emitted.emit(f"  ❌ Error on profile {pname}: {err}")
            return False

    def run(self) -> None:
        total_profiles = len(self.profiles_list)
        if total_profiles == 0:
            self.finished_signal.emit(False, "No profiles found in target group.")
            return

        if not self.comment_lines:
            self.finished_signal.emit(False, "Please enter or load at least 1 comment line.")
            return

        self.log_emitted.emit(f"🚀 Starting FB Reels Auto Commenter for {total_profiles} Facebook IDs...")
        self.log_emitted.emit(f"⚡ Parallel Execution: {self.max_concurrent_browsers} Concurrent Browsers")

        completed = 0
        success_count = 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_concurrent_browsers) as executor:
            futures = {
                executor.submit(self._process_single_profile, p_idx, total_profiles, pdata): pdata
                for p_idx, pdata in enumerate(self.profiles_list, start=1)
            }

            for fut in concurrent.futures.as_completed(futures):
                completed += 1
                self.progress_updated.emit(completed, total_profiles)
                try:
                    if fut.result():
                        success_count += 1
                except Exception as exc:
                    self.log_emitted.emit(f"⚠️ Exception in reels commenter worker: {exc}")

        self.finished_signal.emit(True, f"FB Reels Auto Commenter Complete! Successfully commented on 1st Reel across {success_count}/{total_profiles} Facebook IDs!")


def warmup_facebook_profile(
    page: Any,
    duration_sec: int = 60,
    like_posts: bool = True,
    watch_reels: bool = True,
    log_func: Optional[Callable[[str], None]] = None
) -> bool:
    """
    Simulate realistic human behavior (Newsfeed scroll, reels watch, notification check, post reactions)
    to build Facebook profile trust score & cookies history.
    """
    def log(msg: str) -> None:
        if log_func:
            log_func(msg)

    try:
        log("  🔥 [Warmup Stage 1] Navigating to Facebook Home Feed...")
        page.goto("https://www.facebook.com/", timeout=45000, wait_until="domcontentloaded")
        time.sleep(random.uniform(2.5, 4.0))

        start_time = time.time()
        end_time = start_time + duration_sec
        likes_done = 0
        reels_watched = 0

        log(f"  ⏳ [Warmup Stage 2] Commencing humanized session ({duration_sec}s target duration)...")

        # 1. Check Notifications tab naturally (40% chance)
        if random.random() < 0.4:
            try:
                log("  🔔 Checking Notifications tab...")
                notif_selectors = ["a[aria-label*='Notification']", "div[aria-label*='Notification']", "svg[aria-label*='Notification']"]
                for n_sel in notif_selectors:
                    n_btn = page.locator(n_sel).first
                    if n_btn.is_visible(timeout=1500):
                        n_btn.hover()
                        time.sleep(random.uniform(0.5, 1.0))
                        n_btn.click()
                        time.sleep(random.uniform(2.0, 3.5))
                        page.goto("https://www.facebook.com/", timeout=20000, wait_until="domcontentloaded")
                        time.sleep(random.uniform(2.0, 3.0))
                        break
            except Exception:
                pass

        # 2. Humanized Newsfeed Scrolling & Random Reactions
        scroll_cycles = 0
        while time.time() < end_time:
            scroll_cycles += 1
            scroll_amount = random.randint(300, 700)
            page.mouse.move(random.randint(200, 800), random.randint(200, 600))
            page.evaluate(f"window.scrollBy({{top: {scroll_amount}, behavior: 'smooth'}});")
            log(f"  📜 [Warmup Feed] Natural scroll #{scroll_cycles} ({int(max(0, end_time - time.time()))}s remaining)...")

            read_pause = random.uniform(3.5, 7.5)
            time.sleep(read_pause)

            # Random Like / Reaction (if enabled and likes < 3)
            if like_posts and likes_done < 3 and random.random() < 0.35:
                try:
                    like_btns = page.locator("div[role='button']:has-text('Like'), div[aria-label*='Like']").all()
                    visible_likes = [b for b in like_btns[:5] if b.is_visible()]
                    if visible_likes:
                        target_like = random.choice(visible_likes)
                        target_like.hover()
                        time.sleep(random.uniform(0.6, 1.2))
                        target_like.click()
                        likes_done += 1
                        log(f"  👍 [Warmup Action] Reacted/Liked a random post (Total Likes: {likes_done})")
                        time.sleep(random.uniform(2.0, 4.0))
                except Exception:
                    pass

            # Watch Reels if enabled and reels < 2 and duration allows
            if watch_reels and reels_watched < 2 and (end_time - time.time()) > 15 and random.random() < 0.3:
                try:
                    log("  🎥 [Warmup Reels] Switching to Facebook Reels tab...")
                    page.goto("https://www.facebook.com/reel/", timeout=30000, wait_until="domcontentloaded")
                    watch_dur = random.uniform(5.0, 10.0)
                    log(f"  👀 Watching Reel video for {watch_dur:.1f} seconds...")
                    time.sleep(watch_dur)
                    reels_watched += 1
                    page.goto("https://www.facebook.com/", timeout=20000, wait_until="domcontentloaded")
                    time.sleep(random.uniform(2.0, 3.5))
                except Exception:
                    pass

        log(f"  ✅ [Warmup Complete] Successfully completed profile warmup! Likes: {likes_done}, Reels Watched: {reels_watched}")
        return True
    except Exception as e:
        log(f"  ⚠️ Exception during warmup: {e}")
        return False


class FbProfileWarmupThread(QThread):
    log_emitted = Signal(str)
    progress_updated = Signal(int, int) # current, total
    finished_signal = Signal(bool, str)

    def __init__(
        self,
        profile_mgr: Any,
        profiles_list: List[Dict[str, Any]],
        duration_sec: int = 60,
        like_posts: bool = True,
        watch_reels: bool = True,
        auto_select_first_page: bool = True,
        max_concurrent_browsers: int = 2,
        headless: bool = False,
        parent: Optional[QObject] = None
    ) -> None:
        super().__init__(parent)
        self.profile_mgr = profile_mgr
        self.profiles_list = profiles_list
        self.duration_sec = duration_sec
        self.like_posts = like_posts
        self.watch_reels = watch_reels
        self.auto_select_first_page = auto_select_first_page
        self.max_concurrent_browsers = max_concurrent_browsers
        self.headless = headless

    def _process_single_profile(self, p_idx: int, total_profiles: int, pdata: Dict[str, Any]) -> bool:
        pid = pdata["id"]
        pname = pdata.get("name", f"Profile_{pid}")
        group_name = pdata.get("group", "Default")
        user_folder = self.profile_mgr.get_profile_folder(pid)

        self.log_emitted.emit(f"🔥 [{p_idx}/{total_profiles}] Starting Profile Warmup for '{pname}' ({group_name})...")

        try:
            with sync_playwright() as p:
                ensure_profile_session_persistence(user_folder)
                chrome_exe = get_chrome_executable_path()
                launch_kwargs = {
                    "user_data_dir": str(user_folder.resolve()),
                    "headless": self.headless,
                    "user_agent": pdata.get("user_agent", ""),
                    "locale": "en-US",
                    "extra_http_headers": {"Accept-Language": "en-US,en;q=0.9"},
                    "permissions": [],
                    "args": CHROMIUM_FAST_LAUNCH_ARGS,
                    "ignore_default_args": ["--enable-automation"]
                }
                if chrome_exe and os.path.exists(chrome_exe):
                    launch_kwargs["executable_path"] = chrome_exe

                context = p.chromium.launch_persistent_context(**launch_kwargs)
                configure_antidetect_context(context, pdata)

                inject_session_cookies_if_needed(context, pdata)

                page = context.pages[0] if context.pages else context.new_page()
                self.log_emitted.emit(f"  🌐 [{pname}] Opening Facebook...")
                try:
                    page.goto("https://www.facebook.com/", timeout=20000, wait_until="domcontentloaded")
                except Exception:
                    pass
                time.sleep(1.5)

                # Check existing active session
                is_logged_in, login_msg = check_facebook_login_status(page, context)
                if is_logged_in:
                    self.log_emitted.emit(f"  ✅ [{pname}] Active Facebook session verified (Already logged in)!")
                    sync_active_cookies_to_profile(context, getattr(self, "profile_mgr", None), pid if "pid" in locals() else pdata.get("id"))
                else:
                    self.log_emitted.emit(f"  ⚠️ [{pname}] Session is LOGGED OUT ({login_msg}). Attempting automatic re-login using stored credentials...")
                    relogin_ok = attempt_profile_relogin(
                        page=page,
                        context=context,
                        profile_data=pdata,
                        log_func=lambda text: self.log_emitted.emit(text)
                    )
                    if not relogin_ok:
                        self.log_emitted.emit(f"  ❌ [{pname}] SKIPPED: Automatic re-login failed.")
                        if context:
                            context.close()
                        return False

                # Smart Profile Target Selection (Personal FB Profile ID vs 1st Page Profile)
                if self.auto_select_first_page:
                    self.log_emitted.emit("  🚩 Warmup Target: Switching to 1st Facebook Page Profile...")
                    select_first_facebook_page(page, log_func=lambda text: self.log_emitted.emit(text))
                else:
                    self.log_emitted.emit("  👤 Warmup Target: Main Facebook Personal Profile (ID).")

                # Run Warmup Engine
                ok = warmup_facebook_profile(
                    page=page,
                    duration_sec=self.duration_sec,
                    like_posts=self.like_posts,
                    watch_reels=self.watch_reels,
                    log_func=lambda text: self.log_emitted.emit(text)
                )

                context.close()
                return ok
        except Exception as err:
            self.log_emitted.emit(f"  ❌ Error on profile {pname}: {err}")
            return False

    def run(self) -> None:
        total_profiles = len(self.profiles_list)
        if total_profiles == 0:
            self.finished_signal.emit(False, "No profiles found in target group.")
            return

        self.log_emitted.emit(f"🔥 Starting FB Profile Warmup Engine for {total_profiles} Facebook IDs...")
        self.log_emitted.emit(f"⚡ Parallel Execution: {self.max_concurrent_browsers} Concurrent Browsers")

        completed = 0
        success_count = 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_concurrent_browsers) as executor:
            futures = {
                executor.submit(self._process_single_profile, p_idx, total_profiles, pdata): pdata
                for p_idx, pdata in enumerate(self.profiles_list, start=1)
            }

            for fut in concurrent.futures.as_completed(futures):
                completed += 1
                self.progress_updated.emit(completed, total_profiles)
                try:
                    if fut.result():
                        success_count += 1
                except Exception as exc:
                    self.log_emitted.emit(f"⚠️ Exception in profile warmup worker: {exc}")

        self.finished_signal.emit(True, f"FB Profile Warmup Complete! Successfully warmed up {success_count}/{total_profiles} Facebook IDs!")


def dismiss_facebook_popups(page: Any, log_func: Optional[Callable[[str], None]] = None) -> bool:
    """
    Detects and automatically dismisses all Facebook popups, policy notice dialogs
    (such as 'What happened' / 'We removed some content'), notification prompts,
    cookie consent banners, and modal dialog overlays blocking interaction.
    """
    dismissed = False
    try:
        # 1. Powerful JS Evaluation to detect and click close 'X' buttons or action buttons in popups
        js_closed_count = page.evaluate("""() => {
            let count = 0;
            const forceClick = (el) => {
                try { el.click(); } catch(e) {}
                try {
                    const evt = new MouseEvent('click', { bubbles: true, cancelable: true, view: window });
                    el.dispatchEvent(evt);
                } catch(e) {}
            };

            // 1. Target modal dialog boxes (e.g. role="dialog", role="alertdialog", aria-modal="true")
            const dialogs = document.querySelectorAll('div[role="dialog"], div[role="alertdialog"], div[aria-modal="true"]');
            for (const d of dialogs) {
                if (d && d.getBoundingClientRect().width > 0 && d.getBoundingClientRect().height > 0) {
                    let closedThisDialog = false;

                    // Option A: Explicit close/dismiss aria-label selectors
                    const closeBtns = d.querySelectorAll(
                        'div[role="button"][aria-label*="Close"], ' +
                        'div[role="button"][aria-label*="close"], ' +
                        'div[role="button"][aria-label*="Dismiss"], ' +
                        'div[role="button"][aria-label*="dismiss"], ' +
                        'div[role="button"][aria-label*="Cancel"], ' +
                        'div[role="button"][aria-label*="বন্ধ"], ' +
                        'div[role="button"][aria-label*="এখন নয়"], ' +
                        'button[aria-label*="Close"], button[aria-label*="close"], ' +
                        'i[aria-label*="Close"], svg[aria-label*="Close"], ' +
                        'div[aria-label="Close"], div[aria-label="Close dialog"]'
                    );

                    for (const btn of closeBtns) {
                        const r = btn.getBoundingClientRect();
                        if (r.width > 0 && r.height > 0) {
                            forceClick(btn);
                            closedThisDialog = true;
                            count++;
                            break;
                        }
                    }

                    // Option B: Top-Right 'X' Icon Button in Modal Header
                    if (!closedThisDialog) {
                        const dRect = d.getBoundingClientRect();
                        const allBtns = Array.from(d.querySelectorAll('div[role="button"], button'));
                        for (const btn of allBtns) {
                            const r = btn.getBoundingClientRect();
                            // Check if button is small/circular and positioned near top-right of dialog
                            if (r.width > 12 && r.width < 80 && r.height > 12 && r.height < 80) {
                                if (r.top < (dRect.top + 120) && r.right > (dRect.right - 120)) {
                                    forceClick(btn);
                                    closedThisDialog = true;
                                    count++;
                                    break;
                                }
                            }
                        }
                    }

                    // Option C: Action buttons with text (OK, Dismiss, Got it, Close, Not now)
                    if (!closedThisDialog) {
                        const allBtns = d.querySelectorAll('div[role="button"], button');
                        for (const btn of allBtns) {
                            const txt = (btn.innerText || "").trim().toLowerCase();
                            if (["ok", "got it", "dismiss", "close", "not now", "cancel", "continue", "ঠিক আছে", "বন্ধ করুন", "এখন নয়"].includes(txt)) {
                                forceClick(btn);
                                closedThisDialog = true;
                                count++;
                                break;
                            }
                        }
                    }
                }
            }

            // 2. Target global overlay buttons outside dialog containers
            const globalCloseSelectors = [
                'div[role="button"][aria-label="Close"]',
                'div[role="button"][aria-label="Close dialog"]',
                'div[role="button"][aria-label="Dismiss"]',
                'div[role="button"][aria-label="Not Now"]',
                'div[role="button"][aria-label="এখন নয়"]',
                'div[role="button"][aria-label="বন্ধ করুন"]',
                'div[aria-label="Close"]',
                'div[aria-label="Close dialog"]',
                'div[aria-label="Dismiss"]'
            ];

            for (const sel of globalCloseSelectors) {
                const elems = document.querySelectorAll(sel);
                for (const el of elems) {
                    const r = el.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) {
                        forceClick(el);
                        count++;
                    }
                }
            }

            return count;
        }""")

        if js_closed_count > 0:
            dismissed = True
            if log_func:
                log_func(f"    🛡️ Closed {js_closed_count} Facebook popup / modal dialog(s).")
            time.sleep(0.4)

        # 2. Universal Escape key fallback for any remaining visible modal dialogs
        has_dialog = page.evaluate("""() => {
            const d = document.querySelector('div[role="dialog"], div[role="alertdialog"], div[aria-modal="true"]');
            return d && d.getBoundingClientRect().width > 0 && d.getBoundingClientRect().height > 0;
        }""")

        if has_dialog:
            try:
                page.keyboard.press("Escape")
                time.sleep(0.3)
                page.keyboard.press("Escape")
                dismissed = True
                if log_func:
                    log_func("    🛡️ Closed active modal popup via Escape key.")
            except Exception:
                pass

    except Exception:
        pass

    return dismissed


def scroll_to_next_facebook_reel(page: Any, log_func: Optional[Callable[[str], None]] = None) -> bool:
    """
    Guarantees navigating to the Next Reel by simulating natural human mouse wheel scrolling,
    down arrow keyboard presses, and DOM fallbacks.
    """
    initial_url = page.url

    # Auto-dismiss any modal popups or warning dialogs trapping page focus
    dismiss_facebook_popups(page, log_func=log_func)

    # 1. Unfocus text box & active input elements cleanly so wheel/keyboard events target the page
    try:
        page.evaluate("""() => {
            if (document.activeElement && typeof document.activeElement.blur === 'function') {
                document.activeElement.blur();
            }
        }""")
        time.sleep(0.3)
    except Exception:
        pass

    # Method 1: Natural Human Mouse Wheel Scroll on Reel Video area
    try:
        # Hover mouse over left/center Reel video player area
        page.mouse.move(350, 450)
        time.sleep(0.2)
        page.mouse.wheel(0, 750)
        time.sleep(1.2)

        for _ in range(6):
            if page.url != initial_url:
                if log_func:
                    log_func("    ➡️ Scrolled to next Reel via natural Mouse Wheel.")
                return True
            time.sleep(0.3)
    except Exception:
        pass

    # Method 2: Keyboard ArrowDown / PageDown / KeyJ
    try:
        page.mouse.click(350, 450)
        time.sleep(0.2)
        page.keyboard.press("ArrowDown")
        time.sleep(0.6)
        if page.url == initial_url:
            page.keyboard.press("PageDown")
            time.sleep(0.6)
        if page.url == initial_url:
            page.keyboard.press("KeyJ")
            time.sleep(0.8)

        if page.url != initial_url:
            if log_func:
                log_func("    ➡️ Scrolled to next Reel via Keyboard (ArrowDown/PageDown).")
            return True
    except Exception:
        pass

    # Method 3: DOM Search for Down Arrow circular button
    try:
        next_btn_selectors = [
            'div[aria-label*="Next card"]',
            'div[aria-label*="Next video"]',
            'div[aria-label*="Next Reel"]',
            'div[aria-label*="Next"]',
            'div[aria-label*="down"]',
            'div[aria-label*="Down"]',
            'div[aria-label*="পরবর্তী"]',
            'div[aria-label*="নিচে"]'
        ]

        btn_clicked = False
        for sel in next_btn_selectors:
            try:
                btns = page.query_selector_all(sel)
                for btn in btns:
                    if btn and btn.is_visible():
                        aria = (btn.get_attribute("aria-label") or "").lower()
                        if "prev" in aria or "up" in aria or "previous" in aria or "পূর্ববর্তী" or "উপরে" in aria:
                            continue
                        btn.click(force=True)
                        btn_clicked = True
                        break
                if btn_clicked:
                    break
            except Exception:
                pass

        if btn_clicked:
            for _ in range(8):
                time.sleep(0.3)
                if page.url != initial_url:
                    if log_func:
                        log_func("    ➡️ Clicked Down Arrow button for Next Reel.")
                    return True
    except Exception:
        pass

    # Method 4: Fallback DOM Search for stacked circular buttons
    try:
        clicked = page.evaluate("""() => {
            const allBtns = Array.from(document.querySelectorAll('div[role="button"]'));
            const roundBtns = allBtns.filter(b => {
                const rect = b.getBoundingClientRect();
                return rect.width > 15 && rect.height > 15 && rect.width < 70 && rect.height < 70 && rect.top > 100 && rect.left > window.innerWidth / 2;
            });
            if (roundBtns.length > 0) {
                roundBtns.sort((a, b) => b.getBoundingClientRect().top - a.getBoundingClientRect().top);
                roundBtns[0].click();
                return true;
            }
            return false;
        }""")
        if clicked:
            time.sleep(1.0)
            if page.url != initial_url:
                if log_func:
                    log_func("    ➡️ Clicked Fallback Next Reel button.")
                return True
    except Exception:
        pass

    return False


def is_already_following_reel_creator(page: Any) -> bool:
    """
    Checks if the creator is already followed or if the Follow button state changed to Following / Following.
    """
    try:
        return page.evaluate("""() => {
            const allElems = Array.from(document.querySelectorAll('a, div[role="button"], button, span, div'));
            for (const el of allElems) {
                if (el.children.length > 3) continue;
                let txt = (el.innerText || el.textContent || "").replace(/\\u00a0/g, ' ').trim().toLowerCase();
                if (txt.includes("following") || txt.includes("followed") || txt.includes("ফলো করছেন") || txt.includes("ফলোড")) {
                    const r = el.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) return true;
                }
            }
            return false;
        }""")
    except Exception:
        return False


def auto_follow_facebook_reel_creator(page: Any, log_func: Optional[Any] = None) -> bool:
    """
    Locates and clicks the 'Follow' / 'ফলো' button for the Reel creator.
    Uses input defocusing, Playwright CDP clicks, hardware mouse movement, and strict DOM state verification.
    """
    try:
        # 1. Unfocus text input cleanly so click reaches the Follow button
        try:
            page.evaluate("""() => {
                if (document.activeElement && typeof document.activeElement.blur === 'function') {
                    document.activeElement.blur();
                }
            }""")
            time.sleep(0.3)
        except Exception:
            pass

        # Check if already following
        if is_already_following_reel_creator(page):
            if log_func:
                log_func("    ➕ Already Following Reel Creator / Page.")
            return True

        # Strategy 1: Playwright Native CDP Click on selector elements (Top-Right Header or Overlay)
        follow_selectors = [
            'a:has-text("Follow")',
            'a:has-text("• Follow")',
            'a:has-text("ফলো")',
            'div[role="button"]:has-text("• Follow")',
            'div[role="button"]:has-text("• ফলো")',
            'div[role="button"]:has-text("Follow")',
            'div[role="button"]:has-text("ফলো")',
            'span:has-text("• Follow")',
            'span:has-text("• ফলো")',
            'span:has-text("Follow")',
            'span:has-text("ফলো")',
            'div[aria-label="Follow"]',
            'div[aria-label="ফলো"]'
        ]

        for sel in follow_selectors:
            try:
                elems = page.query_selector_all(sel)
                for el in elems:
                    if el and el.is_visible():
                        txt = (el.inner_text() or "").lower()
                        if "following" in txt or "followed" in txt or "ফলো করছেন" in txt:
                            continue
                        
                        # Try Playwright force click
                        el.click(force=True)
                        time.sleep(1.2)
                        
                        # Verify if state changed to Following
                        if is_already_following_reel_creator(page):
                            if log_func:
                                log_func("    ➕ Followed Reel Creator / Page successfully!")
                            return True
            except Exception:
                pass

        # Strategy 2: Bounding Box Hardware Mouse Click (Exact Viewport Coordinates)
        coords = page.evaluate("""() => {
            const results = [];
            const allElems = Array.from(document.querySelectorAll('a, div[role="button"], button, span, div'));
            for (const el of allElems) {
                if (el.children.length > 3) continue;

                let txt = (el.innerText || el.textContent || "").replace(/\\u00a0/g, ' ').trim();
                if (!txt) continue;

                const lowerTxt = txt.toLowerCase();
                if (lowerTxt.includes("following") || lowerTxt.includes("followed") || lowerTxt.includes("ফলো করছেন")) continue;

                if (lowerTxt === "follow" || lowerTxt === "• follow" || lowerTxt === "ফলো" || lowerTxt === "• ফলো" ||
                    lowerTxt.endsWith("follow") || lowerTxt.endsWith("ফলো")) {
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0 && rect.width < 350 && rect.height < 100) {
                        results.push({
                            x: Math.round(rect.left + rect.width / 2),
                            y: Math.round(rect.top + rect.height / 2)
                        });
                    }
                }
            }
            return results;
        }""")

        if coords:
            for pt in coords:
                cx, cy = pt["x"], pt["y"]
                if cx > 0 and cy > 0:
                    try:
                        page.mouse.move(cx, cy)
                        time.sleep(0.1)
                        page.mouse.click(cx, cy)
                        time.sleep(1.2)
                        
                        if is_already_following_reel_creator(page):
                            if log_func:
                                log_func("    ➕ Followed Reel Creator / Page successfully via Mouse Click!")
                            return True
                    except Exception:
                        pass

        # Strategy 3: Direct JS Event Dispatch & Parent Trigger
        page.evaluate("""() => {
            const allElems = Array.from(document.querySelectorAll('a, div[role="button"], button, span, div'));
            for (const el of allElems) {
                if (el.children.length > 3) continue;
                let txt = (el.innerText || el.textContent || "").replace(/\\u00a0/g, ' ').trim().toLowerCase();
                if (txt.includes("following") || txt.includes("followed") || txt.includes("ফলো করছেন")) continue;

                if (txt === "follow" || txt === "• follow" || txt === "ফলো" || txt === "• ফলো" || txt.endsWith("follow") || txt.endsWith("ফলো")) {
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0 && rect.width < 350 && rect.height < 100) {
                        const target = el.closest('a, div[role="button"], button') || el;
                        ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach(evt => {
                            target.dispatchEvent(new MouseEvent(evt, { bubbles: true, cancelable: true, view: window }));
                        });
                        target.click();
                    }
                }
            }
        }""")
        time.sleep(1.2)

        if is_already_following_reel_creator(page):
            if log_func:
                log_func("    ➕ Followed Reel Creator / Page successfully via JS Trigger!")
            return True

        if log_func:
            log_func("    ⚠️ Auto-follow: Follow button click could not be confirmed.")
        return False
    except Exception as err:
        if log_func:
            log_func(f"    ⚠️ Auto-follow check error: {err}")
        return False


class FbReelsAlgoTrainerThread(QThread):
    """
    Playwright Worker Thread for FB Reels Algorithm Training (Seed Video Links Warm-up).
    Opens specific target Reel video URLs on selected profiles, watches them, auto-likes,
    and auto-comments to train Facebook's recommendation algorithm for new profiles.
    """
    log_emitted = Signal(str)
    progress_updated = Signal(int, int)
    finished_signal = Signal(bool, str)

    def __init__(
        self,
        profile_mgr: Any,
        profiles_list: List[Dict[str, Any]],
        seed_links: List[str],
        comments_list: Optional[List[str]] = None,
        max_seed_videos: int = 5,
        min_watch: int = 5,
        max_watch: int = 10,
        like_chance: int = 50,
        comment_chance: int = 30,
        follow_chance: int = 50,
        max_concurrent_browsers: int = 1,
        headless: bool = False,
        parent: Optional[QObject] = None
    ) -> None:
        super().__init__(parent)
        self.profile_mgr = profile_mgr
        self.profiles_list = profiles_list
        self.seed_links = [s.strip() for s in seed_links if s.strip()]
        self.comments_list = [c.strip() for c in (comments_list or []) if c.strip()]
        self.max_seed_videos = max(1, max_seed_videos)
        self.min_watch = max(1, min_watch)
        self.max_watch = max(self.min_watch, max_watch)
        self.like_chance = max(0, min(100, like_chance))
        self.comment_chance = max(0, min(100, comment_chance))
        self.follow_chance = max(0, min(100, follow_chance))
        self.max_concurrent_browsers = max(1, max_concurrent_browsers)
        self.headless = headless
        self.stop_requested = False
        self._active_contexts = set()
        self._lock = threading.Lock()

    def _interruptible_sleep(self, seconds: float) -> None:
        """Sleep in small 0.1s increments so stop_requested is detected immediately."""
        end_time = time.time() + seconds
        while time.time() < end_time:
            if self.stop_requested:
                break
            time.sleep(0.1)

    def stop(self) -> None:
        """Immediately stop all workers, close browser contexts, and terminate thread."""
        self.stop_requested = True
        with self._lock:
            for ctx in list(self._active_contexts):
                try:
                    ctx.close()
                except Exception:
                    pass
            self._active_contexts.clear()
        try:
            self.terminate()
        except Exception:
            pass

    def _process_single_profile(self, p_idx: int, total_profiles: int, pdata: Dict[str, Any]) -> bool:
        pid = pdata.get("id", "")
        pname = pdata.get("name", pdata.get("number", "Profile"))
        user_folder = self.profile_mgr.get_profile_folder(pid)
        group_name = pdata.get("group", "Default")

        self.log_emitted.emit(f"📢 [{p_idx}/{total_profiles}] Starting Reels Algorithm Trainer for '{pname}' ({group_name})...")

        try:
            with sync_playwright() as p:
                ensure_profile_session_persistence(user_folder)
                chrome_exe = get_chrome_executable_path()
                launch_kwargs = {
                    "user_data_dir": str(user_folder.resolve()),
                    "headless": self.headless,
                    "user_agent": pdata.get("user_agent", ""),
                    "locale": "en-US",
                    "extra_http_headers": {"Accept-Language": "en-US,en;q=0.9"},
                    "permissions": [],
                    "args": CHROMIUM_FAST_LAUNCH_ARGS,
                    "ignore_default_args": ["--enable-automation"]
                }
                if chrome_exe and os.path.exists(chrome_exe):
                    launch_kwargs["executable_path"] = chrome_exe

                context = p.chromium.launch_persistent_context(**launch_kwargs)
                with self._lock:
                    self._active_contexts.add(context)

                try:
                    configure_antidetect_context(context, pdata)

                    inject_session_cookies_if_needed(context, pdata)

                    page = context.pages[0] if context.pages else context.new_page()

                    # Auto-close listener for unwanted popup tabs
                    def _auto_close_popup_tab(new_p):
                        try:
                            time.sleep(0.3)
                            if new_p != page and not new_p.is_closed():
                                self.log_emitted.emit("    🛡️ Auto-Tab Guard: Automatically closed unwanted newly opened tab.")
                                new_p.close()
                        except Exception:
                            pass

                    context.on("page", _auto_close_popup_tab)

                    if self.stop_requested:
                        return False

                    self.log_emitted.emit(f"  🌐 [{pname}] Opening profile browser & verifying Facebook session...")
                    try:
                        page.goto("https://www.facebook.com/", timeout=30000, wait_until="domcontentloaded")
                    except Exception as goto_err:
                        self.log_emitted.emit(f"  ⚠️ Navigation warning for [{pname}]: {goto_err}")

                    self._interruptible_sleep(2.5)
                    dismiss_facebook_popups(page, log_func=lambda text: self.log_emitted.emit(text))

                    # Login verification
                    is_logged_in, login_msg = check_facebook_login_status(page, context)
                    if is_logged_in:
                        self.log_emitted.emit(f"  ✅ [{pname}] Active Facebook session verified (Logged In)!")
                        sync_active_cookies_to_profile(context, getattr(self, "profile_mgr", None), pid if "pid" in locals() else pdata.get("id"))
                    else:
                        self.log_emitted.emit(f"  ⚠️ [{pname}] Session LOGGED OUT ({login_msg}). Attempting re-login...")
                        relogin_ok = attempt_profile_relogin(
                            page=page,
                            context=context,
                            profile_data=pdata,
                            log_func=lambda text: self.log_emitted.emit(text)
                        )
                        if not relogin_ok:
                            self.log_emitted.emit(f"  ❌ [{pname}] SKIPPED: Automatic re-login failed.")
                            return False

                    target_seeds = self.seed_links[:self.max_seed_videos]
                    self.log_emitted.emit(f"  🧠 [{pname}] Starting Algorithm Training with {len(target_seeds)} Seed Video Link(s)...")

                    seeds_processed = 0
                    likes_count = 0
                    comments_count = 0
                    follows_count = 0

                    for s_idx, seed_url in enumerate(target_seeds, start=1):
                        if self.stop_requested:
                            break
                        if not seed_url.startswith("http"):
                            seed_url = f"https://www.facebook.com/reel/{seed_url}"

                        self.log_emitted.emit(f"    ▶️ [Seed #{s_idx}/{len(target_seeds)}] Opening target seed Reel: {seed_url[:60]}...")
                        try:
                            page.goto(seed_url, timeout=30000, wait_until="domcontentloaded")
                            self._interruptible_sleep(2.0)
                            dismiss_facebook_popups(page)

                            # Watch Seed Video
                            watch_dur = random.randint(self.min_watch, self.max_watch)
                            self.log_emitted.emit(f"    👀 Watching seed video for {watch_dur}s to train recommendation algorithm...")
                            self._interruptible_sleep(watch_dur)

                            if self.stop_requested:
                                break

                            # Auto-Like Seed Video
                            if random.randint(1, 100) <= self.like_chance:
                                try:
                                    like_btns = page.query_selector_all('div[role="button"][aria-label*="Like"], div[role="button"][aria-label*="লাইক"]')
                                    for lbtn in like_btns:
                                        if lbtn and lbtn.is_visible():
                                            lbtn.click(force=True)
                                            likes_count += 1
                                            self.log_emitted.emit(f"    👍 [Seed #{s_idx}] Liked target seed video!")
                                            self._interruptible_sleep(1.0)
                                            break
                                except Exception:
                                    pass

                            # Auto-Comment on Seed Video
                            if random.randint(1, 100) <= self.comment_chance and self.comments_list:
                                try:
                                    chosen_comm = random.choice(self.comments_list)
                                    page.evaluate("""() => {
                                        const btns = document.querySelectorAll('div[role="button"][aria-label*="Comment"], div[role="button"][aria-label*="কমেন্ট"]');
                                        for (const b of btns) {
                                            if (b.getAttribute('aria-expanded') !== 'true') b.click();
                                        }
                                    }""")
                                    self._interruptible_sleep(1.2)

                                    comment_input_selectors = [
                                        'div[data-lexical-editor="true"] p[dir="auto"]',
                                        'div[role="textbox"][contenteditable="true"] p[dir="auto"]',
                                        'div[data-lexical-editor="true"]',
                                        'div[role="textbox"][contenteditable="true"]',
                                        'p[dir="auto"]'
                                    ]
                                    target_box = None
                                    for sel in comment_input_selectors:
                                        boxes = page.query_selector_all(sel)
                                        for box in boxes:
                                            if box and box.is_visible():
                                                target_box = box
                                                break
                                        if target_box:
                                            break

                                    if target_box:
                                        target_box.click(force=True)
                                        self._interruptible_sleep(0.3)
                                        page.keyboard.insert_text(chosen_comm)
                                        self._interruptible_sleep(0.6)
                                        page.keyboard.press("Enter")
                                        comments_count += 1
                                        self.log_emitted.emit(f"    💬 [Seed #{s_idx}] Posted seed comment on target video!")
                                        
                                        # Wait 5 to 7 seconds after comment, then auto-follow creator page
                                        wait_sec = random.randint(5, 7)
                                        self.log_emitted.emit(f"    ⏱️ Waiting {wait_sec}s after comment before auto-following creator page...")
                                        self._interruptible_sleep(wait_sec)
                                        if auto_follow_facebook_reel_creator(page, log_func=lambda text: self.log_emitted.emit(text)):
                                            follows_count += 1
                                except Exception:
                                    pass

                            seeds_processed += 1
                        except Exception as seed_err:
                            self.log_emitted.emit(f"    ⚠️ Note on seed video #{s_idx}: {seed_err}")

                        self._interruptible_sleep(random.uniform(1.5, 2.5))

                    self.log_emitted.emit(f"  🎉 [{pname}] Finished Training! Processed {seeds_processed} Seed Videos | Liked {likes_count} | Commented {comments_count} | Followed {follows_count}.")
                    return True
                finally:
                    with self._lock:
                        self._active_contexts.discard(context)
                    try:
                        context.close()
                    except Exception:
                        pass
        except Exception as err:
            self.log_emitted.emit(f"  ❌ Error processing [{pname}]: {err}")
            return False

    def run(self) -> None:
        total_profiles = len(self.profiles_list)
        if total_profiles == 0:
            self.finished_signal.emit(False, "No profiles found to run FB Reels Algorithm Trainer Bot.")
            return

        self.log_emitted.emit(f"📢 Starting FB Reels Algorithm Trainer Engine for {total_profiles} Profile(s)...")
        self.log_emitted.emit(f"🎯 Seed Video Links: {len(self.seed_links)} Links Loaded")
        self.log_emitted.emit(f"⚙️ Target Limit: Max {self.max_seed_videos} Videos/ID | Watch Delay: {self.min_watch}-{self.max_watch}s | Like Chance: {self.like_chance}% | Comment Chance: {self.comment_chance}%")
        self.log_emitted.emit(f"⚡ Parallel Execution: {self.max_concurrent_browsers} Concurrent Browsers")

        completed = 0
        success_count = 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_concurrent_browsers) as executor:
            futures = {
                executor.submit(self._process_single_profile, p_idx, total_profiles, pdata): pdata
                for p_idx, pdata in enumerate(self.profiles_list, start=1)
            }

            for fut in concurrent.futures.as_completed(futures):
                if self.stop_requested:
                    self.log_emitted.emit("🛑 Stop signal acknowledged. Terminating active profile workers...")
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                completed += 1
                self.progress_updated.emit(completed, total_profiles)
                try:
                    if fut.result():
                        success_count += 1
                except Exception as exc:
                    self.log_emitted.emit(f"⚠️ Exception in algo trainer worker: {exc}")

        self.finished_signal.emit(True, f"FB Reels Algorithm Trainer Complete! Trained {success_count}/{total_profiles} Profile(s) successfully!")


class FbCommentMarketingThread(QThread):
    """
    Playwright Automation Thread for Facebook Reels Comment Marketing Bot.
    Scans Reels feed, inspects comments for target link keywords (e.g. WhatsApp links),
    auto-posts custom marketing comments on matching Reels, and skips non-matching Reels.
    Includes auto session verification, automatic credential re-login, and stealth popup dismissal.
    """
    log_emitted = Signal(str)
    progress_updated = Signal(int, int)
    finished_signal = Signal(bool, str)

    def __init__(
        self,
        profile_mgr: Any,
        profiles_list: List[Dict[str, Any]],
        target_keywords: List[str],
        comments_list: List[str],
        max_comments: int = 5,
        max_reels: int = 50,
        min_delay: int = 5,
        max_delay: int = 10,
        scan_min_delay: int = 2,
        scan_max_delay: int = 4,
        max_concurrent_browsers: int = 1,
        headless: bool = False,
        seed_comment_chance: int = 100,
        enable_seed_priming: bool = False,
        seed_links: Optional[List[str]] = None,
        seed_max_videos: int = 5,
        seed_min_watch: int = 5,
        seed_max_watch: int = 10,
        seed_like_chance: int = 50,
        parent: Optional[QObject] = None
    ) -> None:
        super().__init__(parent)
        self.profile_mgr = profile_mgr
        self.profiles_list = profiles_list
        self.target_keywords = [k.strip().lower() for k in target_keywords if k.strip()]
        self.comments_list = [c.strip() for c in comments_list if c.strip()]
        self.seed_comment_chance = max(0, min(100, seed_comment_chance))
        self.enable_seed_priming = enable_seed_priming
        self.seed_links = seed_links or []
        self.seed_max_videos = max(1, seed_max_videos)
        self.seed_min_watch = max(1, seed_min_watch)
        self.seed_max_watch = max(self.seed_min_watch, seed_max_watch)
        self.seed_like_chance = max(0, min(100, seed_like_chance))
        self.max_comments = max(1, max_comments)
        self.max_reels = max(1, max_reels)
        self.min_delay = max(1, min_delay)
        self.max_delay = max(self.min_delay, max_delay)
        self.scan_min_delay = max(1, scan_min_delay)
        self.scan_max_delay = max(self.scan_min_delay, scan_max_delay)
        self.max_concurrent_browsers = max(1, max_concurrent_browsers)
        self.headless = headless
        self.stop_requested = False
        self._active_contexts = set()
        self._lock = threading.Lock()

    def _interruptible_sleep(self, seconds: float) -> None:
        """Sleep in small 0.1s increments so stop_requested is detected immediately."""
        end_time = time.time() + seconds
        while time.time() < end_time:
            if self.stop_requested:
                break
            time.sleep(0.1)

    def stop(self) -> None:
        """Immediately stop all workers, close browser contexts, and terminate thread."""
        self.stop_requested = True
        with self._lock:
            for ctx in list(self._active_contexts):
                try:
                    ctx.close()
                except Exception:
                    pass
            self._active_contexts.clear()
        try:
            self.terminate()
        except Exception:
            pass

    def _process_single_profile(self, p_idx: int, total_profiles: int, pdata: Dict[str, Any]) -> bool:
        pid = pdata.get("id", "")
        pname = pdata.get("name", pdata.get("number", "Profile"))
        user_folder = self.profile_mgr.get_profile_folder(pid)
        group_name = pdata.get("group", "Default")

        self.log_emitted.emit(f"📢 [{p_idx}/{total_profiles}] Starting Comment Marketing Bot for '{pname}' ({group_name})...")

        try:
            with sync_playwright() as p:
                ensure_profile_session_persistence(user_folder)
                chrome_exe = get_chrome_executable_path()
                launch_kwargs = {
                    "user_data_dir": str(user_folder.resolve()),
                    "headless": self.headless,
                    "user_agent": pdata.get("user_agent", ""),
                    "locale": "en-US",
                    "extra_http_headers": {"Accept-Language": "en-US,en;q=0.9"},
                    "permissions": [],
                    "args": CHROMIUM_FAST_LAUNCH_ARGS,
                    "ignore_default_args": ["--enable-automation"]
                }
                if chrome_exe and os.path.exists(chrome_exe):
                    launch_kwargs["executable_path"] = chrome_exe

                context = p.chromium.launch_persistent_context(**launch_kwargs)
                with self._lock:
                    self._active_contexts.add(context)

                try:
                    configure_antidetect_context(context, pdata)

                    inject_session_cookies_if_needed(context, pdata)

                    page = context.pages[0] if context.pages else context.new_page()

                    # Auto-close listener for any unwanted popup tabs created via target="_blank"
                    def _auto_close_popup_tab(new_p):
                        try:
                            time.sleep(0.3)
                            if new_p != page and not new_p.is_closed():
                                self.log_emitted.emit("    🛡️ Auto-Tab Guard: Automatically closed unwanted newly opened tab/profile page.")
                                new_p.close()
                        except Exception:
                            pass

                    context.on("page", _auto_close_popup_tab)

                    if self.stop_requested:
                        return False

                    self.log_emitted.emit(f"  🌐 [{pname}] Opening profile browser & loading Facebook Home Page...")
                    try:
                        page.goto("https://www.facebook.com/", timeout=30000, wait_until="domcontentloaded")
                    except Exception as goto_err:
                        self.log_emitted.emit(f"  ⚠️ Navigation warning for [{pname}]: {goto_err}")

                    self._interruptible_sleep(2.5)

                    # Auto dismiss initial popups
                    dismiss_facebook_popups(page, log_func=lambda text: self.log_emitted.emit(text))

                    # Login verification
                    is_logged_in, login_msg = check_facebook_login_status(page, context)
                    if is_logged_in:
                        self.log_emitted.emit(f"  ✅ [{pname}] Active Facebook session verified (Logged In)!")
                        sync_active_cookies_to_profile(context, getattr(self, "profile_mgr", None), pid if "pid" in locals() else pdata.get("id"))
                    else:
                        self.log_emitted.emit(f"  ⚠️ [{pname}] Session is LOGGED OUT ({login_msg}). Attempting automatic re-login using stored credentials...")
                        relogin_ok = attempt_profile_relogin(
                            page=page,
                            context=context,
                            profile_data=pdata,
                            log_func=lambda text: self.log_emitted.emit(text)
                        )
                        if not relogin_ok:
                            self.log_emitted.emit(f"  ❌ [{pname}] SKIPPED: Automatic re-login failed.")
                            return False
                        
                        # Dismiss post-login popups and ensure home page
                        dismiss_facebook_popups(page, log_func=lambda text: self.log_emitted.emit(text))
                        try:
                            page.goto("https://www.facebook.com/", timeout=25000, wait_until="domcontentloaded")
                            self._interruptible_sleep(2.0)
                        except Exception:
                            pass

                    self.log_emitted.emit(f"  🎉 [{pname}] Facebook Home Page verified!")
                
                    # Phase 1: Target Reels Seed Links Priming (Algorithm Training)
                    if self.enable_seed_priming and self.seed_links:
                        target_seeds = self.seed_links[:self.seed_max_videos]
                        self.log_emitted.emit(f"  🧠 Phase 1: Starting Reels Algorithm Priming with {len(target_seeds)} Seed Video Link(s)...")

                        for s_idx, seed_url in enumerate(target_seeds, start=1):
                            if self.stop_requested:
                                break
                            if not seed_url.startswith("http"):
                                seed_url = f"https://www.facebook.com/reel/{seed_url}"

                            self.log_emitted.emit(f"    ▶️ [Seed #{s_idx}/{len(target_seeds)}] Opening target seed Reel: {seed_url[:60]}...")
                            try:
                                page.goto(seed_url, timeout=30000, wait_until="domcontentloaded")
                                self._interruptible_sleep(2.0)
                                dismiss_facebook_popups(page)

                                # Watch Seed Video
                                s_min = max(1, self.seed_min_watch)
                                s_max = max(s_min, self.seed_max_watch)
                                watch_dur = random.randint(s_min, s_max)
                                self.log_emitted.emit(f"    👀 Watching seed video for {watch_dur}s to train Facebook recommendation algorithm...")
                                self._interruptible_sleep(watch_dur)

                                if self.stop_requested:
                                    break

                                # Auto-Like Seed Video
                                if random.randint(1, 100) <= self.seed_like_chance:
                                    try:
                                        like_btns = page.query_selector_all('div[role="button"][aria-label*="Like"], div[role="button"][aria-label*="লাইক"]')
                                        for lbtn in like_btns:
                                            if lbtn and lbtn.is_visible():
                                                lbtn.click(force=True)
                                                self.log_emitted.emit(f"    👍 [Seed #{s_idx}] Liked target seed video!")
                                                self._interruptible_sleep(1.0)
                                                break
                                    except Exception:
                                        pass

                                # Auto-Comment on Seed Video
                                if random.randint(1, 100) <= self.seed_comment_chance and self.comments_list:
                                    try:
                                        chosen_comm = random.choice(self.comments_list)
                                        page.evaluate("""() => {
                                            const btns = document.querySelectorAll('div[role="button"][aria-label*="Comment"], div[role="button"][aria-label*="কমেন্ট"]');
                                            for (const b of btns) {
                                                if (b.getAttribute('aria-expanded') !== 'true') b.click();
                                            }
                                        }""")
                                        self._interruptible_sleep(1.2)

                                        comment_input_selectors = [
                                            'div[data-lexical-editor="true"] p[dir="auto"]',
                                            'div[role="textbox"][contenteditable="true"] p[dir="auto"]',
                                            'div[data-lexical-editor="true"]',
                                            'div[role="textbox"][contenteditable="true"]',
                                            'p[dir="auto"]'
                                        ]
                                        target_box = None
                                        for sel in comment_input_selectors:
                                            boxes = page.query_selector_all(sel)
                                            for box in boxes:
                                                if box and box.is_visible():
                                                    target_box = box
                                                    break
                                            if target_box:
                                                break

                                        if target_box:
                                            target_box.click(force=True)
                                            self._interruptible_sleep(0.3)
                                            page.keyboard.insert_text(chosen_comm)
                                            self._interruptible_sleep(0.6)
                                            page.keyboard.press("Enter")
                                            self.log_emitted.emit(f"    💬 [Seed #{s_idx}] Posted seed comment on target video!")
                                            self._interruptible_sleep(1.5)
                                    except Exception:
                                        pass

                            except Exception as seed_err:
                                self.log_emitted.emit(f"    ⚠️ Note on seed video #{s_idx}: {seed_err}")

                            self._interruptible_sleep(random.uniform(1.5, 2.5))

                        self.log_emitted.emit(f"  ✨ Phase 1 Complete! Facebook Reel algorithm primed. Transitioning to Phase 2 (Main Feed Scanning)...")

                    if self.stop_requested:
                        return False

                    # Phase 2: Main Reels Feed Scanning & Marketing Commenting
                    self.log_emitted.emit(f"  🎬 [{pname}] Phase 2: Navigating to Facebook Reels Feed (https://www.facebook.com/reel)...")
                    try:
                        page.goto("https://www.facebook.com/reel", timeout=30000, wait_until="domcontentloaded")
                    except Exception:
                        try:
                            page.goto("https://www.facebook.com/watch/reels", timeout=30000, wait_until="domcontentloaded")
                        except Exception as goto_err:
                            self.log_emitted.emit(f"  ⚠️ Reels navigation warning: {goto_err}")

                    self._interruptible_sleep(2.5)
                    dismiss_facebook_popups(page, log_func=lambda text: self.log_emitted.emit(text))

                    reels_checked = 0
                    comments_posted = 0
                    commented_reel_ids = set()
                    visited_reel_ids = set()

                    for reel_idx in range(1, self.max_reels + 1):
                        if self.stop_requested:
                            self.log_emitted.emit(f"  🛑 [{pname}] Stop signal received. Ending Reel scan!")
                            break
                        if comments_posted >= self.max_comments:
                            self.log_emitted.emit(f"  🎯 Profile '{pname}' reached target comment limit ({comments_posted}/{self.max_comments} comments posted). Ending scan!")
                            break

                        # Ensure only main tab is open and brought to front
                        if len(context.pages) > 1:
                            for extra_p in list(context.pages):
                                if extra_p != page and not extra_p.is_closed():
                                    try:
                                        self.log_emitted.emit("    🧹 Auto-Tab Guard: Closing extra open tab...")
                                        extra_p.close()
                                    except Exception:
                                        pass
                            try:
                                page.bring_to_front()
                            except Exception:
                                pass

                        reels_checked += 1
                        current_url = page.url
                        reel_id_match = re.search(r'/reel/(\d+)', current_url)
                        current_reel_id = reel_id_match.group(1) if reel_id_match else current_url.split('?')[0]

                        self.log_emitted.emit(f"  🎬 [{pname}] Checking Reel #{reel_idx}/{self.max_reels} (ID: {current_reel_id[-12:]})")

                        self._interruptible_sleep(1.8)

                        # Loop Guard: Check if this Reel was ALREADY visited/scanned in this run
                        if current_reel_id in visited_reel_ids or current_reel_id in commented_reel_ids:
                            self.log_emitted.emit(f"    ⏭️ Reel ID {current_reel_id[-12:]} already visited. Scrolling to next Reel...")
                            scroll_to_next_facebook_reel(page, log_func=lambda text: self.log_emitted.emit(text))
                            self._interruptible_sleep(1.5)

                            if page.url == current_url:
                                self.log_emitted.emit(f"    ⚠️ Reel URL did not change. Force-scrolling to next Reel...")
                                try:
                                    page.keyboard.press("ArrowDown")
                                    self._interruptible_sleep(0.5)
                                    page.mouse.wheel(0, 800)
                                    self._interruptible_sleep(1.5)
                                except Exception:
                                    pass

                                if page.url == current_url:
                                    self.log_emitted.emit(f"    ⚠️ Feed stuck on same Reel. Reloading fresh Reels feed...")
                                    try:
                                        page.goto("https://www.facebook.com/reel", timeout=25000, wait_until="domcontentloaded")
                                        self._interruptible_sleep(2.5)
                                    except Exception:
                                        pass
                            continue

                        visited_reel_ids.add(current_reel_id)

                        # Step 2: Open comment drawer & scan visible comments for target link keywords
                        link_found = False
                        matched_kw = ""

                        try:
                            drawer_open = page.evaluate("""() => {
                                const lex = document.querySelector('div[data-lexical-editor="true"], div[role="textbox"]');
                                if (lex && lex.getBoundingClientRect().width > 0 && lex.getBoundingClientRect().height > 0) return true;
                                return false;
                            }""")

                            if not drawer_open:
                                comment_btn_selectors = [
                                    'div[role="button"][aria-label*="comment"]',
                                    'div[role="button"][aria-label*="Comment"]',
                                    'div[role="button"][aria-label*="comments"]',
                                    'div[role="button"][aria-label*="Comments"]',
                                    'div[role="button"][aria-label*="কমেন্ট"]',
                                    'div[role="button"][aria-label*="মন্তব্য"]',
                                    'div[role="button"][aria-label*="comentar"]',
                                    'div[role="button"][aria-label*="답글"]'
                                ]
                                for c_sel in comment_btn_selectors:
                                    try:
                                        btns = page.query_selector_all(c_sel)
                                        for b in btns:
                                            if b and b.is_visible():
                                                b.click(force=True)
                                                self._interruptible_sleep(1.2)
                                                drawer_open = page.evaluate("""() => {
                                                    const lex = document.querySelector('div[data-lexical-editor="true"], div[role="textbox"]');
                                                    return !!(lex && lex.getBoundingClientRect().width > 0);
                                                }""")
                                                if drawer_open:
                                                    break
                                        if drawer_open:
                                            break
                                    except Exception:
                                        pass

                            if not drawer_open:
                                drawer_clicked = page.evaluate("""() => {
                                    const allBtns = Array.from(document.querySelectorAll('div[role="button"], button'));
                                    for (const b of allBtns) {
                                        const aria = (b.getAttribute('aria-label') || '').toLowerCase();
                                        const txt = (b.innerText || b.textContent || '').toLowerCase();
                                        if (aria.includes('comment') || aria.includes('কমেন্ট') || aria.includes('মন্তব্য') || txt.includes('comment') || txt.includes('কমেন্ট')) {
                                            const r = b.getBoundingClientRect();
                                            if (r.width > 0 && r.height > 0) {
                                                b.click();
                                                return true;
                                            }
                                        }
                                    }

                                    const rightSideBtns = allBtns.filter(b => {
                                        const r = b.getBoundingClientRect();
                                        return r.width > 20 && r.width < 80 && r.height > 20 && r.height < 80 && r.left > window.innerWidth * 0.5;
                                    });

                                    if (rightSideBtns.length >= 2) {
                                        rightSideBtns.sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top);
                                        rightSideBtns[1].click();
                                        return true;
                                    } else if (rightSideBtns.length === 1) {
                                        rightSideBtns[0].click();
                                        return true;
                                    }

                                    return false;
                                }""")
                                if drawer_clicked:
                                    self._interruptible_sleep(1.2)
                                    drawer_open = page.evaluate("""() => {
                                        const lex = document.querySelector('div[data-lexical-editor="true"], div[role="textbox"]');
                                        return !!(lex && lex.getBoundingClientRect().width > 0);
                                    }""")

                            if drawer_open:
                                self.log_emitted.emit(f"    💬 Opened comment drawer for Reel #{reel_idx}. Scanning comments for keywords...")
                            else:
                                self.log_emitted.emit(f"    ⚠️ Could not open comment drawer for Reel #{reel_idx}.")

                            self._interruptible_sleep(0.8)
                            dismiss_facebook_popups(page)

                            # Isolated JS scan: Scans ONLY active right-hand comment drawer panel
                            scan_res = page.evaluate("""() => {
                                let container = document.querySelector('div[data-pagelet*="Comment"], div[role="dialog"], div[role="complementary"]');
                                if (!container) {
                                    const candidates = Array.from(document.querySelectorAll('div'));
                                    for (const c of candidates) {
                                        const r = c.getBoundingClientRect();
                                        if (r.left > window.innerWidth * 0.5 && r.width > 180 && r.height > 200 && r.top < window.innerHeight * 0.4) {
                                            container = c;
                                            break;
                                        }
                                    }
                                }
                                if (!container) {
                                    container = document.body;
                                }

                                const rawTxt = (container.innerText || container.textContent || "").toLowerCase();
                                const anchors = Array.from(container.querySelectorAll('a[href]'));
                                const linkStrings = anchors.map(a => {
                                    let h = a.getAttribute('href') || a.href || "";
                                    try { h = decodeURIComponent(h); } catch(e) {}
                                    const t = a.innerText || a.textContent || "";
                                    return (h + " " + t).toLowerCase();
                                });

                                return { text: rawTxt, links: linkStrings };
                            }""")

                            drawer_text = scan_res.get("text", "")
                            drawer_links = scan_res.get("links", [])

                            for kw in self.target_keywords:
                                kw_lower = kw.strip().lower()
                                if not kw_lower:
                                    continue

                                # 1. Check links inside comments drawer
                                for lk in drawer_links:
                                    if kw_lower in lk:
                                        link_found = True
                                        matched_kw = kw_lower
                                        break
                                if link_found:
                                    break

                                # 2. Check innerText inside comments drawer
                                if kw_lower in drawer_text:
                                    link_found = True
                                    matched_kw = kw_lower
                                    break

                            if link_found:
                                self.log_emitted.emit(f"    🎯 MATCH DETECTED! Target keyword '{matched_kw}' found in Reel #{reel_idx} comments/links!")
                            else:
                                self.log_emitted.emit(f"    ℹ️ No target keyword matching {self.target_keywords} found in Reel #{reel_idx} comments.")

                        except Exception as scan_err:
                            self.log_emitted.emit(f"    ⚠️ Comment scan error on Reel #{reel_idx}: {scan_err}")

                        if self.stop_requested:
                            break

                        # Step 3: If match found, post comment and pause random delay
                        if link_found and current_reel_id not in commented_reel_ids:
                            self.log_emitted.emit(f"    🎯 MATCH CONFIRMED! Keyword '{matched_kw}' detected in Reel #{reel_idx} comments.")

                            if self.comments_list:
                                chosen_comment = random.choice(self.comments_list)
                                self.log_emitted.emit(f"    💬 Preparing to post comment: '{chosen_comment}'")

                                posted_ok = False
                                dismiss_facebook_popups(page)

                                # 1. Find Viewport Coordinates of Comment Input Box ("Comment as ...")
                                box_coords = page.evaluate("""() => {
                                    const all = Array.from(document.querySelectorAll('div, span, p, form'));
                                    for (const el of all) {
                                        if (el.children.length > 3) continue;
                                        const txt = (el.innerText || el.getAttribute('aria-label') || '').trim().toLowerCase();
                                        if (!txt) continue;
                                        if (txt.includes('comment as') || txt.includes('write a comment') || txt.includes('একটি মন্তব্য') || txt.includes('মন্তব্য করুন')) {
                                            const r = el.getBoundingClientRect();
                                            if (r.width > 20 && r.height > 10 && r.left > window.innerWidth * 0.4) {
                                                return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
                                            }
                                        }
                                    }
                                    const candidates = Array.from(document.querySelectorAll('div[role="button"], div[role="textbox"], form div'));
                                    for (const d of candidates) {
                                        const r = d.getBoundingClientRect();
                                        if (r.top > window.innerHeight * 0.6 && r.left > window.innerWidth * 0.5 && r.width > 80 && r.height > 15) {
                                            return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
                                        }
                                    }
                                    return null;
                                }""")

                                if box_coords:
                                    cx, cy = box_coords["x"], box_coords["y"]
                                    try:
                                        page.mouse.move(cx, cy)
                                        self._interruptible_sleep(0.1)
                                        page.mouse.click(cx, cy)
                                        self._interruptible_sleep(0.5)
                                    except Exception:
                                        pass

                                # Fallback JS focus/click
                                page.evaluate("""() => {
                                    let activeBox = document.querySelector('div[data-lexical-editor="true"], div[role="textbox"][contenteditable="true"]');
                                    if (activeBox) { activeBox.focus(); activeBox.click(); return; }
                                    const placeholders = Array.from(document.querySelectorAll('div[aria-label*="Comment as"], div[aria-label*="Write a comment"], div[aria-label*="একটি মন্তব্য"], div[role="textbox"]'));
                                    for (const el of placeholders) {
                                        const r = el.getBoundingClientRect();
                                        if (r.width > 0 && r.height > 0) { el.click(); break; }
                                    }
                                }""")
                                self._interruptible_sleep(0.5)

                                comment_input_selectors = [
                                    'div[data-lexical-editor="true"] p[dir="auto"]',
                                    'div[role="textbox"][contenteditable="true"] p[dir="auto"]',
                                    'div[data-lexical-editor="true"]',
                                    'div[role="textbox"][contenteditable="true"]',
                                    'div[aria-label*="Comment as"]',
                                    'div[aria-label*="Write a comment"]',
                                    'div[aria-label*="একটি মন্তব্য লিখুন"]',
                                    'p[dir="auto"]'
                                ]

                                target_box = None
                                for sel in comment_input_selectors:
                                    try:
                                        boxes = page.query_selector_all(sel)
                                        for box in boxes:
                                            if box and box.is_visible():
                                                target_box = box
                                                break
                                        if target_box:
                                            break
                                    except Exception:
                                        pass

                                if target_box:
                                    try:
                                        target_box.click(force=True)
                                        self._interruptible_sleep(0.3)
                                        try:
                                            page.keyboard.press("Control+A")
                                            page.keyboard.press("Backspace")
                                            self._interruptible_sleep(0.2)
                                        except Exception:
                                            pass

                                        page.keyboard.insert_text(chosen_comment)
                                        self._interruptible_sleep(0.5)

                                        # Lexical DOM state injection
                                        page.evaluate("""(commentText) => {
                                            const editor = document.activeElement || document.querySelector('div[data-lexical-editor="true"], div[role="textbox"][contenteditable="true"]');
                                            if (editor) {
                                                editor.focus();
                                                const p = editor.querySelector('p') || editor;
                                                p.textContent = commentText;
                                                editor.dispatchEvent(new InputEvent('input', { bubbles: true, cancelable: true, inputType: 'insertText', data: commentText }));
                                            }
                                        }""", chosen_comment)

                                        self._interruptible_sleep(0.6)
                                        page.keyboard.press("Enter")
                                        self._interruptible_sleep(1.5)

                                        # Click Paper Plane Send Icon Button (Excluding comment drawer toggle button!)
                                        page.evaluate("""() => {
                                            const sendBtns = Array.from(document.querySelectorAll('div[aria-label="Send"], div[aria-label="Post"], div[aria-label="Submit"], div[aria-label="পোস্ট"], div[aria-label="পাঠান"]'));
                                            for (const btn of sendBtns) {
                                                const r = btn.getBoundingClientRect();
                                                if (r.width > 0 && r.height > 0 && r.left > window.innerWidth * 0.6) {
                                                    btn.click();
                                                    return true;
                                                }
                                            }
                                            const svgs = Array.from(document.querySelectorAll('svg'));
                                            for (const svg of svgs) {
                                                const btn = svg.closest('div[role="button"]');
                                                if (btn) {
                                                    const r = btn.getBoundingClientRect();
                                                    if (r.left > window.innerWidth * 0.6 && r.top > window.innerHeight * 0.75) {
                                                        const aria = (btn.getAttribute('aria-label') || '').toLowerCase();
                                                        if (!aria.includes('comment') && !aria.includes('কমেন্ট') && !aria.includes('মন্তব্য')) {
                                                            btn.click();
                                                            return true;
                                                        }
                                                    }
                                                }
                                            }
                                            return false;
                                        }""")
                                        self._interruptible_sleep(1.5)

                                        posted_ok = True
                                    except Exception as post_err:
                                        self.log_emitted.emit(f"    ❌ Failed to type/post comment on Reel #{reel_idx}: {post_err}")
                                else:
                                    self.log_emitted.emit(f"    ❌ Comment input box could not be activated/found on Reel #{reel_idx}")

                                if posted_ok:
                                    comments_posted += 1
                                    commented_reel_ids.add(current_reel_id)
                                    self.log_emitted.emit(f"    ✅ Posted comment on Reel #{reel_idx}! (Comments Progress: {comments_posted}/{self.max_comments})")

                                    # Keep comment drawer open so posted comment remains visible during watch delay
                                    try:
                                        drawer_is_open = page.evaluate("""() => {
                                            const drawer = document.querySelector('div[data-pagelet*="Comment"], div[role="dialog"], div[role="complementary"]');
                                            if (drawer && drawer.getBoundingClientRect().width > 150) return true;
                                            return false;
                                        }""")
                                        if not drawer_is_open:
                                            page.evaluate("""() => {
                                                const allBtns = Array.from(document.querySelectorAll('div[role="button"]'));
                                                for (const b of allBtns) {
                                                    const aria = (b.getAttribute('aria-label') || '').toLowerCase();
                                                    if (aria.includes('comment') || aria.includes('কমেন্ট')) {
                                                        b.click();
                                                        return true;
                                                    }
                                                }
                                            }""")
                                    except Exception:
                                        pass
                                    
                                    # Auto-Follow Reel Creator
                                    auto_follow_facebook_reel_creator(page, log_func=lambda text: self.log_emitted.emit(text))
                                    
                                    min_p = max(1, self.min_delay)
                                    max_p = max(min_p, self.max_delay)
                                    post_pause = random.randint(min_p, max_p)
                                    self.log_emitted.emit(f"    ⏱️ Watching Reel video with posted comment visible for {post_pause}s...")
                                    for sec in range(post_pause, 0, -1):
                                        if self.stop_requested:
                                            break
                                        if sec % 5 == 0 or sec == post_pause or sec <= 3:
                                            self.log_emitted.emit(f"      ⏳ Watching Reel video... ({sec}s remaining)")
                                        self._interruptible_sleep(1.0)

                                    if comments_posted >= self.max_comments:
                                        self.log_emitted.emit(f"  🎯 Target comment limit reached ({comments_posted}/{self.max_comments} comments posted) for Profile '{pname}'!")
                                        break
                        else:
                            self.log_emitted.emit(f"    ⏭️ No target keyword in Reel #{reel_idx} comments.")
                            s_min = max(1, self.scan_min_delay)
                            s_max = max(s_min, self.scan_max_delay)
                            scan_pause = random.randint(s_min, s_max)
                            self.log_emitted.emit(f"    ⏱️ Scan Delay: Pausing {scan_pause}s before scrolling to next Reel...")
                            self._interruptible_sleep(scan_pause)

                        if self.stop_requested:
                            break

                        # Step 4: Scroll down via natural Mouse Wheel for Next Reel video
                        self.log_emitted.emit(f"    ⬇️ Step 4: Scrolling to Next Reel video via natural Mouse Wheel...")
                        scroll_to_next_facebook_reel(page, log_func=lambda text: self.log_emitted.emit(text))

                    self.log_emitted.emit(f"  🎉 [{pname}] Finished! Scanned {reels_checked} Reels | Posted {comments_posted}/{self.max_comments} Target Comments.")
                    return True
                finally:
                    with self._lock:
                        self._active_contexts.discard(context)
                    try:
                        context.close()
                    except Exception:
                        pass
        except Exception as err:
            self.log_emitted.emit(f"  ❌ Error processing [{pname}]: {err}")
            return False

    def run(self) -> None:
        total_profiles = len(self.profiles_list)
        if total_profiles == 0:
            self.finished_signal.emit(False, "No profiles found to run FB Comment Marketing Bot.")
            return

        self.log_emitted.emit(f"📢 Starting FB Comment Marketing Bot Engine for {total_profiles} Profile(s)...")
        self.log_emitted.emit(f"🎯 Keywords Filter: {', '.join(self.target_keywords)}")
        self.log_emitted.emit(f"⚙️ Target Limit: {self.max_comments} Comment(s)/ID | Scan Limit: {self.max_reels} Reels | Scan Delay: {self.scan_min_delay}-{self.scan_max_delay}s | Post-Comment Delay: {self.min_delay}-{self.max_delay}s")
        self.log_emitted.emit(f"⚡ Parallel Execution: {self.max_concurrent_browsers} Concurrent Browsers")

        completed = 0
        success_count = 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_concurrent_browsers) as executor:
            futures = {
                executor.submit(self._process_single_profile, p_idx, total_profiles, pdata): pdata
                for p_idx, pdata in enumerate(self.profiles_list, start=1)
            }

            for fut in concurrent.futures.as_completed(futures):
                if self.stop_requested:
                    self.log_emitted.emit("🛑 Stop signal acknowledged. Terminating active profile workers...")
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                completed += 1
                self.progress_updated.emit(completed, total_profiles)
                try:
                    if fut.result():
                        success_count += 1
                except Exception as exc:
                    self.log_emitted.emit(f"⚠️ Exception in comment marketing worker: {exc}")

        self.finished_signal.emit(True, f"FB Comment Marketing Bot Complete! Processed {success_count}/{total_profiles} Profile(s) successfully!")
